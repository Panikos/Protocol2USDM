"""
SAP (Statistical Analysis Plan) Extractor

Extracts USDM entities from SAP documents:
- AnalysisPopulation (ITT, PP, Safety, etc.)
- PopulationDefinition
- Characteristic (baseline characteristics)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count

logger = logging.getLogger(__name__)


@dataclass
class AnalysisPopulation:
    """USDM AnalysisPopulation entity."""
    id: str
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    population_type: str = "Analysis"  # Analysis, Safety, Efficacy, etc.
    criteria: Optional[str] = None
    instance_type: str = "AnalysisPopulation"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "populationType": self.population_type,
            "instanceType": self.instance_type,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.criteria:
            result["criteria"] = self.criteria
        return result


@dataclass
class Characteristic:
    """USDM Characteristic entity (baseline characteristic)."""
    id: str
    name: str
    description: Optional[str] = None
    data_type: str = "Text"
    instance_type: str = "Characteristic"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "dataType": self.data_type,
            "instanceType": self.instance_type,
            "description": self.description,
        }


@dataclass
class SAPData:
    """Container for SAP extraction results."""
    analysis_populations: List[AnalysisPopulation] = field(default_factory=list)
    characteristics: List[Characteristic] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysisPopulations": [p.to_dict() for p in self.analysis_populations],
            "characteristics": [c.to_dict() for c in self.characteristics],
            "summary": {
                "populationCount": len(self.analysis_populations),
                "characteristicCount": len(self.characteristics),
            }
        }


@dataclass
class SAPExtractionResult:
    """Result container for SAP extraction."""
    success: bool
    data: Optional[SAPData] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None
    source_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "sourceFile": self.source_file,
            "pagesUsed": self.pages_used,
            "modelUsed": self.model_used,
        }
        if self.data:
            result["sapData"] = self.data.to_dict()
        if self.error:
            result["error"] = self.error
        return result


SAP_EXTRACTION_PROMPT = """Extract Analysis Populations and Baseline Characteristics from this clinical document.

Look for analysis populations in:
- Section 9 (Statistical Considerations / Populations for Analysis)
- Statistical Analysis Plan sections
- Any section defining study populations

**Analysis Populations to extract:**
- Full Analysis Set (FAS) / Intent-to-Treat (ITT) population
- Modified ITT (mITT) population  
- Per-Protocol (PP) population
- Safety population / Safety Analysis Set
- Pharmacokinetic (PK) Analysis Set
- Pharmacodynamic (PD) Analysis Set
- Any other defined analysis populations

**Baseline Characteristics to extract:**
- Demographics (age, sex, race, ethnicity)
- Disease characteristics
- Prior therapies
- Baseline assessments

Return JSON:
```json
{{
  "analysisPopulations": [
    {{
      "id": "pop_1",
      "name": "Full Analysis Set",
      "label": "FAS",
      "description": "All participants who were enrolled and received at least 1 dose of study drug",
      "populationType": "Efficacy",
      "criteria": "Enrolled and received at least 1 dose"
    }},
    {{
      "id": "pop_2",
      "name": "Safety Analysis Set",
      "label": "SAF",
      "description": "All participants who received at least 1 dose of study drug",
      "populationType": "Safety",
      "criteria": "Received at least 1 dose"
    }}
  ],
  "characteristics": [
    {{
      "id": "char_1",
      "name": "Age",
      "description": "Age at baseline in years",
      "dataType": "Numeric"
    }}
  ]
}}
```

DOCUMENT TEXT:
{sap_text}
"""


def extract_from_sap(
    sap_path: str,
    model: str = "gemini-2.5-pro",
    output_dir: Optional[str] = None,
) -> SAPExtractionResult:
    """
    Extract analysis populations and characteristics from SAP document.
    """
    logger.info(f"Extracting from SAP: {sap_path}")
    
    if not Path(sap_path).exists():
        return SAPExtractionResult(
            success=False,
            error=f"SAP file not found: {sap_path}",
            source_file=sap_path,
        )
    
    # Extract text from SAP
    try:
        pages = list(range(min(40, get_page_count(sap_path))))
        text = extract_text_from_pages(sap_path, pages)
    except Exception as e:
        return SAPExtractionResult(
            success=False,
            error=f"Failed to read SAP: {e}",
            source_file=sap_path,
        )
    
    prompt = SAP_EXTRACTION_PROMPT.format(sap_text=text[:30000])
    
    try:
        # Combine system prompt with user prompt
        full_prompt = f"You are an expert biostatistician extracting analysis populations from SAP documents.\n\n{prompt}"
        result = call_llm(
            prompt=full_prompt,
            model_name=model,
            json_mode=True,
            temperature=0.1,
        )
        response = result.get('response', '')
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response
        raw_data = json.loads(json_str)
        
        populations = [
            AnalysisPopulation(
                id=p.get('id', f"pop_{i+1}"),
                name=p.get('name', ''),
                label=p.get('label'),
                description=p.get('description'),
                population_type=p.get('populationType', 'Analysis'),
                criteria=p.get('criteria'),
            )
            for i, p in enumerate(raw_data.get('analysisPopulations', []))
        ]
        
        characteristics = [
            Characteristic(
                id=c.get('id', f"char_{i+1}"),
                name=c.get('name', ''),
                description=c.get('description'),
                data_type=c.get('dataType', 'Text'),
            )
            for i, c in enumerate(raw_data.get('characteristics', []))
        ]
        
        data = SAPData(analysis_populations=populations, characteristics=characteristics)
        
        result = SAPExtractionResult(
            success=True,
            data=data,
            pages_used=pages,
            model_used=model,
            source_file=sap_path,
        )
        
        if output_dir:
            output_path = Path(output_dir) / "11_sap_populations.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Extracted {len(populations)} populations, {len(characteristics)} characteristics from SAP")
        return result
        
    except Exception as e:
        logger.error(f"SAP extraction failed: {e}")
        return SAPExtractionResult(
            success=False,
            error=str(e),
            source_file=sap_path,
            model_used=model,
        )

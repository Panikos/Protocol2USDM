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
    definition: Optional[str] = None  # Full definition text from SAP
    population_type: str = "Analysis"  # Analysis, Safety, Efficacy, etc.
    criteria: Optional[str] = None
    instance_type: str = "AnalysisPopulation"
    
    def to_dict(self) -> Dict[str, Any]:
        # Use definition as description if available, otherwise use description
        desc = self.definition or self.description or self.name
        result = {
            "id": self.id,
            "name": self.name,
            "text": desc,  # Required field per USDM schema
            "populationType": self.population_type,
            "instanceType": self.instance_type,
        }
        if self.label:
            result["label"] = self.label
        if desc:
            result["populationDescription"] = desc
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
    code: str = ""  # Will be set from name if not provided
    instance_type: str = "Characteristic"
    
    def to_dict(self) -> Dict[str, Any]:
        # USDM requires Characteristic to have Code fields
        char_code = self.code or self.name.upper().replace(" ", "_")[:20]
        return {
            "id": self.id,
            "name": self.name,
            "code": char_code,  # Required by USDM
            "codeSystem": "http://www.cdisc.org/baseline-characteristics",  # Required
            "codeSystemVersion": "2024-03-29",  # Required
            "decode": self.name,  # Required - human readable name
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


SAP_EXTRACTION_PROMPT = """Extract Analysis Populations with their COMPLETE DEFINITIONS from this SAP document.

**CRITICAL: You MUST extract the full definition/criteria text for each population.**

Look for analysis population definitions in ANY section titled:
- "DATA SETS ANALYZED", "STUDY POPULATIONS", "ANALYSIS SETS", "POPULATIONS FOR ANALYSIS"
- Subsections with population names as headers (e.g., "Screened Set", "Full Analysis Set", "Safety Set")
- The definition text immediately follows the population name/header
- Definitions typically start with "All participants who...", "All subjects who...", "Includes all..."

**For each population, extract:**
1. **Name**: Full name (e.g., "Full Analysis Set", "Safety Analysis Set")
2. **Label/Abbreviation**: Short form (e.g., "FAS", "SAF", "ITT", "PP")
3. **Definition**: The COMPLETE text describing who is included. This is REQUIRED.
   - Look for phrases like "includes all subjects who...", "defined as...", "consists of..."
   - Extract the full eligibility criteria text
4. **Type**: Efficacy, Safety, or PK/PD

**Common populations and their typical definitions:**
- Full Analysis Set (FAS): Usually all randomized subjects who received at least one dose
- Safety Analysis Set (SAF): All subjects who received at least one dose of study drug
- Per-Protocol Set (PP): Subjects without major protocol deviations
- PK Analysis Set: Subjects with evaluable PK samples

Return JSON with COMPLETE definitions (not placeholders):
```json
{{
  "analysisPopulations": [
    {{
      "id": "pop_1",
      "name": "Full Analysis Set",
      "label": "FAS",
      "definition": "All enrolled subjects who received at least one dose of study drug and have at least one post-baseline efficacy assessment",
      "populationType": "Efficacy",
      "criteria": "Enrolled AND received >=1 dose AND has post-baseline assessment"
    }},
    {{
      "id": "pop_2", 
      "name": "Safety Analysis Set",
      "label": "SAF",
      "definition": "All subjects who received at least one dose of study drug, whether randomized or not",
      "populationType": "Safety",
      "criteria": "Received >=1 dose"
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

**IMPORTANT: Do NOT return placeholder text like "Definition not found" or "See section X". 
Search the ENTIRE document for definition text. The definition is the sentence(s) that describe which subjects are included.**

**Example definitions from typical SAPs:**
- "The Screened Set includes all subjects who signed an informed consent form."
- "The Full Analysis Set includes all enrolled subjects who received at least one dose of study drug."
- "The Safety Set consists of all subjects who received at least one dose of study medication."

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
        
        # Handle case where LLM returns a list directly
        if isinstance(raw_data, list):
            raw_data = {"analysisPopulations": raw_data, "characteristics": []}
        
        pop_list = raw_data.get('analysisPopulations', [])
        if not isinstance(pop_list, list):
            pop_list = []
        
        populations = [
            AnalysisPopulation(
                id=p.get('id', f"pop_{i+1}") if isinstance(p, dict) else f"pop_{i+1}",
                name=p.get('name', '') if isinstance(p, dict) else str(p),
                label=p.get('label') if isinstance(p, dict) else None,
                description=p.get('description') if isinstance(p, dict) else None,
                definition=p.get('definition') if isinstance(p, dict) else None,
                population_type=p.get('populationType', 'Analysis') if isinstance(p, dict) else 'Analysis',
                criteria=p.get('criteria') if isinstance(p, dict) else None,
            )
            for i, p in enumerate(pop_list)
        ]
        
        char_list = raw_data.get('characteristics', [])
        if not isinstance(char_list, list):
            char_list = []
        
        characteristics = [
            Characteristic(
                id=c.get('id', f"char_{i+1}") if isinstance(c, dict) else f"char_{i+1}",
                name=c.get('name', '') if isinstance(c, dict) else str(c),
                description=c.get('description') if isinstance(c, dict) else None,
                data_type=c.get('dataType', 'Text') if isinstance(c, dict) else 'Text',
            )
            for i, c in enumerate(char_list)
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

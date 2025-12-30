"""
Derived Variable Extractor

Extracts definitions of derived/computed variables from protocol PDFs.
Captures how analysis variables are computed from raw collected data.
"""

import re
import logging
from typing import List, Optional, Tuple, Dict, Any

from .schema import (
    DerivedVariable,
    VariableType,
    ExecutionModelData,
    ExecutionModelResult,
)

logger = logging.getLogger(__name__)


# Keywords for finding derived variable pages
VARIABLE_KEYWORDS = [
    "baseline", "change from baseline", "percent change",
    "derived", "computed", "calculated", "analysis variable",
    "imputation", "LOCF", "MMRM", "missing data",
    "efficacy variable", "safety variable", "pharmacokinetic",
    "AUC", "Cmax", "Tmax", "half-life",
]

# Patterns for detecting variable types
VARIABLE_TYPE_PATTERNS = [
    (r'change\s+from\s+baseline', VariableType.CHANGE_FROM_BASELINE, 0.95),
    (r'percent(?:age)?\s+change', VariableType.PERCENT_CHANGE, 0.95),
    (r'time\s+to\s+(?:first\s+)?(?:event|occurrence)', VariableType.TIME_TO_EVENT, 0.90),
    (r'baseline\s+(?:value|measurement)', VariableType.BASELINE, 0.90),
    (r'categorical|binary|dichotomous', VariableType.CATEGORICAL, 0.85),
    (r'composite\s+(?:endpoint|score|variable)', VariableType.COMPOSITE, 0.90),
]

# Common baseline definitions
BASELINE_PATTERNS = [
    (r'baseline\s+(?:is\s+)?(?:defined\s+as|=)\s+([^.]+)', 0.95),
    (r'last\s+(?:non-?missing\s+)?(?:value|observation)\s+(?:before|prior\s+to)\s+([^.]+)', 0.90),
    (r'(?:day\s*-?\d+|screening|randomization)\s+(?:value|measurement)', 0.85),
    (r'pre-?(?:dose|treatment|randomization)\s+(?:value|measurement)', 0.85),
]

# Imputation methods
IMPUTATION_PATTERNS = [
    (r'LOCF|last\s+observation\s+carried\s+forward', 'LOCF'),
    (r'MMRM|mixed\s+(?:model|effect)', 'MMRM'),
    (r'multiple\s+imputation', 'MI'),
    (r'worst\s+case', 'worst_case'),
    (r'baseline\s+carried\s+forward', 'BCF'),
]


def find_variable_pages(pdf_path: str) -> List[int]:
    """Find pages likely to contain derived variable definitions."""
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    page_count = get_page_count(pdf_path)
    relevant_pages = []
    
    for page_idx in range(min(page_count, 80)):
        text = extract_text_from_pages(pdf_path, [page_idx])
        if text:
            text_lower = text.lower()
            score = sum(1 for kw in VARIABLE_KEYWORDS if kw in text_lower)
            if score >= 2:
                relevant_pages.append(page_idx)
    
    return relevant_pages


def _detect_variable_type(text: str) -> Tuple[VariableType, float]:
    """Detect the type of derived variable from text."""
    text_lower = text.lower()
    
    for pattern, var_type, confidence in VARIABLE_TYPE_PATTERNS:
        if re.search(pattern, text_lower):
            return var_type, confidence
    
    return VariableType.CUSTOM, 0.5


def _extract_source_variables(text: str) -> List[str]:
    """Extract source variables needed for derivation."""
    sources = []
    text_lower = text.lower()
    
    # Common measurement variables
    measurements = [
        'glucose', 'HbA1c', 'blood pressure', 'heart rate',
        'weight', 'BMI', 'creatinine', 'ALT', 'AST',
        'hemoglobin', 'platelet', 'WBC', 'neutrophil',
        'tumor size', 'PSA', 'CA-125',
    ]
    
    for var in measurements:
        if var.lower() in text_lower:
            sources.append(var)
    
    # Extract from "based on" patterns
    based_on = re.findall(r'based\s+on\s+(?:the\s+)?(\w+(?:\s+\w+)?)', text_lower)
    sources.extend(based_on)
    
    # Extract from "using" patterns
    using = re.findall(r'using\s+(?:the\s+)?(\w+(?:\s+\w+)?)', text_lower)
    sources.extend(using)
    
    return list(set(sources))


def _extract_baseline_definition(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract baseline definition and visit."""
    text_lower = text.lower()
    
    definition = None
    visit = None
    
    for pattern, confidence in BASELINE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            definition = match.group(1).strip() if match.lastindex else match.group(0)
            break
    
    # Extract baseline visit
    visit_patterns = [
        r'(?:at\s+)?(?:day\s*-?\d+)',
        r'(?:at\s+)?screening',
        r'(?:at\s+)?randomization',
        r'(?:at\s+)?(?:visit\s+\d+)',
    ]
    
    for pattern in visit_patterns:
        match = re.search(pattern, text_lower)
        if match:
            visit = match.group(0).strip()
            break
    
    return definition, visit


def _extract_derivation_rule(text: str, var_type: VariableType) -> Optional[str]:
    """Extract the derivation rule/formula."""
    text_lower = text.lower()
    
    # Look for explicit formulas
    formula_patterns = [
        r'(?:calculated|computed|derived)\s+(?:as|by)\s+[:\s]*([^.]+)',
        r'formula[:\s]+([^.]+)',
        r'=\s*([^.]+)',
    ]
    
    for pattern in formula_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    
    # Build rule based on variable type
    if var_type == VariableType.CHANGE_FROM_BASELINE:
        return "post_value - baseline_value"
    elif var_type == VariableType.PERCENT_CHANGE:
        return "((post_value - baseline_value) / baseline_value) * 100"
    elif var_type == VariableType.TIME_TO_EVENT:
        return "event_date - reference_date"
    
    return None


def _extract_analysis_window(text: str) -> Optional[str]:
    """Extract the analysis time window."""
    patterns = [
        r'(?:at\s+)?week\s+(\d+)\s*(?:±\s*(\d+)\s*days?)?',
        r'(?:at\s+)?day\s+(\d+)\s*(?:±\s*(\d+)\s*days?)?',
        r'(?:at\s+)?month\s+(\d+)',
        r'(?:between\s+)?(?:day|week)\s+(\d+)\s+(?:and|to)\s+(?:day|week)\s+(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(0).strip()
    
    return None


def _extract_imputation_rule(text: str) -> Optional[str]:
    """Extract imputation method for missing data."""
    text_lower = text.lower()
    
    for pattern, method in IMPUTATION_PATTERNS:
        if re.search(pattern, text_lower):
            return method
    
    return None


def _extract_unit(text: str) -> Optional[str]:
    """Extract the measurement unit."""
    unit_patterns = [
        r'(?:expressed|reported|measured)\s+(?:in|as)\s+(\w+(?:/\w+)?)',
        r'(\d+(?:\.\d+)?)\s*(mg/?d?l?|mmol/?l?|%|kg/?m?2?|mm\s*hg)',
    ]
    
    for pattern in unit_patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1)
    
    return None


def _parse_variables_from_text(text: str) -> List[DerivedVariable]:
    """Parse derived variable definitions from text."""
    variables = []
    
    # Split by common section markers
    sections = re.split(
        r'(?=\n(?:\d+\.\d+|\•|\-)\s+)',
        text
    )
    
    for i, section in enumerate(sections):
        if len(section.strip()) < 30:
            continue
        
        # Check if this section defines a variable
        if not any(kw in section.lower() for kw in ['baseline', 'change', 'derived', 'calculated', 'variable']):
            continue
        
        var_type, confidence = _detect_variable_type(section)
        
        # Extract variable name
        name_patterns = [
            r'(?:derived|analysis|efficacy)\s+variable[:\s]+([^.]+)',
            r'change\s+from\s+baseline\s+(?:in\s+)?(\w+(?:\s+\w+)?)',
            r'(\w+(?:\s+\w+)?)\s+(?:is\s+)?(?:defined|calculated|derived)',
        ]
        
        name = None
        for pattern in name_patterns:
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                break
        
        if not name:
            name = f"Derived Variable {i+1}"
        
        name = name[:80]  # Truncate
        
        source_vars = _extract_source_variables(section)
        baseline_def, baseline_visit = _extract_baseline_definition(section)
        derivation = _extract_derivation_rule(section, var_type)
        analysis_window = _extract_analysis_window(section)
        imputation = _extract_imputation_rule(section)
        unit = _extract_unit(section)
        
        variable = DerivedVariable(
            id=f"dv_{i+1}",
            name=name,
            variable_type=var_type,
            source_variables=source_vars,
            derivation_rule=derivation,
            baseline_definition=baseline_def,
            baseline_visit=baseline_visit,
            analysis_window=analysis_window,
            imputation_rule=imputation,
            unit=unit,
            source_text=section[:200],
        )
        variables.append(variable)
    
    return variables


def extract_derived_variables(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
    sap_path: Optional[str] = None,
) -> ExecutionModelResult:
    """
    Extract derived variable definitions from protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use
        pages: Specific pages to analyze
        use_llm: Whether to use LLM enhancement
        
    Returns:
        ExecutionModelResult with derived variables
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting derived variable extraction...")
    
    # Find relevant pages
    pages = find_variable_pages(pdf_path)
    
    if not pages:
        pages = list(range(min(50, get_page_count(pdf_path))))
    
    logger.info(f"Found {len(pages)} potential variable pages")
    
    # Extract text
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Parse variables from text
    variables = _parse_variables_from_text(text)
    
    # Extract from SAP if provided (SAP has detailed derivation rules)
    if sap_path:
        logger.info("Extracting additional variables from SAP...")
        try:
            sap_pages = find_variable_pages(sap_path)
            if not sap_pages:
                sap_pages = list(range(min(80, get_page_count(sap_path))))
            sap_text = extract_text_from_pages(sap_path, sap_pages)
            if sap_text:
                sap_variables = _parse_variables_from_text(sap_text)
                # Merge SAP variables (SAP has more detail on analysis methods)
                for sap_var in sap_variables:
                    existing = [v for v in variables if v.name.lower() in sap_var.name.lower() or sap_var.name.lower() in v.name.lower()]
                    if existing:
                        # Enhance existing with SAP details
                        if sap_var.derivation_rule and not existing[0].derivation_rule:
                            existing[0].derivation_rule = sap_var.derivation_rule
                        if sap_var.imputation_rule and not existing[0].imputation_rule:
                            existing[0].imputation_rule = sap_var.imputation_rule
                        if sap_var.baseline_definition and not existing[0].baseline_definition:
                            existing[0].baseline_definition = sap_var.baseline_definition
                    else:
                        sap_var.source_text = f"[SAP] {sap_var.source_text}"
                        variables.append(sap_var)
                logger.info(f"  Added/enhanced variables from SAP: {len(sap_variables)}")
        except Exception as e:
            logger.warning(f"SAP variable extraction failed: {e}")
    
    # LLM enhancement
    if use_llm and len(text) > 100:
        try:
            enhanced = _enhance_with_llm(text, variables, model)
            if enhanced:
                variables = enhanced
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
    
    logger.info(f"Extracted {len(variables)} derived variables")
    
    return ExecutionModelResult(
        success=True,
        data=ExecutionModelData(derived_variables=variables),
        pages_used=pages,
        model_used=model,
    )


def _enhance_with_llm(
    text: str,
    variables: List[DerivedVariable],
    model: str,
) -> Optional[List[DerivedVariable]]:
    """Enhance variable extraction using LLM."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol text and extract DERIVED VARIABLE definitions.

For each derived/computed variable, identify:
1. Variable name
2. Type: Baseline, ChangeFromBaseline, PercentChange, TimeToEvent, Categorical, Composite, Custom
3. Source variables required
4. Derivation rule/formula
5. Baseline definition (when/how)
6. Analysis time window
7. Imputation method for missing data

Return JSON:
```json
{{
  "variables": [
    {{
      "name": "Change from Baseline in HbA1c",
      "type": "ChangeFromBaseline",
      "sourceVariables": ["HbA1c"],
      "derivationRule": "week12_value - baseline_value",
      "baselineDefinition": "Last non-missing value before Day 1",
      "baselineVisit": "Day -1",
      "analysisWindow": "Week 12 ± 7 days",
      "imputationRule": "MMRM",
      "unit": "%"
    }}
  ]
}}
```

Protocol text:
{text[:6000]}

Return ONLY the JSON."""

    try:
        response = call_llm(
            prompt=prompt,
            model_name=model,
            max_tokens=3000,
            temperature=0.1,
        )
        
        if not response:
            return None
        
        # Parse JSON response
        import json
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return None
        
        data = json.loads(json_match.group())
        
        # Convert to DerivedVariable objects
        enhanced = []
        for i, var_data in enumerate(data.get('variables', [])):
            var_type = VariableType.CUSTOM
            type_str = var_data.get('type', 'Custom')
            for vt in VariableType:
                if vt.value.lower() == type_str.lower():
                    var_type = vt
                    break
            
            variable = DerivedVariable(
                id=f"dv_{i+1}",
                name=var_data.get('name', f'Variable {i+1}'),
                variable_type=var_type,
                source_variables=var_data.get('sourceVariables', []),
                derivation_rule=var_data.get('derivationRule'),
                baseline_definition=var_data.get('baselineDefinition'),
                baseline_visit=var_data.get('baselineVisit'),
                analysis_window=var_data.get('analysisWindow'),
                imputation_rule=var_data.get('imputationRule'),
                unit=var_data.get('unit'),
            )
            enhanced.append(variable)
        
        return enhanced if enhanced else None
        
    except Exception as e:
        logger.warning(f"LLM variable enhancement failed: {e}")
        return None

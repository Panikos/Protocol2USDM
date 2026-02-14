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
        # USDM requires name to have at least 1 character
        name = self.name or self.label or self.definition or f"Population {self.id}"
        result = {
            "id": self.id,
            "name": name,
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
class DerivedVariable:
    """SAP-defined derived variable with calculation formula."""
    id: str
    name: str
    formula: str
    unit: Optional[str] = None
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "formula": self.formula,
        }
        if self.unit:
            result["unit"] = self.unit
        if self.notes:
            result["notes"] = self.notes
        return result


@dataclass
class DataHandlingRule:
    """SAP-defined data handling rule (missing data, BLQ, etc.)."""
    id: str
    name: str
    rule: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "rule": self.rule,
        }


@dataclass
class StatisticalMethod:
    """Statistical analysis method with STATO ontology and CDISC ARS mapping."""
    id: str
    name: str  # e.g., "ANCOVA", "MMRM", "Kaplan-Meier"
    description: str  # Full description from SAP
    endpoint_name: Optional[str] = None  # Which endpoint this applies to
    stato_code: Optional[str] = None  # STATO ontology code (e.g., "STATO:0000029")
    stato_label: Optional[str] = None  # STATO preferred label
    hypothesis_type: Optional[str] = None  # "superiority", "non-inferiority", "equivalence"
    test_type: Optional[str] = None  # "one-sided", "two-sided"
    alpha_level: Optional[float] = None  # Significance level (e.g., 0.05)
    covariates: Optional[List[str]] = None  # Covariates/stratification factors
    software: Optional[str] = None  # Statistical software (SAS, R, etc.)
    # CDISC ARS linkage
    ars_method_id: Optional[str] = None  # ARS AnalysisMethod identifier pattern
    ars_operation_id: Optional[str] = None  # ARS Operation code (e.g., "Mth01_CatVar_Count_ByGrp")
    ars_reason: Optional[str] = None  # ARS Analysis reason: PRIMARY, SENSITIVITY, EXPLORATORY
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
        if self.endpoint_name:
            result["endpointName"] = self.endpoint_name
        if self.stato_code:
            result["statoCode"] = self.stato_code
        if self.stato_label:
            result["statoLabel"] = self.stato_label
        if self.hypothesis_type:
            result["hypothesisType"] = self.hypothesis_type
        if self.test_type:
            result["testType"] = self.test_type
        if self.alpha_level is not None:
            result["alphaLevel"] = self.alpha_level
        if self.covariates:
            result["covariates"] = self.covariates
        if self.software:
            result["software"] = self.software
        # ARS linkage
        if self.ars_method_id:
            result["arsMethodId"] = self.ars_method_id
        if self.ars_operation_id:
            result["arsOperationId"] = self.ars_operation_id
        if self.ars_reason:
            result["arsReason"] = self.ars_reason
        return result


@dataclass
class MultiplicityAdjustment:
    """Multiplicity adjustment procedure for controlling Type I error."""
    id: str
    name: str  # e.g., "Hochberg", "Bonferroni", "Graphical"
    description: str
    method_type: str  # "familywise", "gatekeeping", "graphical", "alpha-spending"
    stato_code: Optional[str] = None  # STATO code if applicable
    overall_alpha: Optional[float] = None  # Family-wise error rate
    endpoints_covered: Optional[List[str]] = None  # Which endpoints are in the family
    hierarchy: Optional[str] = None  # Testing hierarchy description
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "methodType": self.method_type,
        }
        if self.stato_code:
            result["statoCode"] = self.stato_code
        if self.overall_alpha is not None:
            result["overallAlpha"] = self.overall_alpha
        if self.endpoints_covered:
            result["endpointsCovered"] = self.endpoints_covered
        if self.hierarchy:
            result["hierarchy"] = self.hierarchy
        return result


@dataclass
class SensitivityAnalysis:
    """Sensitivity analysis specification from SAP with CDISC ARS linkage."""
    id: str
    name: str
    description: str
    primary_endpoint: Optional[str] = None  # Which endpoint this is for
    analysis_type: str = "sensitivity"  # "sensitivity", "supportive", "exploratory"
    method_variation: Optional[str] = None  # How it differs from primary
    population: Optional[str] = None  # Which population (e.g., PP vs ITT)
    # CDISC ARS linkage
    ars_reason: Optional[str] = None  # ARS reason code: SENSITIVITY, EXPLORATORY, etc.
    ars_analysis_id: Optional[str] = None  # Reference to ARS Analysis object
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "analysisType": self.analysis_type,
        }
        if self.primary_endpoint:
            result["primaryEndpoint"] = self.primary_endpoint
        if self.method_variation:
            result["methodVariation"] = self.method_variation
        if self.population:
            result["population"] = self.population
        # ARS linkage
        if self.ars_reason:
            result["arsReason"] = self.ars_reason
        if self.ars_analysis_id:
            result["arsAnalysisId"] = self.ars_analysis_id
        return result


@dataclass
class SubgroupAnalysis:
    """Pre-specified subgroup analysis from SAP."""
    id: str
    name: str  # e.g., "Age subgroup", "Region subgroup"
    description: str
    subgroup_variable: str  # Variable used for subgrouping
    categories: Optional[List[str]] = None  # Subgroup categories
    endpoints: Optional[List[str]] = None  # Which endpoints
    interaction_test: bool = False  # Whether interaction test is planned
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "subgroupVariable": self.subgroup_variable,
            "interactionTest": self.interaction_test,
        }
        if self.categories:
            result["categories"] = self.categories
        if self.endpoints:
            result["endpoints"] = self.endpoints
        return result


@dataclass
class InterimAnalysis:
    """Interim analysis specification from SAP with CDISC ARS linkage."""
    id: str
    name: str  # e.g., "IA1", "Final Analysis"
    description: str
    timing: Optional[str] = None  # When it occurs (e.g., "50% information")
    information_fraction: Optional[float] = None  # 0.0-1.0
    stopping_rule_efficacy: Optional[str] = None  # Efficacy stopping boundary
    stopping_rule_futility: Optional[str] = None  # Futility stopping boundary
    alpha_spent: Optional[float] = None  # Alpha spent at this look
    spending_function: Optional[str] = None  # e.g., "O'Brien-Fleming", "Pocock"
    # CDISC ARS linkage
    ars_reporting_event_type: Optional[str] = None  # ARS ReportingEvent type: INTERIM_1, INTERIM_2, FINAL
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
        if self.timing:
            result["timing"] = self.timing
        if self.information_fraction is not None:
            result["informationFraction"] = self.information_fraction
        if self.stopping_rule_efficacy:
            result["stoppingRuleEfficacy"] = self.stopping_rule_efficacy
        if self.stopping_rule_futility:
            result["stoppingRuleFutility"] = self.stopping_rule_futility
        if self.alpha_spent is not None:
            result["alphaSpent"] = self.alpha_spent
        if self.spending_function:
            result["spendingFunction"] = self.spending_function
        # ARS linkage
        if self.ars_reporting_event_type:
            result["arsReportingEventType"] = self.ars_reporting_event_type
        return result


@dataclass
class SampleSizeCalculation:
    """Sample size and power calculation from SAP."""
    id: str
    name: str
    description: str
    target_sample_size: Optional[int] = None
    power: Optional[float] = None  # e.g., 0.80, 0.90
    alpha: Optional[float] = None  # e.g., 0.05
    effect_size: Optional[str] = None  # Expected treatment effect
    dropout_rate: Optional[float] = None  # Expected dropout
    assumptions: Optional[str] = None  # Key assumptions
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
        if self.target_sample_size is not None:
            result["targetSampleSize"] = self.target_sample_size
        if self.power is not None:
            result["power"] = self.power
        if self.alpha is not None:
            result["alpha"] = self.alpha
        if self.effect_size:
            result["effectSize"] = self.effect_size
        if self.dropout_rate is not None:
            result["dropoutRate"] = self.dropout_rate
        if self.assumptions:
            result["assumptions"] = self.assumptions
        return result


@dataclass
class SAPData:
    """Container for SAP extraction results."""
    analysis_populations: List[AnalysisPopulation] = field(default_factory=list)
    characteristics: List[Characteristic] = field(default_factory=list)
    derived_variables: List[DerivedVariable] = field(default_factory=list)
    data_handling_rules: List[DataHandlingRule] = field(default_factory=list)
    statistical_methods: List[StatisticalMethod] = field(default_factory=list)
    multiplicity_adjustments: List[MultiplicityAdjustment] = field(default_factory=list)
    sensitivity_analyses: List[SensitivityAnalysis] = field(default_factory=list)
    subgroup_analyses: List[SubgroupAnalysis] = field(default_factory=list)
    interim_analyses: List[InterimAnalysis] = field(default_factory=list)
    sample_size_calculations: List[SampleSizeCalculation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysisPopulations": [p.to_dict() for p in self.analysis_populations],
            "characteristics": [c.to_dict() for c in self.characteristics],
            "derivedVariables": [d.to_dict() for d in self.derived_variables],
            "dataHandlingRules": [r.to_dict() for r in self.data_handling_rules],
            "statisticalMethods": [s.to_dict() for s in self.statistical_methods],
            "multiplicityAdjustments": [m.to_dict() for m in self.multiplicity_adjustments],
            "sensitivityAnalyses": [s.to_dict() for s in self.sensitivity_analyses],
            "subgroupAnalyses": [s.to_dict() for s in self.subgroup_analyses],
            "interimAnalyses": [i.to_dict() for i in self.interim_analyses],
            "sampleSizeCalculations": [s.to_dict() for s in self.sample_size_calculations],
            "summary": {
                "populationCount": len(self.analysis_populations),
                "characteristicCount": len(self.characteristics),
                "derivedVariableCount": len(self.derived_variables),
                "dataHandlingRuleCount": len(self.data_handling_rules),
                "statisticalMethodCount": len(self.statistical_methods),
                "multiplicityAdjustmentCount": len(self.multiplicity_adjustments),
                "sensitivityAnalysisCount": len(self.sensitivity_analyses),
                "subgroupAnalysisCount": len(self.subgroup_analyses),
                "interimAnalysisCount": len(self.interim_analyses),
                "sampleSizeCalculationCount": len(self.sample_size_calculations),
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


SAP_EXTRACTION_PROMPT = """Extract comprehensive statistical analysis information from this SAP document for USDM/STATO mapping.

## PART 1: Analysis Populations (CDISC Standard)

**Extract ALL 7 standard CDISC population types if defined:**

| populationType | Common Names | Typical Definition |
|----------------|--------------|-------------------|
| Screened | Screened Set, Screening Population | All subjects who signed ICF |
| Enrolled | Enrolled Set, Enrollment Population | Signed ICF + eligible + registered |
| FullAnalysis | Full Analysis Set, FAS, ITT, mITT | Received ≥1 dose (primary efficacy) |
| PerProtocol | Per Protocol Set, PP, Evaluable | FAS + no major deviations + compliant |
| Safety | Safety Set, Safety Population, SAF | Received ≥1 dose (safety analysis) |
| Pharmacokinetic | PK Analysis Set, PK Population | Sufficient plasma samples for PK |
| Pharmacodynamic | PD Analysis Set, PD Population | Sufficient samples for PD analysis |

## PART 2: Statistical Methods (STATO + CDISC ARS Mapping)

Extract primary and secondary statistical analysis methods. Map to STATO codes and CDISC ARS identifiers:

| Method | STATO Code | ARS Operation Pattern |
|--------|------------|----------------------|
| ANCOVA | STATO:0000029 | Mth01_ContVar_Ancova |
| ANOVA | STATO:0000026 | Mth01_ContVar_Anova |
| MMRM | STATO:0000325 | Mth01_ContVar_MMRM |
| t-test | STATO:0000304 | Mth01_ContVar_Ttest |
| Chi-square | STATO:0000049 | Mth01_CatVar_ChiSq |
| Fisher exact | STATO:0000073 | Mth01_CatVar_FisherExact |
| Wilcoxon | STATO:0000076 | Mth01_ContVar_Wilcoxon |
| Kaplan-Meier | STATO:0000149 | Mth01_TTE_KaplanMeier |
| Cox regression | STATO:0000223 | Mth01_TTE_CoxPH |
| Log-rank | STATO:0000148 | Mth01_TTE_LogRank |
| Logistic regression | STATO:0000209 | Mth01_CatVar_LogReg |

**ARS Analysis Reason codes:** PRIMARY, SENSITIVITY, EXPLORATORY

## PART 3: Multiplicity Adjustments

Extract methods for controlling Type I error across multiple endpoints:
- Hochberg, Bonferroni, Holm, graphical approaches
- Gatekeeping procedures, alpha-spending functions
- Testing hierarchies

## PART 4: Sensitivity & Subgroup Analyses

Extract pre-specified sensitivity analyses and subgroup analyses with:
- Which endpoints they apply to
- How they differ from primary analysis
- Subgroup variables and categories

## PART 5: Interim Analyses

Extract interim analysis plan details:
- Number of interim looks
- Information fractions
- Stopping boundaries (efficacy/futility)
- Alpha spending functions (O'Brien-Fleming, Pocock, etc.)

## PART 6: Sample Size & Power

Extract sample size calculations:
- Target N, power, alpha
- Effect size assumptions
- Dropout rate assumptions

## PART 7: Derived Variables & Data Handling

Extract calculation formulas and data handling rules.

Return JSON:
```json
{{
  "analysisPopulations": [
    {{"id": "pop_1", "name": "Full Analysis Set", "label": "FAS", "definition": "All enrolled subjects who received at least one dose", "populationType": "FullAnalysis", "criteria": "Enrolled AND received >=1 dose"}}
  ],
  "statisticalMethods": [
    {{
      "id": "sm_1",
      "name": "ANCOVA",
      "description": "Primary efficacy analysis using ANCOVA with treatment as factor and baseline as covariate",
      "endpointName": "Primary Endpoint: Change in Copper Balance",
      "statoCode": "STATO:0000029",
      "statoLabel": "analysis of covariance",
      "hypothesisType": "superiority",
      "testType": "two-sided",
      "alphaLevel": 0.05,
      "covariates": ["baseline value", "stratification factors"],
      "software": "SAS PROC MIXED",
      "arsOperationId": "Mth01_ContVar_Ancova",
      "arsReason": "PRIMARY"
    }}
  ],
  "multiplicityAdjustments": [
    {{
      "id": "mult_1",
      "name": "Hochberg Procedure",
      "description": "Hochberg step-up procedure for multiple secondary endpoints",
      "methodType": "familywise",
      "statoCode": "STATO:0000183",
      "overallAlpha": 0.05,
      "endpointsCovered": ["Secondary Endpoint 1", "Secondary Endpoint 2"],
      "hierarchy": "Primary tested first, then secondary endpoints adjusted"
    }}
  ],
  "sensitivityAnalyses": [
    {{
      "id": "sens_1",
      "name": "Per Protocol Analysis",
      "description": "Primary analysis repeated on PP population",
      "primaryEndpoint": "Primary Endpoint",
      "analysisType": "sensitivity",
      "methodVariation": "Same ANCOVA model on PP population",
      "population": "Per Protocol Set",
      "arsReason": "SENSITIVITY"
    }}
  ],
  "subgroupAnalyses": [
    {{
      "id": "sub_1",
      "name": "Age Subgroup Analysis",
      "description": "Treatment effect by age category",
      "subgroupVariable": "Age",
      "categories": ["<65 years", ">=65 years"],
      "endpoints": ["Primary Endpoint"],
      "interactionTest": true
    }}
  ],
  "interimAnalyses": [
    {{
      "id": "ia_1",
      "name": "Interim Analysis 1",
      "description": "First interim analysis for efficacy",
      "timing": "50% of events observed",
      "informationFraction": 0.5,
      "stoppingRuleEfficacy": "Z > 2.96 (p < 0.003)",
      "stoppingRuleFutility": "Conditional power < 20%",
      "alphaSpent": 0.003,
      "spendingFunction": "O'Brien-Fleming",
      "arsReportingEventType": "INTERIM_1"
    }}
  ],
  "sampleSizeCalculations": [
    {{
      "id": "ss_1",
      "name": "Primary Endpoint Sample Size",
      "description": "Sample size for primary efficacy endpoint",
      "targetSampleSize": 100,
      "power": 0.80,
      "alpha": 0.05,
      "effectSize": "Mean difference of 5 units",
      "dropoutRate": 0.15,
      "assumptions": "SD=10, two-sided test"
    }}
  ],
  "derivedVariables": [
    {{"id": "dv_1", "name": "Change from Baseline", "formula": "Post-baseline Value - Baseline Value", "unit": "same as original"}}
  ],
  "dataHandlingRules": [
    {{"id": "rule_1", "name": "Missing Data", "rule": "No imputation; available data only"}}
  ],
  "characteristics": [
    {{"id": "char_1", "name": "Age", "description": "Age at baseline", "dataType": "Numeric"}}
  ]
}}
```

**IMPORTANT: Extract ALL elements found in the document. Include STATO codes where method names match the table above.**

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
            extractor_name="sap",
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
                name=(p.get('name') or p.get('label') or f'Population {i+1}') if isinstance(p, dict) else str(p),
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
        
        # Parse derived variables
        dv_list = raw_data.get('derivedVariables', [])
        if not isinstance(dv_list, list):
            dv_list = []
        
        derived_variables = [
            DerivedVariable(
                id=d.get('id', f"dv_{i+1}") if isinstance(d, dict) else f"dv_{i+1}",
                name=d.get('name', '') if isinstance(d, dict) else str(d),
                formula=d.get('formula', '') if isinstance(d, dict) else '',
                unit=d.get('unit') if isinstance(d, dict) else None,
                notes=d.get('notes') if isinstance(d, dict) else None,
            )
            for i, d in enumerate(dv_list)
        ]
        
        # Parse data handling rules
        rule_list = raw_data.get('dataHandlingRules', [])
        if not isinstance(rule_list, list):
            rule_list = []
        
        data_handling_rules = [
            DataHandlingRule(
                id=r.get('id', f"rule_{i+1}") if isinstance(r, dict) else f"rule_{i+1}",
                name=r.get('name', '') if isinstance(r, dict) else str(r),
                rule=r.get('rule', '') if isinstance(r, dict) else '',
            )
            for i, r in enumerate(rule_list)
        ]
        
        # Parse statistical methods
        sm_list = raw_data.get('statisticalMethods', [])
        if not isinstance(sm_list, list):
            sm_list = []
        
        statistical_methods = [
            StatisticalMethod(
                id=s.get('id', f"sm_{i+1}") if isinstance(s, dict) else f"sm_{i+1}",
                name=s.get('name', '') if isinstance(s, dict) else str(s),
                description=s.get('description', '') if isinstance(s, dict) else '',
                endpoint_name=s.get('endpointName') if isinstance(s, dict) else None,
                stato_code=s.get('statoCode') if isinstance(s, dict) else None,
                stato_label=s.get('statoLabel') if isinstance(s, dict) else None,
                hypothesis_type=s.get('hypothesisType') if isinstance(s, dict) else None,
                test_type=s.get('testType') if isinstance(s, dict) else None,
                alpha_level=s.get('alphaLevel') if isinstance(s, dict) else None,
                covariates=s.get('covariates') if isinstance(s, dict) else None,
                software=s.get('software') if isinstance(s, dict) else None,
                # ARS linkage fields
                ars_method_id=s.get('arsMethodId') if isinstance(s, dict) else None,
                ars_operation_id=s.get('arsOperationId') if isinstance(s, dict) else None,
                ars_reason=s.get('arsReason') if isinstance(s, dict) else None,
            )
            for i, s in enumerate(sm_list)
        ]
        
        # Parse multiplicity adjustments
        mult_list = raw_data.get('multiplicityAdjustments', [])
        if not isinstance(mult_list, list):
            mult_list = []
        
        multiplicity_adjustments = [
            MultiplicityAdjustment(
                id=m.get('id', f"mult_{i+1}") if isinstance(m, dict) else f"mult_{i+1}",
                name=m.get('name', '') if isinstance(m, dict) else str(m),
                description=m.get('description', '') if isinstance(m, dict) else '',
                method_type=m.get('methodType', 'familywise') if isinstance(m, dict) else 'familywise',
                stato_code=m.get('statoCode') if isinstance(m, dict) else None,
                overall_alpha=m.get('overallAlpha') if isinstance(m, dict) else None,
                endpoints_covered=m.get('endpointsCovered') if isinstance(m, dict) else None,
                hierarchy=m.get('hierarchy') if isinstance(m, dict) else None,
            )
            for i, m in enumerate(mult_list)
        ]
        
        # Parse sensitivity analyses
        sens_list = raw_data.get('sensitivityAnalyses', [])
        if not isinstance(sens_list, list):
            sens_list = []
        
        sensitivity_analyses = [
            SensitivityAnalysis(
                id=s.get('id', f"sens_{i+1}") if isinstance(s, dict) else f"sens_{i+1}",
                name=s.get('name', '') if isinstance(s, dict) else str(s),
                description=s.get('description', '') if isinstance(s, dict) else '',
                primary_endpoint=s.get('primaryEndpoint') if isinstance(s, dict) else None,
                analysis_type=s.get('analysisType', 'sensitivity') if isinstance(s, dict) else 'sensitivity',
                method_variation=s.get('methodVariation') if isinstance(s, dict) else None,
                population=s.get('population') if isinstance(s, dict) else None,
                # ARS linkage fields
                ars_reason=s.get('arsReason') if isinstance(s, dict) else None,
                ars_analysis_id=s.get('arsAnalysisId') if isinstance(s, dict) else None,
            )
            for i, s in enumerate(sens_list)
        ]
        
        # Parse subgroup analyses
        sub_list = raw_data.get('subgroupAnalyses', [])
        if not isinstance(sub_list, list):
            sub_list = []
        
        subgroup_analyses = [
            SubgroupAnalysis(
                id=s.get('id', f"sub_{i+1}") if isinstance(s, dict) else f"sub_{i+1}",
                name=s.get('name', '') if isinstance(s, dict) else str(s),
                description=s.get('description', '') if isinstance(s, dict) else '',
                subgroup_variable=s.get('subgroupVariable', '') if isinstance(s, dict) else '',
                categories=s.get('categories') if isinstance(s, dict) else None,
                endpoints=s.get('endpoints') if isinstance(s, dict) else None,
                interaction_test=s.get('interactionTest', False) if isinstance(s, dict) else False,
            )
            for i, s in enumerate(sub_list)
        ]
        
        # Parse interim analyses
        ia_list = raw_data.get('interimAnalyses', [])
        if not isinstance(ia_list, list):
            ia_list = []
        
        interim_analyses = [
            InterimAnalysis(
                id=ia.get('id', f"ia_{i+1}") if isinstance(ia, dict) else f"ia_{i+1}",
                name=ia.get('name', '') if isinstance(ia, dict) else str(ia),
                description=ia.get('description', '') if isinstance(ia, dict) else '',
                timing=ia.get('timing') if isinstance(ia, dict) else None,
                information_fraction=ia.get('informationFraction') if isinstance(ia, dict) else None,
                stopping_rule_efficacy=ia.get('stoppingRuleEfficacy') if isinstance(ia, dict) else None,
                stopping_rule_futility=ia.get('stoppingRuleFutility') if isinstance(ia, dict) else None,
                alpha_spent=ia.get('alphaSpent') if isinstance(ia, dict) else None,
                spending_function=ia.get('spendingFunction') if isinstance(ia, dict) else None,
                # ARS linkage field
                ars_reporting_event_type=ia.get('arsReportingEventType') if isinstance(ia, dict) else None,
            )
            for i, ia in enumerate(ia_list)
        ]
        
        # Parse sample size calculations
        ss_list = raw_data.get('sampleSizeCalculations', [])
        if not isinstance(ss_list, list):
            ss_list = []
        
        sample_size_calculations = [
            SampleSizeCalculation(
                id=ss.get('id', f"ss_{i+1}") if isinstance(ss, dict) else f"ss_{i+1}",
                name=ss.get('name', '') if isinstance(ss, dict) else str(ss),
                description=ss.get('description', '') if isinstance(ss, dict) else '',
                target_sample_size=ss.get('targetSampleSize') if isinstance(ss, dict) else None,
                power=ss.get('power') if isinstance(ss, dict) else None,
                alpha=ss.get('alpha') if isinstance(ss, dict) else None,
                effect_size=ss.get('effectSize') if isinstance(ss, dict) else None,
                dropout_rate=ss.get('dropoutRate') if isinstance(ss, dict) else None,
                assumptions=ss.get('assumptions') if isinstance(ss, dict) else None,
            )
            for i, ss in enumerate(ss_list)
        ]
        
        data = SAPData(
            analysis_populations=populations,
            characteristics=characteristics,
            derived_variables=derived_variables,
            data_handling_rules=data_handling_rules,
            statistical_methods=statistical_methods,
            multiplicity_adjustments=multiplicity_adjustments,
            sensitivity_analyses=sensitivity_analyses,
            subgroup_analyses=subgroup_analyses,
            interim_analyses=interim_analyses,
            sample_size_calculations=sample_size_calculations,
        )
        
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
        
        logger.info(f"Extracted {len(populations)} populations, {len(characteristics)} characteristics, "
                    f"{len(derived_variables)} derived variables, {len(data_handling_rules)} data handling rules, "
                    f"{len(statistical_methods)} statistical methods, {len(multiplicity_adjustments)} multiplicity adjustments, "
                    f"{len(sensitivity_analyses)} sensitivity analyses, {len(subgroup_analyses)} subgroup analyses, "
                    f"{len(interim_analyses)} interim analyses, {len(sample_size_calculations)} sample size calculations from SAP")
        return result
        
    except Exception as e:
        logger.error(f"SAP extraction failed: {e}")
        return SAPExtractionResult(
            success=False,
            error=str(e),
            source_file=sap_path,
            model_used=model,
        )

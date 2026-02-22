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
class MissingDataStrategy:
    """Missing data handling approach per ICH E9(R1) alignment.
    
    Bridges estimand ICE handling strategies to statistical missing data methods.
    Each strategy specifies how missing data is handled for a specific endpoint
    and how it aligns with the estimand framework.
    
    ICE Strategy → Missing Data Method mapping:
      Treatment Policy → Include all data (MMRM, MI)
      Hypothetical     → Estimate as if no discontinuation (MMRM under MAR)
      Composite        → Composite endpoint (no imputation needed)
      While on Treatment → Censor at discontinuation
      Principal Stratum → Model-based (causal inference)
    """
    id: str
    name: str                                    # e.g., "MMRM for primary endpoint"
    method: str                                  # MMRM, LOCF, MI, tipping point, etc.
    endpoint_name: Optional[str] = None          # Which endpoint
    endpoint_id: Optional[str] = None            # USDM Endpoint reference
    estimand_alignment: Optional[str] = None     # Which ICE strategy this supports
    assumptions: Optional[str] = None            # MAR, MNAR, etc.
    sensitivity_method: Optional[str] = None     # Sensitivity analysis for this strategy
    description: Optional[str] = None            # Full description from SAP
    instance_type: str = "MissingDataStrategy"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "method": self.method,
            "instanceType": self.instance_type,
        }
        if self.endpoint_name:
            result["endpointName"] = self.endpoint_name
        if self.endpoint_id:
            result["endpointId"] = self.endpoint_id
        if self.estimand_alignment:
            result["estimandAlignment"] = self.estimand_alignment
        if self.assumptions:
            result["assumptions"] = self.assumptions
        if self.sensitivity_method:
            result["sensitivityMethod"] = self.sensitivity_method
        if self.description:
            result["description"] = self.description
        return result


# ICE Strategy → Missing Data Method standard mapping
ICE_MISSING_DATA_MAP = {
    "treatment policy": ["MMRM", "MI", "mixed model"],
    "hypothetical": ["MMRM under MAR", "MI under MAR", "BOCF"],
    "composite": [],  # No imputation needed
    "while on treatment": ["censor", "LOCF", "truncation"],
    "principal stratum": ["causal inference", "principal stratum"],
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
class AnalysisSpecification:
    """Traceability entity linking an endpoint to its analysis method, population, and estimand.
    
    This is the core entity that connects the clinical question (endpoint/estimand)
    to the statistical answer (method/population/missing data strategy).
    Built during post-processing by reconciling SAP methods with protocol endpoints.
    """
    id: str
    endpoint_id: Optional[str] = None       # USDM Endpoint reference
    endpoint_name: Optional[str] = None     # Endpoint text (for display)
    method_id: Optional[str] = None         # StatisticalMethod reference
    method_name: Optional[str] = None       # Method name (for display)
    population_id: Optional[str] = None     # AnalysisPopulation reference
    population_name: Optional[str] = None   # Population name (for display)
    estimand_id: Optional[str] = None       # Estimand reference (confirmatory only)
    analysis_type: str = "primary"           # primary, secondary, sensitivity, exploratory
    missing_data_strategy: Optional[str] = None  # How missing data is handled
    model_specification: Optional[str] = None    # Full model spec text
    instance_type: str = "AnalysisSpecification"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "analysisType": self.analysis_type,
            "instanceType": self.instance_type,
        }
        if self.endpoint_id:
            result["endpointId"] = self.endpoint_id
        if self.endpoint_name:
            result["endpointName"] = self.endpoint_name
        if self.method_id:
            result["methodId"] = self.method_id
        if self.method_name:
            result["methodName"] = self.method_name
        if self.population_id:
            result["populationId"] = self.population_id
        if self.population_name:
            result["populationName"] = self.population_name
        if self.estimand_id:
            result["estimandId"] = self.estimand_id
        if self.missing_data_strategy:
            result["missingDataStrategy"] = self.missing_data_strategy
        if self.model_specification:
            result["modelSpecification"] = self.model_specification
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
    analysis_specifications: List[AnalysisSpecification] = field(default_factory=list)
    missing_data_strategies: List[MissingDataStrategy] = field(default_factory=list)
    
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
            "analysisSpecifications": [a.to_dict() for a in self.analysis_specifications],
            "missingDataStrategies": [m.to_dict() for m in self.missing_data_strategies],
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
                "analysisSpecificationCount": len(self.analysis_specifications),
                "missingDataStrategyCount": len(self.missing_data_strategies),
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


# =============================================================================
# Multi-pass extraction helpers
# =============================================================================

MAX_SAP_PAGES = 100  # Phase E: increased from 40 to handle large SAPs
MAX_PROMPT_CHARS = 50000  # Per-pass character limit (smaller per pass = better focus)


def _call_sap_pass(
    prompt: str,
    model: str,
    pass_name: str,
    max_retries: int = 2,
) -> Optional[Dict[str, Any]]:
    """Call LLM for a single SAP extraction pass with retry and JSON parsing."""
    for attempt in range(max_retries + 1):
        try:
            result = call_llm(
                prompt=prompt,
                model_name=model,
                json_mode=True,
                extractor_name=f"sap_{pass_name}",
                temperature=0.1,
            )
            response = result.get('response', '')
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            json_str = json_match.group(1) if json_match else response
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data
            logger.warning(f"SAP {pass_name}: LLM returned non-dict, retrying")
        except (json.JSONDecodeError, Exception) as e:
            if attempt < max_retries:
                logger.warning(f"SAP {pass_name} attempt {attempt+1} failed: {e}, retrying")
            else:
                logger.error(f"SAP {pass_name} failed after {max_retries+1} attempts: {e}")
    return None


def _build_context_summary(label: str, items: list, fields: List[str]) -> str:
    """Build a concise context summary of previously extracted items for cross-referencing."""
    if not items:
        return f"{label}: None extracted\n"
    lines = [f"{label} ({len(items)} items):"]
    for item in items[:20]:  # Cap to avoid context overflow
        parts = []
        for f in fields:
            val = item.get(f, '') if isinstance(item, dict) else getattr(item, f, '')
            if val:
                parts.append(f"{f}={val}")
        lines.append(f"  - {', '.join(parts)}")
    return '\n'.join(lines) + '\n'


def _safe_list(data: Optional[Dict], key: str) -> list:
    """Safely extract a list from a dict, returning [] if missing or wrong type."""
    if not data:
        return []
    val = data.get(key, [])
    return val if isinstance(val, list) else []


# =============================================================================
# Entity parsers (shared between single-pass and multi-pass)
# =============================================================================

def _parse_populations(pop_list: list) -> List[AnalysisPopulation]:
    return [
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


def _parse_characteristics(char_list: list) -> List[Characteristic]:
    return [
        Characteristic(
            id=c.get('id', f"char_{i+1}") if isinstance(c, dict) else f"char_{i+1}",
            name=c.get('name', '') if isinstance(c, dict) else str(c),
            description=c.get('description') if isinstance(c, dict) else None,
            data_type=c.get('dataType', 'Text') if isinstance(c, dict) else 'Text',
        )
        for i, c in enumerate(char_list)
    ]


def _parse_sample_size(ss_list: list) -> List[SampleSizeCalculation]:
    return [
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


def _parse_statistical_methods(sm_list: list) -> List[StatisticalMethod]:
    return [
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
            ars_method_id=s.get('arsMethodId') if isinstance(s, dict) else None,
            ars_operation_id=s.get('arsOperationId') if isinstance(s, dict) else None,
            ars_reason=s.get('arsReason') if isinstance(s, dict) else None,
        )
        for i, s in enumerate(sm_list)
    ]


def _parse_multiplicity(mult_list: list) -> List[MultiplicityAdjustment]:
    return [
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


def _parse_sensitivity(sens_list: list) -> List[SensitivityAnalysis]:
    return [
        SensitivityAnalysis(
            id=s.get('id', f"sens_{i+1}") if isinstance(s, dict) else f"sens_{i+1}",
            name=s.get('name', '') if isinstance(s, dict) else str(s),
            description=s.get('description', '') if isinstance(s, dict) else '',
            primary_endpoint=s.get('primaryEndpoint') if isinstance(s, dict) else None,
            analysis_type=s.get('analysisType', 'sensitivity') if isinstance(s, dict) else 'sensitivity',
            method_variation=s.get('methodVariation') if isinstance(s, dict) else None,
            population=s.get('population') if isinstance(s, dict) else None,
            ars_reason=s.get('arsReason') if isinstance(s, dict) else None,
            ars_analysis_id=s.get('arsAnalysisId') if isinstance(s, dict) else None,
        )
        for i, s in enumerate(sens_list)
    ]


def _parse_subgroups(sub_list: list) -> List[SubgroupAnalysis]:
    return [
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


def _parse_interim(ia_list: list) -> List[InterimAnalysis]:
    return [
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
            ars_reporting_event_type=ia.get('arsReportingEventType') if isinstance(ia, dict) else None,
        )
        for i, ia in enumerate(ia_list)
    ]


def _parse_derived_variables(dv_list: list) -> List[DerivedVariable]:
    return [
        DerivedVariable(
            id=d.get('id', f"dv_{i+1}") if isinstance(d, dict) else f"dv_{i+1}",
            name=d.get('name', '') if isinstance(d, dict) else str(d),
            formula=d.get('formula', '') if isinstance(d, dict) else '',
            unit=d.get('unit') if isinstance(d, dict) else None,
            notes=d.get('notes') if isinstance(d, dict) else None,
        )
        for i, d in enumerate(dv_list)
    ]


def _parse_data_handling(rule_list: list) -> List[DataHandlingRule]:
    return [
        DataHandlingRule(
            id=r.get('id', f"rule_{i+1}") if isinstance(r, dict) else f"rule_{i+1}",
            name=r.get('name', '') if isinstance(r, dict) else str(r),
            rule=r.get('rule', '') if isinstance(r, dict) else '',
        )
        for i, r in enumerate(rule_list)
    ]


# =============================================================================
# Main extraction function (multi-pass)
# =============================================================================

def extract_from_sap(
    sap_path: str,
    model: str = "gemini-2.5-pro",
    output_dir: Optional[str] = None,
    endpoints_context: Optional[List[Dict]] = None,
    analysis_approach: Optional[str] = None,
) -> SAPExtractionResult:
    """
    Extract statistical analysis information from SAP using 4 focused passes.
    
    Multi-pass architecture (each pass receives context from previous passes):
      Pass 1: Populations, sample size, baseline characteristics
      Pass 2: Statistical methods (with endpoint + population context)
      Pass 3: Sensitivity, subgroup, interim analyses (with method context)
           — skipped for descriptive studies
      Pass 4: Derived variables, data handling rules
    
    Args:
        sap_path: Path to SAP PDF file
        model: LLM model name
        output_dir: Optional directory for output JSON
        endpoints_context: Optional list of endpoint dicts from protocol extraction
            for cross-referencing in Pass 2
        analysis_approach: Optional 'confirmatory', 'descriptive', or 'unknown'
            from objectives phase. Gates Pass 3 extraction.
    """
    from .sap_prompts import (
        SAP_PASS1_PROMPT, SAP_PASS2_PROMPT, SAP_PASS3_PROMPT, SAP_PASS4_PROMPT,
    )
    
    logger.info(f"Extracting from SAP (multi-pass): {sap_path}")
    
    if not Path(sap_path).exists():
        return SAPExtractionResult(
            success=False,
            error=f"SAP file not found: {sap_path}",
            source_file=sap_path,
        )
    
    # Phase E: Extract up to MAX_SAP_PAGES (100) for large SAPs
    try:
        total_pages = get_page_count(sap_path)
        pages = list(range(min(MAX_SAP_PAGES, total_pages)))
        text = extract_text_from_pages(sap_path, pages)
        logger.info(f"SAP: {total_pages} pages, extracted {len(pages)} pages, {len(text)} chars")
    except Exception as e:
        return SAPExtractionResult(
            success=False,
            error=f"Failed to read SAP: {e}",
            source_file=sap_path,
        )
    
    # Truncate text per pass to stay within context limits
    sap_text = text[:MAX_PROMPT_CHARS]
    
    try:
        # =================================================================
        # PASS 1: Populations + Sample Size + Characteristics
        # =================================================================
        logger.info("SAP Pass 1/4: Populations, sample size, characteristics...")
        pass1_prompt = SAP_PASS1_PROMPT.format(sap_text=sap_text)
        pass1_data = _call_sap_pass(pass1_prompt, model, "pass1")
        
        populations = _parse_populations(_safe_list(pass1_data, 'analysisPopulations'))
        characteristics = _parse_characteristics(_safe_list(pass1_data, 'characteristics'))
        sample_size_calculations = _parse_sample_size(_safe_list(pass1_data, 'sampleSizeCalculations'))
        
        logger.info(
            f"  Pass 1 complete: {len(populations)} populations, "
            f"{len(sample_size_calculations)} sample size calcs, {len(characteristics)} characteristics"
        )
        
        # Build Pass 1 context for subsequent passes
        pass1_pop_dicts = [p.to_dict() for p in populations]
        pass1_context = _build_context_summary(
            "Analysis Populations", pass1_pop_dicts,
            ['id', 'name', 'populationType'],
        )
        pass1_context += _build_context_summary(
            "Sample Size",
            [s.to_dict() for s in sample_size_calculations],
            ['id', 'name', 'targetSampleSize', 'power', 'alpha'],
        )
        
        # =================================================================
        # PASS 2: Statistical Methods + Multiplicity (with endpoint context)
        # =================================================================
        logger.info("SAP Pass 2/4: Statistical methods with endpoint context...")
        
        ep_context_str = "No endpoint context available from protocol."
        if endpoints_context:
            ep_lines = ["Endpoints from protocol:"]
            for ep in endpoints_context[:20]:
                ep_id = ep.get('id', '')
                ep_text = ep.get('endpointText', ep.get('text', ep.get('name', '')))
                ep_level = ep.get('level', ep.get('endpointLevel', ''))
                if isinstance(ep_level, dict):
                    ep_level = ep_level.get('decode', ep_level.get('code', ''))
                ep_lines.append(f"  - id={ep_id}, level={ep_level}, text={ep_text}")
            ep_context_str = '\n'.join(ep_lines)
        
        pass2_prompt = SAP_PASS2_PROMPT.format(
            sap_text=sap_text,
            pass1_context=pass1_context,
            endpoints_context=ep_context_str,
        )
        pass2_data = _call_sap_pass(pass2_prompt, model, "pass2")
        
        statistical_methods = _parse_statistical_methods(_safe_list(pass2_data, 'statisticalMethods'))
        multiplicity_adjustments = _parse_multiplicity(_safe_list(pass2_data, 'multiplicityAdjustments'))
        
        logger.info(
            f"  Pass 2 complete: {len(statistical_methods)} methods, "
            f"{len(multiplicity_adjustments)} multiplicity adjustments"
        )
        
        # Build Pass 2 context for Pass 3
        pass2_method_dicts = [m.to_dict() for m in statistical_methods]
        pass2_context = _build_context_summary(
            "Statistical Methods", pass2_method_dicts,
            ['id', 'name', 'endpointName', 'arsReason'],
        )
        
        # =================================================================
        # PASS 3: Sensitivity + Subgroup + Interim Analyses
        # Gated by analysis approach — descriptive studies skip this pass
        # =================================================================
        is_descriptive = (analysis_approach or '').lower() == 'descriptive'
        sensitivity_analyses = []
        subgroup_analyses = []
        interim_analyses = []
        
        if is_descriptive:
            logger.info(
                "SAP Pass 3/4: SKIPPED — descriptive study "
                "(sensitivity/subgroup/interim analyses not applicable)"
            )
        else:
            logger.info("SAP Pass 3/4: Sensitivity, subgroup, interim analyses...")
            pass3_prompt = SAP_PASS3_PROMPT.format(
                sap_text=sap_text,
                pass1_context=pass1_context,
                pass2_context=pass2_context,
            )
            pass3_data = _call_sap_pass(pass3_prompt, model, "pass3")
            
            sensitivity_analyses = _parse_sensitivity(_safe_list(pass3_data, 'sensitivityAnalyses'))
            subgroup_analyses = _parse_subgroups(_safe_list(pass3_data, 'subgroupAnalyses'))
            interim_analyses = _parse_interim(_safe_list(pass3_data, 'interimAnalyses'))
            
            logger.info(
                f"  Pass 3 complete: {len(sensitivity_analyses)} sensitivity, "
                f"{len(subgroup_analyses)} subgroup, {len(interim_analyses)} interim analyses"
            )
        
        # =================================================================
        # PASS 4: Derived Variables + Data Handling Rules
        # =================================================================
        logger.info("SAP Pass 4/4: Derived variables, data handling rules...")
        pass4_prompt = SAP_PASS4_PROMPT.format(
            sap_text=sap_text,
            endpoints_context=ep_context_str,
        )
        pass4_data = _call_sap_pass(pass4_prompt, model, "pass4")
        
        derived_variables = _parse_derived_variables(_safe_list(pass4_data, 'derivedVariables'))
        data_handling_rules = _parse_data_handling(_safe_list(pass4_data, 'dataHandlingRules'))
        
        logger.info(
            f"  Pass 4 complete: {len(derived_variables)} derived variables, "
            f"{len(data_handling_rules)} data handling rules"
        )
        
        # =================================================================
        # Assemble final result
        # =================================================================
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
        
        total_entities = (
            len(populations) + len(characteristics) + len(statistical_methods)
            + len(multiplicity_adjustments) + len(sensitivity_analyses)
            + len(subgroup_analyses) + len(interim_analyses)
            + len(sample_size_calculations) + len(derived_variables)
            + len(data_handling_rules)
        )
        logger.info(
            f"SAP extraction complete: {total_entities} total entities across 4 passes "
            f"({len(populations)} pops, {len(statistical_methods)} methods, "
            f"{len(sensitivity_analyses)} sensitivity, {len(subgroup_analyses)} subgroup, "
            f"{len(interim_analyses)} interim, {len(sample_size_calculations)} sample size, "
            f"{len(derived_variables)} derived vars, {len(data_handling_rules)} data rules)"
        )
        return result
        
    except Exception as e:
        logger.error(f"SAP extraction failed: {e}")
        return SAPExtractionResult(
            success=False,
            error=str(e),
            source_file=sap_path,
            model_used=model,
        )

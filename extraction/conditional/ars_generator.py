"""
CDISC ARS (Analysis Results Standard) Generator

Converts SAP extraction data to CDISC ARS-compliant JSON format.
Based on ARS v1.0 specification: https://github.com/cdisc-org/analysis-results-standard

Key ARS Entities:
- ReportingEvent: Top-level container (CSR, Interim Analysis)
- Analysis: Individual analysis specification  
- AnalysisSet: Population definition (maps to USDM AnalysisPopulation)
- AnalysisMethod: Statistical method with operations
- Operation: Specific statistical operation (e.g., count, mean, p-value)
- AnalysisCategorization: Category groupings for organizing analyses
"""

import uuid
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# ARS Model Dataclasses
# =============================================================================

@dataclass
class ExtensibleTerminologyTerm:
    """ARS terminology term with controlled vocabulary."""
    id: str
    value: str
    controlledTerm: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "value": self.value}
        if self.controlledTerm:
            result["controlledTerm"] = self.controlledTerm
        return result


@dataclass
class SponsorTerm:
    """Sponsor-defined terminology term."""
    id: str
    value: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "value": self.value}


@dataclass 
class ReferencedOperationRelationship:
    """Relationship to another operation."""
    id: str
    referencedOperationRole: ExtensibleTerminologyTerm
    operationId: str
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "referencedOperationRole": self.referencedOperationRole.to_dict(),
            "operationId": self.operationId,
        }
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class Operation:
    """
    ARS Operation - A statistical operation performed as part of an analysis method.
    Examples: count, mean, median, standard deviation, p-value, confidence interval
    """
    id: str
    name: str
    label: Optional[str] = None
    order: int = 1
    resultPattern: Optional[str] = None  # Regex pattern for result format
    referencedOperationRelationships: List[ReferencedOperationRelationship] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "order": self.order,
        }
        if self.label:
            result["label"] = self.label
        if self.resultPattern:
            result["resultPattern"] = self.resultPattern
        if self.referencedOperationRelationships:
            result["referencedOperationRelationships"] = [
                r.to_dict() for r in self.referencedOperationRelationships
            ]
        return result


@dataclass
class AnalysisMethod:
    """
    ARS AnalysisMethod - A set of operations that define how an analysis is performed.
    Maps to SAP StatisticalMethod with STATO code.
    """
    id: str
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    operations: List[Operation] = field(default_factory=list)
    # Extensions for STATO mapping
    statoCode: Optional[str] = None
    statoLabel: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.operations:
            result["operations"] = [op.to_dict() for op in self.operations]
        # Include STATO as extension
        if self.statoCode or self.statoLabel:
            result["_statoMapping"] = {}
            if self.statoCode:
                result["_statoMapping"]["code"] = self.statoCode
            if self.statoLabel:
                result["_statoMapping"]["label"] = self.statoLabel
        return result


@dataclass
class AnalysisSet:
    """
    ARS AnalysisSet - A set of subjects whose data are to be included in an analysis.
    Maps to USDM AnalysisPopulation and SAP populations.
    """
    id: str
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    level: int = 1
    order: int = 1
    condition: Optional[str] = None  # Logical condition defining the set
    # Link to USDM
    usdmPopulationId: Optional[str] = None
    usdmPopulationType: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "order": self.order,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.condition:
            result["condition"] = {"value": self.condition}
        # Include USDM linkage as extension
        if self.usdmPopulationId or self.usdmPopulationType:
            result["_usdmLinkage"] = {}
            if self.usdmPopulationId:
                result["_usdmLinkage"]["populationId"] = self.usdmPopulationId
            if self.usdmPopulationType:
                result["_usdmLinkage"]["populationType"] = self.usdmPopulationType
        return result


@dataclass
class AnalysisCategory:
    """ARS AnalysisCategory - A category within an analysis categorization."""
    id: str
    label: str
    order: int = 1
    subCategorizations: List['AnalysisCategorization'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "label": self.label,
            "order": self.order,
        }
        if self.subCategorizations:
            result["subCategorizations"] = [c.to_dict() for c in self.subCategorizations]
        return result


@dataclass
class AnalysisCategorization:
    """
    ARS AnalysisCategorization - A set of related categories used to organize analyses.
    Examples: By Endpoint, By Analysis Type (Primary/Secondary/Exploratory)
    """
    id: str
    label: str
    categories: List[AnalysisCategory] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "label": self.label,
        }
        if self.categories:
            result["categories"] = [c.to_dict() for c in self.categories]
        return result


@dataclass
class OrderedSubSection:
    """Ordered subsection reference."""
    id: str
    order: int
    subSectionId: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "order": self.order,
            "subSectionId": self.subSectionId,
        }


@dataclass
class Analysis:
    """
    ARS Analysis - A specification of a statistical analysis.
    This is the core entity linking methods, populations, and outputs.
    """
    id: str
    name: str
    version: int = 1
    description: Optional[str] = None
    reason: Optional[ExtensibleTerminologyTerm] = None  # PRIMARY, SENSITIVITY, EXPLORATORY
    purpose: Optional[ExtensibleTerminologyTerm] = None  # EFFICACY, SAFETY, PK, etc.
    methodId: Optional[str] = None  # Reference to AnalysisMethod
    analysisSetId: Optional[str] = None  # Reference to AnalysisSet (population)
    categoryIds: List[str] = field(default_factory=list)  # References to AnalysisCategory
    orderedSubSections: List[OrderedSubSection] = field(default_factory=list)
    # Extensions for SAP linkage
    sapEndpointName: Optional[str] = None
    hypothesisType: Optional[str] = None  # superiority, non-inferiority, equivalence
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }
        if self.description:
            result["description"] = self.description
        if self.reason:
            result["reason"] = self.reason.to_dict()
        if self.purpose:
            result["purpose"] = self.purpose.to_dict()
        if self.methodId:
            result["methodId"] = self.methodId
        if self.analysisSetId:
            result["analysisSetId"] = self.analysisSetId
        if self.categoryIds:
            result["categoryIds"] = self.categoryIds
        if self.orderedSubSections:
            result["orderedSubSections"] = [s.to_dict() for s in self.orderedSubSections]
        # SAP extensions
        if self.sapEndpointName or self.hypothesisType:
            result["_sapLinkage"] = {}
            if self.sapEndpointName:
                result["_sapLinkage"]["endpointName"] = self.sapEndpointName
            if self.hypothesisType:
                result["_sapLinkage"]["hypothesisType"] = self.hypothesisType
        return result


@dataclass
class ReportingEvent:
    """
    ARS ReportingEvent - The top-level container for analyses.
    Represents a reporting milestone like CSR, Interim Analysis, DSMB report.
    """
    id: str
    name: str
    version: int = 1
    description: Optional[str] = None
    # Contained entities
    analysisCategorizations: List[AnalysisCategorization] = field(default_factory=list)
    analysisSets: List[AnalysisSet] = field(default_factory=list)
    analysisMethods: List[AnalysisMethod] = field(default_factory=list)
    analyses: List[Analysis] = field(default_factory=list)
    # Metadata
    mainListOfContentsId: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }
        if self.description:
            result["description"] = self.description
        if self.analysisCategorizations:
            result["analysisCategorizations"] = [c.to_dict() for c in self.analysisCategorizations]
        if self.analysisSets:
            result["analysisSets"] = [s.to_dict() for s in self.analysisSets]
        if self.analysisMethods:
            result["analysisMethods"] = [m.to_dict() for m in self.analysisMethods]
        if self.analyses:
            result["analyses"] = [a.to_dict() for a in self.analyses]
        if self.mainListOfContentsId:
            result["mainListOfContentsId"] = self.mainListOfContentsId
        return result


# =============================================================================
# ARS Operation Patterns
# =============================================================================

# Standard ARS operation patterns for common statistical methods
ARS_OPERATION_PATTERNS = {
    "ANCOVA": [
        Operation(id="op_lsmean", name="Mth01_LsMean", label="LS Mean", order=1, resultPattern="XX.XX"),
        Operation(id="op_lsmean_se", name="Mth01_LsMean_SE", label="LS Mean SE", order=2, resultPattern="XX.XX"),
        Operation(id="op_diff", name="Mth01_Diff", label="LS Mean Difference", order=3, resultPattern="XX.XX"),
        Operation(id="op_diff_ci", name="Mth01_Diff_CI", label="95% CI for Difference", order=4, resultPattern="(XX.XX, XX.XX)"),
        Operation(id="op_pvalue", name="Mth01_PValue", label="P-value", order=5, resultPattern="X.XXXX"),
    ],
    "MMRM": [
        Operation(id="op_lsmean", name="Mth01_MMRM_LsMean", label="LS Mean", order=1, resultPattern="XX.XX"),
        Operation(id="op_lsmean_se", name="Mth01_MMRM_SE", label="Standard Error", order=2, resultPattern="XX.XX"),
        Operation(id="op_diff", name="Mth01_MMRM_Diff", label="Treatment Difference", order=3, resultPattern="XX.XX"),
        Operation(id="op_ci", name="Mth01_MMRM_CI", label="95% CI", order=4, resultPattern="(XX.XX, XX.XX)"),
        Operation(id="op_pvalue", name="Mth01_MMRM_PValue", label="P-value", order=5, resultPattern="X.XXXX"),
    ],
    "t-test": [
        Operation(id="op_mean", name="Mth01_Mean", label="Mean", order=1, resultPattern="XX.XX"),
        Operation(id="op_sd", name="Mth01_SD", label="Standard Deviation", order=2, resultPattern="XX.XX"),
        Operation(id="op_diff", name="Mth01_MeanDiff", label="Mean Difference", order=3, resultPattern="XX.XX"),
        Operation(id="op_pvalue", name="Mth01_TTest_PValue", label="P-value", order=4, resultPattern="X.XXXX"),
    ],
    "Chi-square": [
        Operation(id="op_n", name="Mth01_Count", label="n", order=1, resultPattern="XXX"),
        Operation(id="op_pct", name="Mth01_Percent", label="Percentage", order=2, resultPattern="XX.X%"),
        Operation(id="op_chisq", name="Mth01_ChiSq", label="Chi-square statistic", order=3, resultPattern="XX.XX"),
        Operation(id="op_pvalue", name="Mth01_ChiSq_PValue", label="P-value", order=4, resultPattern="X.XXXX"),
    ],
    "Fisher exact": [
        Operation(id="op_n", name="Mth01_Count", label="n", order=1, resultPattern="XXX"),
        Operation(id="op_pct", name="Mth01_Percent", label="Percentage", order=2, resultPattern="XX.X%"),
        Operation(id="op_pvalue", name="Mth01_Fisher_PValue", label="P-value (Fisher)", order=3, resultPattern="X.XXXX"),
    ],
    "Kaplan-Meier": [
        Operation(id="op_median", name="Mth01_KM_Median", label="Median Survival", order=1, resultPattern="XX.X"),
        Operation(id="op_ci", name="Mth01_KM_CI", label="95% CI", order=2, resultPattern="(XX.X, XX.X)"),
        Operation(id="op_rate", name="Mth01_KM_Rate", label="Event Rate", order=3, resultPattern="XX.X%"),
    ],
    "Cox regression": [
        Operation(id="op_hr", name="Mth01_HR", label="Hazard Ratio", order=1, resultPattern="X.XX"),
        Operation(id="op_ci", name="Mth01_HR_CI", label="95% CI for HR", order=2, resultPattern="(X.XX, X.XX)"),
        Operation(id="op_pvalue", name="Mth01_Cox_PValue", label="P-value", order=3, resultPattern="X.XXXX"),
    ],
    "Log-rank": [
        Operation(id="op_chisq", name="Mth01_LogRank_ChiSq", label="Log-rank Chi-square", order=1, resultPattern="XX.XX"),
        Operation(id="op_pvalue", name="Mth01_LogRank_PValue", label="P-value", order=2, resultPattern="X.XXXX"),
    ],
    "Wilcoxon": [
        Operation(id="op_median", name="Mth01_Median", label="Median", order=1, resultPattern="XX.XX"),
        Operation(id="op_iqr", name="Mth01_IQR", label="IQR", order=2, resultPattern="XX.XX"),
        Operation(id="op_pvalue", name="Mth01_Wilcoxon_PValue", label="P-value", order=3, resultPattern="X.XXXX"),
    ],
}

# ARS reason codes
ARS_REASON_CODES = {
    "PRIMARY": ExtensibleTerminologyTerm(id="reason_primary", value="PRIMARY ANALYSIS", controlledTerm="C117746"),
    "SENSITIVITY": ExtensibleTerminologyTerm(id="reason_sensitivity", value="SENSITIVITY ANALYSIS", controlledTerm="C117747"),
    "EXPLORATORY": ExtensibleTerminologyTerm(id="reason_exploratory", value="EXPLORATORY ANALYSIS", controlledTerm="C117748"),
    "SUPPORTIVE": ExtensibleTerminologyTerm(id="reason_supportive", value="SUPPORTIVE ANALYSIS"),
}

# ARS purpose codes
ARS_PURPOSE_CODES = {
    "EFFICACY": ExtensibleTerminologyTerm(id="purpose_efficacy", value="EFFICACY", controlledTerm="C49656"),
    "SAFETY": ExtensibleTerminologyTerm(id="purpose_safety", value="SAFETY", controlledTerm="C49663"),
    "PK": ExtensibleTerminologyTerm(id="purpose_pk", value="PHARMACOKINETIC", controlledTerm="C49664"),
    "PD": ExtensibleTerminologyTerm(id="purpose_pd", value="PHARMACODYNAMIC", controlledTerm="C49665"),
}


# =============================================================================
# ARS Generator
# =============================================================================

class ARSGenerator:
    """
    Generates CDISC ARS-compliant JSON from SAP extraction data.
    """
    
    def __init__(self, sap_data: Dict[str, Any], study_name: str = "Study",
                 endpoint_map: Optional[Dict[str, str]] = None):
        self.sap_data = sap_data
        self.study_name = study_name
        self.endpoint_map: Dict[str, str] = endpoint_map or {}  # name→endpoint_id
        self.reporting_event: Optional[ReportingEvent] = None
        
    def generate(self) -> ReportingEvent:
        """Generate full ARS ReportingEvent from SAP data."""
        
        # Create the main reporting event
        self.reporting_event = ReportingEvent(
            id=f"RE_{str(uuid.uuid4())[:8]}",
            name=f"{self.study_name} - Clinical Study Report",
            description=f"Analysis Results for {self.study_name}",
        )
        
        # Generate analysis sets from populations
        self._generate_analysis_sets()
        
        # Generate analysis methods from statistical methods
        self._generate_analysis_methods()
        
        # Generate categorizations
        self._generate_categorizations()
        
        # Generate analyses
        self._generate_analyses()
        
        return self.reporting_event
    
    def _generate_analysis_sets(self):
        """Convert SAP populations to ARS AnalysisSets."""
        populations = self.sap_data.get('analysisPopulations', [])
        
        for i, pop in enumerate(populations):
            analysis_set = AnalysisSet(
                id=f"AS_{pop.get('id', str(uuid.uuid4())[:8])}",
                name=pop.get('name', f'Population {i+1}'),
                label=pop.get('label'),
                description=pop.get('populationDescription') or pop.get('text'),
                level=1,
                order=i + 1,
                condition=pop.get('criteria'),
                usdmPopulationId=pop.get('id'),
                usdmPopulationType=pop.get('populationType'),
            )
            self.reporting_event.analysisSets.append(analysis_set)
        
        logger.info(f"Generated {len(self.reporting_event.analysisSets)} ARS AnalysisSets")
    
    def _generate_analysis_methods(self):
        """Convert SAP statistical methods to ARS AnalysisMethods."""
        methods = self.sap_data.get('statisticalMethods', [])
        
        for i, method in enumerate(methods):
            method_name = method.get('name', '')
            
            # Get operations based on method type
            operations = self._get_operations_for_method(method_name)
            
            analysis_method = AnalysisMethod(
                id=f"AM_{method.get('id', str(uuid.uuid4())[:8])}",
                name=method.get('arsOperationId') or f"Mth{i+1:02d}_{method_name.replace(' ', '_')}",
                label=method_name,
                description=method.get('description'),
                operations=operations,
                statoCode=method.get('statoCode'),
                statoLabel=method.get('statoLabel'),
            )
            self.reporting_event.analysisMethods.append(analysis_method)
        
        logger.info(f"Generated {len(self.reporting_event.analysisMethods)} ARS AnalysisMethods")
    
    def _get_operations_for_method(self, method_name: str) -> List[Operation]:
        """Get standard operations for a statistical method."""
        # Normalize method name
        method_key = method_name.upper().replace(" ", "").replace("-", "")
        
        for key, ops in ARS_OPERATION_PATTERNS.items():
            if key.upper().replace(" ", "").replace("-", "") in method_key or \
               method_key in key.upper().replace(" ", "").replace("-", ""):
                # Clone operations with new IDs
                return [
                    Operation(
                        id=f"{op.id}_{str(uuid.uuid4())[:4]}",
                        name=op.name,
                        label=op.label,
                        order=op.order,
                        resultPattern=op.resultPattern,
                    )
                    for op in ops
                ]
        
        # Default operation for unknown/unmatched methods — only a generic result.
        # P-value is NOT assumed: descriptive methods don't produce p-values.
        # Inferential tests (ANCOVA, t-test, etc.) get p-values via ARS_OPERATION_PATTERNS.
        return [
            Operation(id=f"op_result_{str(uuid.uuid4())[:4]}", name="Result", label="Analysis Result", order=1),
        ]
    
    def _generate_categorizations(self):
        """Generate analysis categorizations."""
        # Create categorization by analysis reason
        reason_categorization = AnalysisCategorization(
            id="AC_ByReason",
            label="Analyses by Reason",
            categories=[
                AnalysisCategory(id="AC_Primary", label="Primary Analyses", order=1),
                AnalysisCategory(id="AC_Sensitivity", label="Sensitivity Analyses", order=2),
                AnalysisCategory(id="AC_Exploratory", label="Exploratory Analyses", order=3),
            ]
        )
        self.reporting_event.analysisCategorizations.append(reason_categorization)
        
        # Create categorization by endpoint if we have methods with endpoints
        methods = self.sap_data.get('statisticalMethods', [])
        endpoints = set()
        for method in methods:
            if method.get('endpointName'):
                endpoints.add(method.get('endpointName'))
        
        if endpoints:
            endpoint_categories = [
                AnalysisCategory(
                    id=f"AC_Endpoint_{i+1}",
                    label=endpoint,
                    order=i+1
                )
                for i, endpoint in enumerate(sorted(endpoints))
            ]
            endpoint_categorization = AnalysisCategorization(
                id="AC_ByEndpoint",
                label="Analyses by Endpoint",
                categories=endpoint_categories,
            )
            self.reporting_event.analysisCategorizations.append(endpoint_categorization)
        
        logger.info(f"Generated {len(self.reporting_event.analysisCategorizations)} ARS Categorizations")
    
    def _generate_analyses(self):
        """Generate Analysis objects from SAP data."""
        methods = self.sap_data.get('statisticalMethods', [])
        sensitivity = self.sap_data.get('sensitivityAnalyses', [])
        subgroups = self.sap_data.get('subgroupAnalyses', [])
        
        # Map analysis sets by population type for linking
        set_by_type = {
            s.usdmPopulationType: s.id 
            for s in self.reporting_event.analysisSets 
            if s.usdmPopulationType
        }
        
        # Map methods by name for linking
        method_by_name = {
            m.label.upper(): m.id 
            for m in self.reporting_event.analysisMethods 
            if m.label
        }
        
        analysis_count = 0
        
        # Create analyses from statistical methods
        for method in methods:
            reason_code = method.get('arsReason', 'PRIMARY').upper()
            reason = ARS_REASON_CODES.get(reason_code, ARS_REASON_CODES['PRIMARY'])
            
            # Determine analysis set (default to FullAnalysis/FAS)
            analysis_set_id = set_by_type.get('FullAnalysis') or \
                             (self.reporting_event.analysisSets[0].id if self.reporting_event.analysisSets else None)
            
            # Get method ID
            method_name = method.get('name', '').upper()
            method_id = method_by_name.get(method_name)
            if not method_id and self.reporting_event.analysisMethods:
                method_id = self.reporting_event.analysisMethods[0].id
            
            analysis = Analysis(
                id=f"AN_{str(uuid.uuid4())[:8]}",
                name=method.get('endpointName') or f"Analysis using {method.get('name')}",
                description=method.get('description'),
                reason=reason,
                purpose=ARS_PURPOSE_CODES.get('EFFICACY'),
                methodId=method_id,
                analysisSetId=analysis_set_id,
                categoryIds=["AC_Primary"] if reason_code == "PRIMARY" else ["AC_Sensitivity"],
                sapEndpointName=method.get('endpointName'),
                hypothesisType=method.get('hypothesisType'),
            )
            self.reporting_event.analyses.append(analysis)
            analysis_count += 1
        
        # Create analyses from sensitivity analyses
        for sens in sensitivity:
            # Find population for this sensitivity analysis
            pop_name = sens.get('population', '')
            analysis_set_id = None
            for aset in self.reporting_event.analysisSets:
                if pop_name and pop_name.lower() in (aset.name or '').lower():
                    analysis_set_id = aset.id
                    break
            if not analysis_set_id and self.reporting_event.analysisSets:
                analysis_set_id = self.reporting_event.analysisSets[0].id
            
            analysis = Analysis(
                id=f"AN_Sens_{str(uuid.uuid4())[:8]}",
                name=sens.get('name', 'Sensitivity Analysis'),
                description=sens.get('description'),
                reason=ARS_REASON_CODES.get(sens.get('arsReason', 'SENSITIVITY').upper(), ARS_REASON_CODES['SENSITIVITY']),
                analysisSetId=analysis_set_id,
                categoryIds=["AC_Sensitivity"],
                sapEndpointName=sens.get('primaryEndpoint'),
            )
            self.reporting_event.analyses.append(analysis)
            analysis_count += 1
        
        # Create analyses from subgroup analyses
        for sub in subgroups:
            analysis = Analysis(
                id=f"AN_Sub_{str(uuid.uuid4())[:8]}",
                name=sub.get('name', 'Subgroup Analysis'),
                description=sub.get('description'),
                reason=ARS_REASON_CODES['EXPLORATORY'],
                categoryIds=["AC_Exploratory"],
            )
            self.reporting_event.analyses.append(analysis)
            analysis_count += 1
        
        logger.info(f"Generated {analysis_count} ARS Analyses")
    
    def to_dict(self) -> Dict[str, Any]:
        """Return ARS as dictionary."""
        if not self.reporting_event:
            self.generate()
        return {"reportingEvent": self.reporting_event.to_dict()}
    
    def to_json(self, indent: int = 2) -> str:
        """Return ARS as JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, output_path: str):
        """Save ARS JSON to file."""
        path = Path(output_path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info(f"Saved ARS output to {path}")


def generate_ars_from_sap(
    sap_data: Dict[str, Any],
    study_name: str = "Study",
    output_path: Optional[str] = None,
    endpoint_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Generate CDISC ARS JSON from SAP extraction data.
    
    Args:
        sap_data: SAP extraction data dictionary
        study_name: Name of the study for the reporting event
        output_path: Optional path to save ARS JSON
        endpoint_map: Optional {endpoint_name_lower: usdm_endpoint_id} for linkage
        
    Returns:
        ARS JSON as dictionary
    """
    generator = ARSGenerator(sap_data, study_name, endpoint_map=endpoint_map)
    result = generator.generate()
    
    if output_path:
        generator.save(output_path)
    
    return generator.to_dict()

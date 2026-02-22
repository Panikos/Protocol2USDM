"""
Multi-pass SAP extraction prompts.

Four focused passes, each receiving context from previous passes:
  Pass 1: Populations, sample size, baseline characteristics (structural)
  Pass 2: Statistical methods linked to specific endpoints
  Pass 3: Sensitivity, subgroup, interim analyses (linked to Pass 2 methods)
  Pass 4: Derived variables, data handling rules
"""

# =============================================================================
# PASS 1: Populations + Sample Size + Characteristics
# =============================================================================

SAP_PASS1_PROMPT = """You are an expert biostatistician extracting analysis populations and sample size information from a Statistical Analysis Plan (SAP).

## Task
Extract ONLY:
1. Analysis populations (with exact definitions from the document)
2. Sample size calculations
3. Baseline characteristics to be summarized

## Analysis Populations

Extract ALL analysis populations defined in this SAP. For each population, extract the **exact definition text** from the document — do NOT use generic boilerplate.

Standard CDISC population types:
| populationType | Common Names |
|----------------|-------------|
| FullAnalysis | Full Analysis Set, FAS, ITT, mITT |
| PerProtocol | Per Protocol Set, PP, Evaluable |
| Safety | Safety Set, Safety Population, SAF |
| Pharmacokinetic | PK Analysis Set, PK Population |
| Pharmacodynamic | PD Analysis Set, PD Population |
| Screened | Screened Set, Screening Population |
| Enrolled | Enrolled Set, Enrollment Population |

## Sample Size

Extract sample size calculations with:
- Target N (per group and total)
- Power and alpha
- Effect size assumptions (with units)
- Dropout rate assumptions
- Key statistical assumptions

## Baseline Characteristics

Extract the list of baseline characteristics that will be summarized (demographics, disease characteristics, etc.).

## Output Format

```json
{{
  "analysisPopulations": [
    {{
      "id": "pop_1",
      "name": "Full Analysis Set",
      "label": "FAS",
      "definition": "[EXACT text from document defining this population]",
      "populationType": "FullAnalysis",
      "criteria": "[Inclusion/exclusion criteria for this population]"
    }}
  ],
  "sampleSizeCalculations": [
    {{
      "id": "ss_1",
      "name": "Primary Endpoint Sample Size",
      "description": "[Full description from document]",
      "targetSampleSize": 100,
      "perGroupN": {{"treatment": 50, "control": 50}},
      "power": 0.80,
      "alpha": 0.05,
      "effectSize": "[Expected effect with units]",
      "dropoutRate": 0.15,
      "assumptions": "[Key assumptions]"
    }}
  ],
  "characteristics": [
    {{"id": "char_1", "name": "Age", "description": "Age at baseline", "dataType": "Numeric"}},
    {{"id": "char_2", "name": "Sex", "description": "Sex", "dataType": "Categorical"}}
  ]
}}
```

## Rules
1. Use EXACT text from the document for population definitions — never generic boilerplate
2. If a population is not defined in this document, do NOT include it
3. Extract ALL populations, not just the primary analysis population
4. Return ONLY valid JSON

SAP TEXT:
{sap_text}
"""


# =============================================================================
# PASS 2: Statistical Methods (with endpoint context)
# =============================================================================

SAP_PASS2_PROMPT = """You are an expert biostatistician extracting statistical analysis methods from a Statistical Analysis Plan (SAP).

## Previously Extracted Context
{pass1_context}

## Study Endpoints (from protocol)
{endpoints_context}

## Task
Extract ALL statistical analysis methods defined in this SAP. For each method, link it to the specific endpoint it analyzes.

## STATO Ontology Mapping
Map methods to STATO codes where possible:

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
| Descriptive statistics | STATO:0000117 | Mth01_Desc_Summary |

## Output Format

```json
{{
  "statisticalMethods": [
    {{
      "id": "sm_1",
      "name": "ANCOVA",
      "description": "[Full description from SAP]",
      "endpointName": "[Exact endpoint name this method analyzes]",
      "endpointId": "[Endpoint ID from protocol if matched, else null]",
      "analysisType": "primary",
      "populationId": "[Population ID from Pass 1 if matched, else null]",
      "populationName": "[Population name this method uses]",
      "statoCode": "STATO:0000029",
      "statoLabel": "analysis of covariance",
      "hypothesisType": "superiority",
      "testType": "two-sided",
      "alphaLevel": 0.05,
      "modelSpecification": {{
        "dependentVariable": "[Variable being analyzed]",
        "factors": ["treatment group"],
        "covariates": ["baseline value", "stratification factors"],
        "randomEffects": [],
        "interactionTerms": []
      }},
      "missingDataMethod": "[How missing data is handled for this analysis]",
      "software": "SAS PROC MIXED",
      "arsOperationId": "Mth01_ContVar_Ancova",
      "arsReason": "PRIMARY"
    }}
  ],
  "multiplicityAdjustments": [
    {{
      "id": "mult_1",
      "name": "Hochberg Procedure",
      "description": "[Description from SAP]",
      "methodType": "familywise",
      "statoCode": "STATO:0000183",
      "overallAlpha": 0.05,
      "endpointsCovered": ["Primary Endpoint", "Secondary Endpoint 1"],
      "hierarchy": "[Testing hierarchy description]"
    }}
  ]
}}
```

## Rules
1. Link each method to the specific endpoint it analyzes (using endpointName AND endpointId if available)
2. Link each method to the analysis population it uses (using populationId from Pass 1)
3. Extract the FULL model specification — covariates, factors, random effects
4. Extract the missing data method for each analysis
5. Classify each method as "primary", "secondary", or "exploratory" analysis
6. Only extract methods that are EXPLICITLY defined in the SAP
7. If the study uses descriptive statistics only, extract those as methods too (use STATO:0000117)
8. Return ONLY valid JSON

SAP TEXT:
{sap_text}
"""


# =============================================================================
# PASS 3: Sensitivity, Subgroup, Interim Analyses
# =============================================================================

SAP_PASS3_PROMPT = """You are an expert biostatistician extracting sensitivity, subgroup, and interim analyses from a Statistical Analysis Plan (SAP).

## Previously Extracted Context
{pass1_context}

{pass2_context}

## Task
Extract:
1. Sensitivity analyses (linked to which primary analysis they support)
2. Subgroup analyses (with variables and categories)
3. Interim analyses (with stopping rules and decision criteria)

## Output Format

```json
{{
  "sensitivityAnalyses": [
    {{
      "id": "sens_1",
      "name": "Per Protocol Analysis",
      "description": "[Description from SAP]",
      "primaryEndpoint": "[Endpoint this sensitivity analysis is for]",
      "primaryMethodId": "[ID of the primary method this is a sensitivity for, from Pass 2]",
      "analysisType": "sensitivity",
      "methodVariation": "[How it differs from primary — e.g., different population, different model]",
      "population": "[Population name]",
      "populationId": "[Population ID from Pass 1]",
      "arsReason": "SENSITIVITY"
    }}
  ],
  "subgroupAnalyses": [
    {{
      "id": "sub_1",
      "name": "Age Subgroup Analysis",
      "description": "[Description from SAP]",
      "subgroupVariable": "Age",
      "categories": ["<65 years", ">=65 years"],
      "endpoints": ["Primary Endpoint"],
      "interactionTest": true,
      "interactionModel": "[Model for interaction test if specified]"
    }}
  ],
  "interimAnalyses": [
    {{
      "id": "ia_1",
      "name": "Interim Analysis 1",
      "description": "[Description from SAP]",
      "timing": "50% of events observed",
      "informationFraction": 0.5,
      "stoppingRuleEfficacy": "[Efficacy boundary]",
      "stoppingRuleFutility": "[Futility boundary]",
      "alphaSpent": 0.003,
      "spendingFunction": "O'Brien-Fleming",
      "decisionCriteria": "[Decision rules]",
      "arsReportingEventType": "INTERIM_1"
    }}
  ]
}}
```

## Rules
1. Link sensitivity analyses to the primary method they are modifying (using primaryMethodId from Pass 2)
2. Link sensitivity analyses to populations from Pass 1 (using populationId)
3. For subgroups, extract the exact categories and whether an interaction test is planned
4. For interim analyses, extract BOTH efficacy and futility boundaries
5. Only extract analyses that are EXPLICITLY defined in the SAP
6. Return ONLY valid JSON

SAP TEXT:
{sap_text}
"""


# =============================================================================
# PASS 4: Derived Variables + Data Handling Rules
# =============================================================================

SAP_PASS4_PROMPT = """You are an expert biostatistician extracting derived variable definitions and data handling rules from a Statistical Analysis Plan (SAP).

## Previously Extracted Context
{endpoints_context}

## Task
Extract:
1. Derived variable calculation formulas (linked to which endpoint they compute)
2. Data handling rules (missing data imputation, BLQ handling, outlier rules)

## Output Format

```json
{{
  "derivedVariables": [
    {{
      "id": "dv_1",
      "name": "Change from Baseline",
      "formula": "Post-baseline Value - Baseline Value",
      "endpointName": "[Endpoint this variable computes]",
      "unit": "[Unit if specified]",
      "notes": "[Additional notes]"
    }}
  ],
  "dataHandlingRules": [
    {{
      "id": "rule_1",
      "name": "Missing Primary Endpoint Data",
      "rule": "[Exact rule from SAP]",
      "scope": "[Which variables/endpoints this applies to]",
      "method": "[LOCF, MMRM, MI, complete case, etc.]"
    }}
  ]
}}
```

## Rules
1. Link derived variables to the endpoint they compute where possible
2. For data handling rules, specify the SCOPE (which variables/endpoints)
3. Extract the specific METHOD for handling missing data (not just "missing data will be handled")
4. Only extract rules that are EXPLICITLY defined in the SAP
5. Return ONLY valid JSON

SAP TEXT:
{sap_text}
"""

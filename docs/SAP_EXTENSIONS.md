# SAP (Statistical Analysis Plan) Extensions Schema

This document defines the structured extension schema for SAP-derived concepts that are stored as USDM `extensionAttributes`. These extensions support downstream systems and STATO ontology mapping.

## Extension Namespace

All Protocol2USDM SAP extensions use the namespace: `https://protocol2usdm.io/extensions/`

## SAP Extraction Overview

The SAP extractor (`extraction/conditional/sap_extractor.py`) extracts the following data types from SAP documents:

| Data Type | USDM Target | Extension URL |
|-----------|-------------|---------------|
| Analysis Populations | `studyDesign.analysisPopulations[]` | Core USDM entity |
| Statistical Methods | Extension on `StudyDesign` | `x-sap-statistical-methods` |
| Multiplicity Adjustments | Extension on `StudyDesign` | `x-sap-multiplicity-adjustments` |
| Sensitivity Analyses | Extension on `StudyDesign` | `x-sap-sensitivity-analyses` |
| Subgroup Analyses | Extension on `StudyDesign` | `x-sap-subgroup-analyses` |
| Interim Analyses | Extension on `StudyDesign` | `x-sap-interim-analyses` |
| Sample Size Calculations | Extension on `StudyDesign` | `x-sap-sample-size-calculations` |
| Derived Variables | Extension on `StudyDesign` | `x-sap-derived-variables` |
| Data Handling Rules | Extension on `StudyDesign` | `x-sap-data-handling-rules` |

---

## Extension Schemas

### 1. Statistical Methods (STATO Mapping)

**URL**: `https://protocol2usdm.io/extensions/x-sap-statistical-methods`

**Purpose**: Primary and secondary statistical analysis methods with STATO ontology mapping for interoperability.

```json
{
  "id": "ext_sap_statistical_methods",
  "url": "https://protocol2usdm.io/extensions/x-sap-statistical-methods",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"sm_1\", \"name\": \"ANCOVA\", \"description\": \"...\", \"statoCode\": \"STATO:0000029\", ...}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface StatisticalMethod {
  id: string;
  name: string;                    // e.g., "ANCOVA", "MMRM", "Kaplan-Meier"
  description: string;             // Full description from SAP
  endpointName?: string;           // Which endpoint this applies to
  statoCode?: string;              // STATO ontology code (e.g., "STATO:0000029")
  statoLabel?: string;             // STATO preferred label
  hypothesisType?: string;         // "superiority" | "non-inferiority" | "equivalence"
  testType?: string;               // "one-sided" | "two-sided"
  alphaLevel?: number;             // Significance level (e.g., 0.05)
  covariates?: string[];           // Covariates/stratification factors
  software?: string;               // Statistical software (SAS, R, etc.)
}
```

**STATO Code Reference**:
| Method | STATO Code | STATO Label |
|--------|------------|-------------|
| ANCOVA | `STATO:0000029` | analysis of covariance |
| ANOVA | `STATO:0000026` | analysis of variance |
| MMRM | `STATO:0000325` | mixed model repeated measures |
| t-test | `STATO:0000304` | Student's t-test |
| Chi-square | `STATO:0000049` | chi-square test |
| Fisher exact | `STATO:0000073` | Fisher's exact test |
| Wilcoxon | `STATO:0000076` | Wilcoxon rank sum test |
| Kaplan-Meier | `STATO:0000149` | Kaplan-Meier survival estimate |
| Cox regression | `STATO:0000223` | Cox proportional hazards |
| Log-rank | `STATO:0000148` | log-rank test |
| Logistic regression | `STATO:0000209` | logistic regression |

---

### 2. Multiplicity Adjustments

**URL**: `https://protocol2usdm.io/extensions/x-sap-multiplicity-adjustments`

**Purpose**: Methods for controlling Type I error across multiple endpoints/hypotheses.

```json
{
  "id": "ext_sap_multiplicity_adjustments",
  "url": "https://protocol2usdm.io/extensions/x-sap-multiplicity-adjustments",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"mult_1\", \"name\": \"Hochberg Procedure\", \"methodType\": \"familywise\", ...}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface MultiplicityAdjustment {
  id: string;
  name: string;                    // e.g., "Hochberg", "Bonferroni", "Graphical"
  description: string;
  methodType: string;              // "familywise" | "gatekeeping" | "graphical" | "alpha-spending"
  statoCode?: string;              // STATO code if applicable
  overallAlpha?: number;           // Family-wise error rate (e.g., 0.05)
  endpointsCovered?: string[];     // Endpoints in the family
  hierarchy?: string;              // Testing hierarchy description
}
```

---

### 3. Sensitivity Analyses

**URL**: `https://protocol2usdm.io/extensions/x-sap-sensitivity-analyses`

**Purpose**: Pre-specified sensitivity and supportive analyses for robustness assessment.

```json
{
  "id": "ext_sap_sensitivity_analyses",
  "url": "https://protocol2usdm.io/extensions/x-sap-sensitivity-analyses",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"sens_1\", \"name\": \"Per Protocol Analysis\", \"analysisType\": \"sensitivity\", ...}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface SensitivityAnalysis {
  id: string;
  name: string;
  description: string;
  primaryEndpoint?: string;        // Which endpoint this is for
  analysisType: string;            // "sensitivity" | "supportive" | "exploratory"
  methodVariation?: string;        // How it differs from primary analysis
  population?: string;             // Which population (e.g., "Per Protocol Set")
}
```

---

### 4. Subgroup Analyses

**URL**: `https://protocol2usdm.io/extensions/x-sap-subgroup-analyses`

**Purpose**: Pre-specified subgroup analyses with interaction testing specifications.

```json
{
  "id": "ext_sap_subgroup_analyses",
  "url": "https://protocol2usdm.io/extensions/x-sap-subgroup-analyses",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"sub_1\", \"name\": \"Age Subgroup\", \"subgroupVariable\": \"Age\", ...}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface SubgroupAnalysis {
  id: string;
  name: string;                    // e.g., "Age Subgroup", "Region Subgroup"
  description: string;
  subgroupVariable: string;        // Variable used for subgrouping
  categories?: string[];           // Subgroup categories (e.g., ["<65 years", ">=65 years"])
  endpoints?: string[];            // Which endpoints
  interactionTest: boolean;        // Whether interaction test is planned
}
```

---

### 5. Interim Analyses

**URL**: `https://protocol2usdm.io/extensions/x-sap-interim-analyses`

**Purpose**: Interim analysis plan including stopping boundaries and alpha spending.

```json
{
  "id": "ext_sap_interim_analyses",
  "url": "https://protocol2usdm.io/extensions/x-sap-interim-analyses",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"ia_1\", \"name\": \"Interim Analysis 1\", \"informationFraction\": 0.5, ...}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface InterimAnalysis {
  id: string;
  name: string;                      // e.g., "IA1", "Final Analysis"
  description: string;
  timing?: string;                   // When it occurs (e.g., "50% events")
  informationFraction?: number;      // 0.0-1.0
  stoppingRuleEfficacy?: string;     // Efficacy stopping boundary
  stoppingRuleFutility?: string;     // Futility stopping boundary
  alphaSpent?: number;               // Alpha spent at this look
  spendingFunction?: string;         // e.g., "O'Brien-Fleming", "Pocock"
}
```

---

### 6. Sample Size Calculations

**URL**: `https://protocol2usdm.io/extensions/x-sap-sample-size-calculations`

**Purpose**: Power and sample size calculation assumptions.

```json
{
  "id": "ext_sap_sample_size_calculations",
  "url": "https://protocol2usdm.io/extensions/x-sap-sample-size-calculations",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"ss_1\", \"name\": \"Primary Endpoint\", \"targetSampleSize\": 100, \"power\": 0.80, ...}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface SampleSizeCalculation {
  id: string;
  name: string;
  description: string;
  targetSampleSize?: number;
  power?: number;                    // e.g., 0.80, 0.90
  alpha?: number;                    // e.g., 0.05
  effectSize?: string;               // Expected treatment effect
  dropoutRate?: number;              // Expected dropout rate
  assumptions?: string;              // Key assumptions
}
```

---

### 7. Derived Variables

**URL**: `https://protocol2usdm.io/extensions/x-sap-derived-variables`

**Purpose**: Calculation formulas for derived endpoints from SAP.

```json
{
  "id": "ext_sap_derived_variables",
  "url": "https://protocol2usdm.io/extensions/x-sap-derived-variables",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"dv_1\", \"name\": \"Copper Balance\", \"formula\": \"Input - Output\", \"unit\": \"mg/day\"}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface DerivedVariable {
  id: string;
  name: string;
  formula: string;
  unit?: string;
  notes?: string;
}
```

---

### 8. Data Handling Rules

**URL**: `https://protocol2usdm.io/extensions/x-sap-data-handling-rules`

**Purpose**: Missing data and BLQ handling rules from SAP.

```json
{
  "id": "ext_sap_data_handling_rules",
  "url": "https://protocol2usdm.io/extensions/x-sap-data-handling-rules",
  "instanceType": "ExtensionAttribute",
  "valueString": "[{\"id\": \"rule_1\", \"name\": \"Missing Data\", \"rule\": \"No imputation\"}]"
}
```

**Schema for valueString (JSON array)**:
```typescript
interface DataHandlingRule {
  id: string;
  name: string;
  rule: string;
}
```

---

## Downstream System Integration

### STATO Ontology Mapping

The `statoCode` field in `StatisticalMethod` enables automatic mapping to STATO ontology for:
- **Analysis Results Model (ARM)**: Statistical method references
- **Define-XML**: Analysis metadata
- **Clinical Data Interchange**: Standardized method descriptions

### CDISC ARS (Analysis Results Standard) Linkage

SAP extraction now includes CDISC ARS linkage fields for interoperability with the Analysis Results Standard:

| SAP Entity | ARS Field | ARS Entity | Purpose |
|------------|-----------|------------|---------|
| `StatisticalMethod` | `arsOperationId` | `Operation` | Links to ARS operation codes (e.g., `Mth01_ContVar_Ancova`) |
| `StatisticalMethod` | `arsReason` | `Analysis.reason` | Analysis classification: `PRIMARY`, `SENSITIVITY`, `EXPLORATORY` |
| `SensitivityAnalysis` | `arsReason` | `Analysis.reason` | Marks as `SENSITIVITY` analysis |
| `InterimAnalysis` | `arsReportingEventType` | `ReportingEvent` | Event type: `INTERIM_1`, `INTERIM_2`, `FINAL` |

**ARS Operation ID Patterns:**

| Statistical Method | ARS Operation Pattern |
|-------------------|----------------------|
| ANCOVA | `Mth01_ContVar_Ancova` |
| ANOVA | `Mth01_ContVar_Anova` |
| MMRM | `Mth01_ContVar_MMRM` |
| t-test | `Mth01_ContVar_Ttest` |
| Chi-square | `Mth01_CatVar_ChiSq` |
| Fisher exact | `Mth01_CatVar_FisherExact` |
| Wilcoxon | `Mth01_ContVar_Wilcoxon` |
| Kaplan-Meier | `Mth01_TTE_KaplanMeier` |
| Cox regression | `Mth01_TTE_CoxPH` |
| Log-rank | `Mth01_TTE_LogRank` |
| Logistic regression | `Mth01_CatVar_LogReg` |

**Example JSON with ARS Linkage:**
```json
{
  "id": "sm_1",
  "name": "ANCOVA",
  "statoCode": "STATO:0000029",
  "arsOperationId": "Mth01_ContVar_Ancova",
  "arsReason": "PRIMARY"
}
```

For more information on CDISC ARS, see:
- [ARS GitHub Repository](https://github.com/cdisc-org/analysis-results-standard)
- [ARS Documentation](https://cdisc-org.github.io/analysis-results-standard/)

### ADaM Dataset Generation

SAP extensions support automated ADaM specification generation:
- `derivedVariables` → ADSL/ADEFF variable derivations
- `analysisPopulations` → Population flags (FASFL, SAFFL, PPROTFL)
- `sensitivityAnalyses` → Supplementary analysis datasets

### Regulatory Submission Support

Extensions support ICH E9(R1) estimand framework:
- `statisticalMethods` → Summary measure specification
- `sensitivityAnalyses` → Robustness assessment documentation
- `interimAnalyses` → DMC charter alignment

---

## Web UI Display

All SAP extensions are displayed in the **Extensions** tab of the Protocol2USDM web UI under the **SAP Data** category (purple badge).

| Extension | Icon | Description |
|-----------|------|-------------|
| Statistical Methods | BarChart3 | STATO-mapped analysis methods |
| Multiplicity Adjustments | Layers | Type I error control |
| Sensitivity Analyses | FlaskConical | Robustness analyses |
| Subgroup Analyses | GitBranch | Pre-specified subgroups |
| Interim Analyses | Clock | Stopping boundaries |
| Sample Size Calculations | Hash | Power assumptions |
| Derived Variables | Calculator | Calculation formulas |
| Data Handling Rules | ClipboardList | Missing data rules |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-31 | Initial SAP extension schema with STATO mapping |


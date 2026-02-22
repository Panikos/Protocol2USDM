# SAP Extraction & Analysis Enhancement Strategy

**Date**: 2026-02-22  
**Status**: Design Discussion  
**Authors**: Multi-agent expert panel (Biostatistics, CDISC/Regulatory, Clinical Data Management, ML/NLP Engineering, Product/UX)

---

## 1. Current State Assessment

### What exists today

The SAP extraction pipeline (`extraction/conditional/sap_extractor.py`) performs:
- **Single LLM call** with a monolithic 7-part prompt covering populations, methods, multiplicity, sensitivity, subgroups, interim analyses, sample size, derived variables, and data handling
- **40-page limit** on PDF extraction, **30K char** truncation on prompt text
- **STATO ontology mapping** via 11-method lookup table hardcoded in the prompt
- **CDISC ARS generation** (`ars_generator.py`) converting SAP data to ARS ReportingEvent structure
- **M11 Section 10 rendering** via `_compose_statistics()` in the DOCX composer
- **Extension attribute storage** — SAP data stored as JSON-serialized extension attributes on studyDesign (not first-class USDM entities)
- **Web UI** — `SAPDataView.tsx` and `ARSDataView.tsx` display extracted SAP data

### Recent fixes (this session)
- Analysis approach classification (confirmatory vs descriptive) gates estimand extraction
- Population fallback no longer fabricates boilerplate definitions
- ARS default operations no longer fabricate P-values for unknown methods

---

## 2. Expert Panel Analysis

### 2.1 Biostatistician Perspective

> *"The single most important thing a statistician wants to know is: which statistical method applies to which endpoint, and does the analysis plan coherently support the estimand framework?"*

**Critical gaps:**

| Gap | Impact | Priority |
|-----|--------|----------|
| **No endpoint-to-method linkage** | Cannot trace which statistical method analyzes which endpoint. This is the core question every biostat asks during SAP review. | P0 |
| **No estimand-to-analysis traceability** | ICH E9(R1) requires each estimand to map to a primary analysis method with specific handling strategies. Currently no linkage exists. | P0 |
| **Missing data strategy not first-class** | SAPs extensively define missing data handling (MMRM, LOCF, MI, tipping point). These map directly to estimand ICE strategies but aren't extracted as structured entities. | P1 |
| **No analysis model specification** | Covariates, stratification factors, interaction terms, random effects — the full statistical model specification is critical but only captured as free text in `description`. | P1 |
| **Descriptive statistics not structured** | For descriptive/exploratory studies, the summary statistics approach (N, mean, SD, median, IQR, min, max) should be structured — not just "no methods found." | P1 |
| **No primary/secondary analysis hierarchy** | The ordering and conditional gating of analyses (test primary first, then secondary only if primary succeeds) is clinically critical but not captured. | P2 |

**What biostatisticians actually want to see:**
```
Objective → Endpoint → Estimand → Primary Analysis Method → Sensitivity Analyses
                                  ↓
                          Analysis Population (FAS/ITT)
                                  ↓
                          Missing Data Strategy
                                  ↓
                          Multiplicity Adjustment (if applicable)
```

### 2.2 CDISC/Regulatory Perspective

> *"The USDM-to-ARS bridge is the regulatory future. Sponsors will need traceable, machine-readable analysis specifications from protocol through to CSR."*

**Critical gaps:**

| Gap | Impact | Priority |
|-----|--------|----------|
| **ARS not validated against schema** | Generated ARS JSON is never validated against CDISC ARS v1.0 schema. Unknown if output would pass CDISC validation. | P1 |
| **No ARS-to-USDM endpoint linkage** | ARS `Analysis` objects reference endpoints by name (string), not by USDM endpoint ID. No structural traceability. | P1 |
| **ResultPattern not populated** | ARS operations require `resultPattern` to describe expected output format. Currently empty for all operations. | P2 |
| **STATO codes not validated** | STATO codes are hardcoded in prompt lookup table. No runtime validation against NCI EVS or STATO ontology. | P2 |
| **No Define.xml alignment** | SAP specifies ADaM dataset structure, but no linkage to variable-level metadata that would inform Define.xml generation. | P3 |

**Regulatory trajectory**: ICH M11 Technical Specification §10 explicitly requires structured statistical methods. CDISC is converging USDM + ARS + Define.xml into a unified regulatory submission package. Our platform is positioned to deliver this, but the SAP→ARS bridge needs to be much stronger.

### 2.3 Clinical Data Management Perspective

> *"Data managers need to know what data to collect, how to handle edge cases, and which derived variables to program. The SAP is their specification document."*

**Critical gaps:**

| Gap | Impact | Priority |
|-----|--------|----------|
| **Derived variables not linked to endpoints** | Formulas are extracted but not connected to which endpoint they compute. A data programmer can't use them without context. | P1 |
| **Data handling rules not linked to variables** | BLQ rules, outlier handling, and imputation rules need to reference specific variables/endpoints. | P1 |
| **No visit window reconciliation** | SAP defines analysis visit windows; SoA defines scheduled visits. These should be aligned. | P2 |
| **No SDTM/ADaM dataset mapping** | SAPs often specify which ADaM datasets (ADSL, ADEFF, ADTTE) map to which analyses. Not captured. | P3 |

### 2.4 ML/NLP Engineering Perspective

> *"The current single-prompt approach is a known quality bottleneck. Context window saturation causes extraction degradation, and there's no validation loop."*

**Critical gaps:**

| Gap | Impact | Priority |
|-----|--------|----------|
| **Single monolithic prompt** | All 7 extraction parts compete for context window. Quality degrades on complex SAPs. The objectives extractor's Phase 1/2 pattern proved this split works. | P0 |
| **No chunking for large SAPs** | SAPs routinely exceed 100 pages. Current 40-page/30K-char limit misses critical later sections (sensitivity analyses, subgroup specs). | P0 |
| **No table extraction** | SAP tables (analysis datasets table, subgroup specifications, testing hierarchy) contain the most structured and critical information. Currently lost in PDF→text conversion. | P1 |
| **No confidence scoring** | No way to assess extraction quality per-entity. The objectives phase has confidence scoring; SAP phase doesn't. | P1 |
| **No validation loop** | Extracted methods aren't validated against known statistical patterns. E.g., MMRM should have specific covariates, ANCOVA should reference baseline. | P2 |
| **Hardcoded STATO table** | 11-method STATO lookup is in the prompt. Should be a separate code-level mapping with fallback to NCI EVS API. | P2 |

### 2.5 Product/UX Perspective

> *"The statistical analysis section is where Protocol2USDM can differentiate from competitors. Clinical professionals need to see the full traceability chain, not disconnected data fragments."*

**Critical gaps:**

| Gap | Impact | Priority |
|-----|--------|----------|
| **No traceability view** | No UI showing the full chain: Endpoint → Method → Population → Estimand. This is the killer feature for biostatisticians. | P1 |
| **SAP data buried in extensions** | Not first-class USDM entities — harder to edit, validate, and render. | P1 |
| **No protocol-vs-SAP comparison** | Protocol §10 and SAP may describe the same methods differently. Flagging discrepancies is high-value for clinical teams. | P2 |
| **ARS output is disconnected** | `ars_reporting_event.json` is a separate file, not integrated into the viewer. | P2 |
| **No statistical coherence dashboard** | No summary view showing: "3/5 endpoints have methods defined, 2 estimands lack analysis linkage, sample size covers primary endpoint only." | P2 |

---

## 3. Proposed Enhancement Roadmap

### Phase A: Multi-Pass SAP Extraction (P0 — Foundation)

**Rationale**: The single-prompt approach is the root cause of most quality issues. Splitting into focused passes — like the successful objectives Phase 1/2 pattern — dramatically improves extraction quality and enables cross-referencing.

```
Pass 1: Structural extraction (no LLM inference needed)
  → Analysis populations, sample size, baseline characteristics
  → Analysis approach classification (feed from objectives phase if available)
  
Pass 2: Method extraction WITH endpoint context
  → Statistical methods linked to specific endpoints (by ID)
  → Hypothesis type, alpha, covariates per method
  → Feed in: endpoints from objectives phase, analysis approach
  
Pass 3: Analysis plan hierarchy
  → Sensitivity analyses linked to primary methods
  → Subgroup analyses with variable specs
  → Multiplicity adjustment hierarchy
  → Interim analysis decision rules
  
Pass 4: Data handling & derived variables  
  → Missing data strategies per endpoint
  → Derived variable formulas linked to endpoints
  → Data handling rules linked to variables
```

**Key design principle**: Each pass receives the output of previous passes as context, enabling cross-referencing without hallucination.

### Phase B: Endpoint-to-Method Traceability (P0 — Core Value)

**Rationale**: This is the single highest-value feature for biostatisticians and regulators.

**Implementation:**
1. Pass 2 of SAP extraction receives `endpoints[]` from objectives phase
2. LLM links each `StatisticalMethod` to specific endpoint IDs
3. New `AnalysisSpecification` entity bridges:
   - `endpointId` → which endpoint
   - `methodId` → which statistical method  
   - `populationId` → which analysis population
   - `estimandId` → which estimand (for confirmatory studies)
   - `missingDataStrategy` → how missing data is handled
4. ARS `Analysis` objects reference USDM endpoint IDs (not just names)
5. Web UI traceability view shows the full chain

**Schema addition:**
```python
@dataclass
class AnalysisSpecification:
    """Links an endpoint to its analysis method, population, and estimand.
    
    This is the core traceability entity that connects the clinical question
    (endpoint/estimand) to the statistical answer (method/population).
    """
    id: str
    endpoint_id: str                    # USDM Endpoint reference
    method_id: str                      # StatisticalMethod reference
    population_id: str                  # AnalysisPopulation reference  
    estimand_id: Optional[str] = None   # Estimand reference (confirmatory only)
    analysis_type: str = "primary"      # primary, sensitivity, exploratory
    missing_data_strategy: Optional[str] = None
    model_specification: Optional[str] = None  # Full model spec
```

### Phase C: Analysis Approach-Aware SAP (P1 — Leveraging Recent Work)

**Rationale**: The `analysisApproach` classification we just built should propagate into SAP extraction to prevent inappropriate extraction patterns.

**For descriptive studies:**
- Extract summary statistics approach (N, mean, SD, median, IQR, min/max)
- Extract analysis populations (these still apply to descriptive studies)
- Do NOT extract hypothesis type, alpha level, multiplicity adjustments
- Structure the descriptive approach as first-class entities
- New `DescriptiveStatisticsSpec` with: measures, grouping variables, display format

**For confirmatory studies:**
- Full extraction of all 7 SAP parts
- Require hypothesis type and alpha on primary methods
- Validate multiplicity adjustment covers all primary/secondary endpoints
- Link estimands to primary analysis methods

### Phase D: Missing Data as First-Class Entity (P1)

**Rationale**: Missing data handling is the bridge between ICH E9(R1) estimands and statistical analysis. It's clinically critical and currently completely unstructured.

**New entity:**
```python
@dataclass  
class MissingDataStrategy:
    """Missing data handling approach per ICH E9(R1) alignment."""
    id: str
    name: str                           # e.g., "MMRM for primary endpoint"
    method: str                         # MMRM, LOCF, MI, tipping point, etc.
    endpoint_id: Optional[str] = None   # Which endpoint
    estimand_alignment: Optional[str] = None  # Which ICE strategy this supports
    assumptions: Optional[str] = None   # MAR, MNAR, etc.
    sensitivity_method: Optional[str] = None  # Sensitivity for this strategy
```

**ICE strategy mapping:**
| ICE Strategy | Typical Missing Data Approach |
|---|---|
| Treatment Policy | Include all data (MMRM, MI) |
| Hypothetical | Estimate as if no discontinuation (MMRM under MAR) |
| Composite | Composite endpoint (no imputation needed) |
| While on Treatment | Censor at discontinuation |

### Phase E: Large Document Handling (P0 — Engineering)

**Rationale**: SAPs routinely exceed 100 pages. Current 40-page limit misses critical content.

**Implementation:**
1. **Section-based chunking**: Use TOC/heading detection (like narrative extractor) to identify SAP sections
2. **Targeted extraction**: Route specific SAP sections to specific passes
   - "Analysis Populations" section → Pass 1
   - "Statistical Methods" section → Pass 2  
   - "Sensitivity Analyses" section → Pass 3
3. **Table-aware extraction**: Use PDF table detection to extract structured tables before LLM processing
4. **Progressive summarization**: For very large SAPs, summarize non-critical sections and extract critical ones verbatim

### Phase F: ARS Schema Conformance (P1 — Regulatory)

**Implementation:**
1. Validate generated ARS against CDISC ARS v1.0 JSON Schema
2. Fill `ResultPattern` on operations (e.g., "XX.X" for decimals, "X.XXX" for p-values)
3. Link `Analysis.dataset` to ADaM dataset names from SAP
4. Generate proper `ListOfContents` for ARS document structure
5. Validate STATO codes against NCI EVS at generation time (using existing `evs_client.py`)

### Phase G: Web UI — Statistical Traceability View (P1 — Differentiation)

**New component: `StatisticalTraceabilityView.tsx`**

Visual representation of the full analysis chain:
```
┌─────────────────────────────────────────────────────────────────┐
│  TRACEABILITY: Primary Efficacy                                  │
│                                                                  │
│  Objective: Evaluate efficacy of WTX101 vs placebo              │
│       ↓                                                          │
│  Endpoint: Change from baseline in NCC at Week 48                │
│       ↓                                                          │
│  Estimand: Primary Efficacy Estimand                             │
│    • Population: ITT (All randomized, ≥1 dose)                   │
│    • Treatment: WTX101 15mg vs Placebo                           │
│    • ICE: Discontinuation → Treatment Policy                     │
│    • Summary Measure: Difference in LS means                     │
│       ↓                                                          │
│  Analysis: ANCOVA (STATO:0000029)                                │
│    • Population: Full Analysis Set                                │
│    • Covariates: Baseline NCC, stratification factors            │
│    • Alpha: 0.05 (two-sided)                                     │
│    • Missing Data: MMRM under MAR                                │
│       ↓                                                          │
│  Sensitivity: Per-Protocol Analysis, Tipping Point               │
│       ↓                                                          │
│  Multiplicity: Hochberg procedure (primary → secondary)          │
└─────────────────────────────────────────────────────────────────┘
```

**Also:**
- Protocol-vs-SAP comparison panel (flag discrepancies)
- Statistical coherence score (% of endpoints with complete analysis specs)
- Inline ARS data in the existing viewer (not separate file)

---

## 4. Implementation Priority Matrix

| Phase | Effort | Value | Dependencies | Recommended Sprint |
|-------|--------|-------|-------------|-------------------|
| **A. Multi-pass extraction** | Large | Very High | None | Sprint 1 (foundation) |
| **E. Large document handling** | Medium | High | Phase A | Sprint 1 (with A) |
| **B. Endpoint-method traceability** | Large | Very High | Phase A | Sprint 2 |
| **C. Approach-aware SAP** | Small | High | Recent work | Sprint 2 (with B) |
| **D. Missing data entities** | Medium | High | Phase B | Sprint 3 |
| **F. ARS conformance** | Medium | Medium | Phase B | Sprint 3 |
| **G. Web UI traceability** | Large | Very High | Phases B, D | Sprint 4 |

---

## 5. Key Design Principles

1. **Extract, don't infer** — Only extract what the SAP explicitly states. No fabrication of methods, populations, or strategies (lesson from estimand fix).

2. **Traceability is the product** — Every statistical entity must link to specific endpoints, populations, and estimands. Disconnected data has minimal value.

3. **Analysis approach gates everything** — Descriptive vs confirmatory classification should propagate through SAP extraction, ARS generation, and M11 rendering.

4. **Multi-pass with cross-referencing** — Each extraction pass builds on previous results, enabling the LLM to make connections without hallucinating.

5. **Validate against standards** — ARS against CDISC schema, STATO codes against NCI EVS, statistical models against known patterns.

6. **First-class USDM entities** — Statistical analysis data should be proper USDM entities (not extension attributes) where the schema supports it. Use extensions only for truly supplementary data.

---

## 6. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Multi-pass increases LLM cost | Each pass is smaller/cheaper; total cost similar to one large call but quality much higher |
| Traceability may create false links | Require explicit endpoint ID matching, not fuzzy name matching. Confidence scoring per link. |
| Large SAPs may still exceed context | Section-based chunking ensures critical content is always extracted |
| ARS schema may evolve | Pin to ARS v1.0; abstract schema validation so version updates are isolated |
| Descriptive study SAPs have different structure | Analysis approach classification (already built) routes to appropriate extraction template |

---

## 7. Success Metrics

- **Endpoint coverage**: % of protocol endpoints with linked statistical methods → target: >90%
- **Estimand-analysis alignment**: % of estimands with complete analysis specifications → target: >80%
- **ARS schema conformance**: % of generated ARS passing CDISC validation → target: 100%
- **SAP page coverage**: % of SAP pages successfully processed → target: >95%
- **Biostatistician satisfaction**: Traceability view rated as "clinically useful" by ≥3 biostatisticians

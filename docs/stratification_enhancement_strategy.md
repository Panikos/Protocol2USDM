# Stratification & Randomization Enhancement Strategy

## Multi-Agent Expert Discussion

**Date**: 2026-02-22
**Participants**:
- **Dr. Elena Vasquez** — Biostatistician / Randomization Expert (15y pharma)
- **Dr. Ravi Menon** — CDISC Standards Architect (USDM v4.0 working group)
- **Dr. Sarah Chen** — Clinical Operations Lead (protocol authoring, IWRS vendor liaison)
- **Marcus Torres** — Software Architect (Protocol2USDM pipeline + web UI)

---

## 1. Current State Assessment

### 1.1 What Exists Today

**Extraction** (`extraction/execution/stratification_extractor.py`, 449 lines):
- Phase 4C of execution model pipeline
- Two-layer approach: heuristic regex + LLM enhancement
- Extracts: ratio, method, block size, stratification factors (name + categories), central randomization flag
- Factor categories partially hardcoded (sex → Male/Female, age → <65/≥65)
- Output stored as `RandomizationScheme` on `ExecutionModelData`
- LLM prompt is a simple single-shot extraction with 8K char limit

**Schema** (`extraction/execution/schema.py`):
- `StratificationFactor`: id, name, categories[], is_blocking, source_text
- `RandomizationScheme`: id, ratio, method, block_size, stratification_factors[], central_randomization, source_text

**Study Design Phase** (`extraction/studydesign/`):
- Extracts `randomization_type` (Randomized/Non-Randomized) and `allocation_ratio`
- `stratification_factors` stored as bare `List[str]` — no structure

**USDM Mapping**:
- Randomization type → `StudyDesign.subTypes[]` Code (C25196 Randomized, C48660 Non-Randomized)
- Stratification → loosely mapped to `StudyCohort` presence (boolean indicator in M11 composer)
- No first-class USDM entity for stratification factors
- `TransitionRule` (C82567) is the closest standard entity for allocation logic

**Web UI**:
- `StudyMetadataView.tsx`: Shows randomization as a coded dropdown in design characteristics
- `StudyDesignView.tsx`: Shows allocation ratio as editable field
- `ExecutionModelView.tsx`: Shows randomization scheme in execution model tab
- No dedicated stratification visualization

**M11 Rendering** (`rendering/composers.py`):
- Synopsis: "Stratification Indicator" = Yes/No based on cohort presence
- No rendering of stratification factor details in §4 (Trial Design)

---

## 2. Expert Discussion

### DR. VASQUEZ (Biostatistics)

The current implementation has **three fundamental gaps** from a biostatistics perspective:

**Gap 1: Factor-Level Detail is Superficial**
We capture factor names and categories but miss the critical operational details:
- **Stratification algorithm** — Is this permuted block within strata? Minimization? Biased-coin? The `method` field captures this as free text, but the algorithm determines whether unblinding risk exists.
- **Nesting structure** — Are factors crossed or nested? For multi-regional trials, "region" may be a blocking factor with "disease severity" nested within. This affects sample size calculations and interim analysis validity.
- **Factor-to-arm mapping** — Which strata map to which arms? In adaptive designs, certain strata may be dropped. We don't capture this dynamic structure.
- **Permissible combinations** — Not all factor level combinations may be valid. A 3-factor stratification with 2×3×4 levels creates 24 cells, but some may be excluded. We should capture the valid cell matrix.

**Gap 2: No Connection to Statistical Analysis**
Stratification factors directly determine:
- **Primary analysis model covariates** — Per ICH E9, stratification factors used in randomization should be included as covariates in the primary analysis model
- **Subgroup analysis pre-specification** — Stratification factors are the canonical pre-specified subgroups
- **Sample size impact** — Stratification affects the variance structure; overstratification can reduce power

We extract stratification in the execution phase and statistical methods in the SAP phase, but there's zero cross-linking. A reviewer checking protocol coherence can't verify that the ANCOVA model includes all stratification factors as covariates.

**Gap 3: No Adaptive/Response-Adaptive Handling**
Many modern trials use:
- **Response-adaptive randomization** (RAR) — Allocation ratios change based on interim results
- **Bayesian adaptive stratification** — Factor weights update over time
- **Covariate-adaptive randomization** (minimization) — Not truly stratified but often described as such
- **Platform trials** — Multiple sub-studies with different stratification schemes per arm entry

The current binary "stratified block randomization" model can't represent these.

### DR. MENON (CDISC Standards)

From a USDM v4.0 compliance perspective, stratification is **under-modeled in the standard itself**, which means we have latitude but also responsibility:

**USDM v4.0 Entities for Randomization**:
- `StudyDesign.subTypes[]` — Stores randomization type as a Code (C25196/C48660). This is the only first-class field.
- `TransitionRule` (C82567) — "A guide that governs the allocation of subjects to operational options at a discrete decision point." This is semantically correct for randomization rules but is designed for encounter/element transitions, not allocation to arms.
- `StudyCohort` (C61512) — Groups sharing characteristics. Stratification strata ARE cohorts conceptually, but USDM StudyCohort is designed for enrollment populations, not randomization strata.
- `Characteristic` — Can represent stratification factor levels (e.g., "Age ≥65") but has no built-in "used for stratification" flag.

**My recommendation**: Use **extension attributes** for the detailed stratification model (factor hierarchy, algorithm, nesting) since USDM v4.0 doesn't have first-class entities. But ensure the core USDM fields are populated correctly:

1. `subTypes[]` for randomization type
2. `StudyCohort` for each stratum (with `criterionIds` linking to eligibility criteria that define the stratum)
3. `TransitionRule` on the randomization `StudyElement` to capture the allocation logic text
4. Extension `x-stratification-scheme` for the full structured model

**ICH M11 mapping**: Section 4.3 "Method of Treatment Assignment" requires:
- Method of randomization
- Stratification factors and their levels
- Allocation ratio
- IWRS/IXRS system
- Unblinding procedures

Currently our §4 composer only renders a "Stratification Indicator: Yes/No" — this needs to become a proper subsection.

### DR. CHEN (Clinical Operations)

From an operational perspective, the biggest pain points are:

**Pain 1: IWRS Configuration Alignment**
When a sponsor sets up their IWRS (Interactive Web Response System), they need the exact stratification scheme: factors, levels, valid combinations, allocation ratio per stratum. Today's extraction gives them factor names but not the operational detail needed for IWRS configuration. If we could extract and validate the complete scheme, it would save weeks of IWRS setup.

**Pain 2: Protocol Amendment Impact**
Stratification schemes frequently change during amendments — factors get added, dropped, or their cutpoints change (e.g., age cutoff from 65 to 60). We need to track stratification changes across amendment versions so reviewers can assess re-randomization rules and data integrity implications.

**Pain 3: Multi-Regional Considerations**
ICH E17 multi-regional trials often use region as a stratification factor, but the operational meaning varies:
- **Poolability**: Can regions be combined in analysis?
- **Enrollment caps**: Some regions have maximum enrollment
- **Regulatory differences**: Different countries may require different stratification schemes

We should capture region-specific stratification constraints.

**Pain 4: Blinding and Allocation Concealment**
The relationship between stratification, blinding, and allocation concealment is critical for GCP compliance. Open-label stratified designs have different concealment requirements than double-blind ones. We should link the stratification scheme to the blinding schema.

### MARCUS TORRES (Software Architecture)

Looking at the codebase, here's my assessment of implementation feasibility:

**Current Architecture Gaps**:
1. **Dual extraction, no merge**: Study design phase extracts `randomization_type` + `stratification_factors` (bare strings). Execution phase extracts detailed `RandomizationScheme`. These never merge — the study design data goes to `StudyDesign.subTypes[]` and the execution data goes to an extension attribute. Neither benefits from the other.

2. **Heuristic bias**: `_get_factor_categories()` returns hardcoded defaults (sex → Male/Female, age → <65/≥65, region → NA/Europe/Asia/RoW). This is dangerous — it fabricates categories that may not exist in the protocol. Per our hallucination audit principles, these should come from the PDF or not at all.

3. **No cross-phase linking**: Stratification factors from Phase 4C don't link to:
   - Eligibility criteria (which define the factor levels)
   - SAP statistical methods (which should include stratification covariates)
   - Study arms (which the allocation targets)
   - Analysis populations (which may be stratified subgroups)

4. **LLM prompt is weak**: The prompt in `_extract_scheme_llm()` is a generic "analyze this text" with 8K char limit. Compared to our multi-pass SAP prompts, this is first-generation quality.

5. **M11 rendering gap**: The synopsis composer uses cohort presence as a proxy for stratification — this is wrong. A study can have cohorts without stratification and stratification without explicit cohorts.

---

## 3. Aligned Recommendations

### Phase 1: Schema & Extraction Refactor (Sprint A)

**A1: Enhanced StratificationScheme Entity**
Replace the flat `RandomizationScheme` + `StratificationFactor` with a richer model:

```python
@dataclass
class StratificationFactor:
    id: str
    name: str                           # "Age Group"
    categories: List[FactorLevel]       # Structured levels, not bare strings
    is_blocking: bool = False           # Used for block randomization
    is_nesting: bool = False            # Nested within another factor
    parent_factor_id: Optional[str]     # If nested, which factor contains this
    data_source: Optional[str]          # "screening CRF", "medical history"
    source_text: Optional[str]          # Verbatim protocol text

@dataclass
class FactorLevel:
    id: str
    label: str                          # "≥65 years"
    definition: Optional[str]           # "Participants aged 65 years or older at screening"
    criterion_id: Optional[str]         # Link to EligibilityCriterion
    code: Optional[Dict]               # NCI code if applicable

@dataclass
class AllocationCell:
    id: str
    factor_levels: Dict[str, str]       # {factor_id: level_id}
    arm_id: Optional[str]               # Target arm
    ratio_weight: int = 1               # Allocation weight within cell
    is_valid: bool = True               # False if combination excluded
    planned_enrollment: Optional[int]   # Per-cell enrollment target

@dataclass
class StratificationScheme:
    id: str
    method: str                         # "Stratified permuted block", "Minimization", "Biased-coin"
    algorithm_type: str                 # "block", "minimization", "adaptive", "simple"
    allocation_ratio: str               # "1:1", "2:1:1"
    block_sizes: List[int]              # [4, 6] for variable block sizes
    factors: List[StratificationFactor]
    cells: List[AllocationCell]         # Valid stratum×arm combinations
    iwrs_system: Optional[str]          # "Oracle Argus IXRS", "Medidata RTSM"
    seed_method: Optional[str]          # "Computer-generated", "Pre-sealed envelopes"
    concealment_method: Optional[str]   # "Central telephone", "IWRS", "Sealed envelopes"
    is_adaptive: bool = False           # Response-adaptive randomization
    adaptive_rules: Optional[str]       # Description of adaptation rules
    blinding_schema_id: Optional[str]   # Link to blinding entity
    source_text: Optional[str]
    amendment_history: List[Dict]       # Track changes across amendments
```

**A2: Multi-Pass LLM Extraction**
Similar to SAP enhancement, split into focused passes:

- **Pass 1: Scheme identification** — Is this randomized? What method? Ratio? Block size? IWRS?
- **Pass 2: Factor extraction** — What are the stratification factors? What are their exact levels/cutpoints? What defines each level? (requires longer context — look at §4 + §5 together)
- **Pass 3: Cross-validation** — With arms + eligibility context, validate that factors make sense. Flag any factors mentioned in §4 but not reflected in eligibility criteria.

**A3: Remove Hardcoded Category Defaults**
Delete `_get_factor_categories()` entirely. Categories must come from the PDF or LLM extraction, never from hardcoded defaults. If the LLM can't extract categories, store `categories=[]` and flag for manual review.

### Phase 2: Cross-Phase Linking (Sprint B)

**B1: Link Factors → Eligibility Criteria**
Each `FactorLevel` should resolve to an `EligibilityCriterion` where possible:
- "Age ≥65" → matches inclusion criterion "Adults aged 18-85 years" with sub-categorization
- "Prior therapy: Yes" → matches an explicit criterion about prior treatment

**B2: Link Factors → SAP Covariates**
After SAP extraction, cross-reference stratification factors against:
- Statistical method covariates (from Pass 2 of SAP)
- Pre-specified subgroup analyses (from Pass 3 of SAP)
Flag mismatches: "Stratification factor 'Region' not included as covariate in primary ANCOVA model"

**B3: Link Scheme → Study Arms**
The allocation ratio should decompose into arm-level targets. For "1:1:1" with arms [Drug A, Drug B, Placebo], each arm gets weight 1. For "2:1" with [Drug, Placebo], Drug gets weight 2.

**B4: Link Scheme → Analysis Populations**
Stratified analysis populations should reference the stratification scheme. The ITT population stratified by region should show which strata are represented.

### Phase 3: USDM Mapping & M11 Rendering (Sprint C)

**C1: USDM Entity Mapping**

| Extracted Entity | USDM Target | How |
|-----------------|-------------|-----|
| Randomization type | `StudyDesign.subTypes[]` | Code (C25196/C48660) — already done |
| Allocation ratio | `TransitionRule.text` on randomization element | Narrative text |
| Stratification factors | `StudyCohort` per stratum + `criterionIds` | Create cohort per unique stratum |
| Factor levels | `Characteristic` on each `StudyCohort` | One per level |
| Full scheme | Extension `x-stratification-scheme` | JSON valueString |
| IWRS details | Extension `x-iwrs-configuration` | JSON valueString |

**C2: M11 §4.3 Composer**
Add a dedicated `_compose_treatment_assignment()` composer that renders:
- Method of randomization (stratified permuted block, minimization, etc.)
- Allocation ratio with arm mapping
- Stratification factors table (Factor | Levels | Source)
- IWRS/IXRS system identification
- Allocation concealment method
- For adaptive designs: adaptation rules and triggers

**C3: Synopsis Enhancement**
Replace the boolean "Stratification Indicator" with actual content:
- "Stratified by [factor1 (n levels), factor2 (n levels)] using [method]"

### Phase 4: Web UI (Sprint D)

**D1: StratificationSchemeView Component**
New component showing:
- **Visual allocation diagram**: Arms × Strata matrix with ratio weights
- **Factor hierarchy**: Tree view showing nesting relationships
- **Coherence indicators**: Green/amber/red for factor→eligibility, factor→SAP links
- **Amendment timeline**: How stratification changed across protocol versions
- **IWRS configuration export**: Generate IWRS-compatible configuration summary

**D2: Cross-Reference Panel**
In the existing StudyDesignView, add a "Stratification" section that shows:
- Stratification factors with clickable links to eligibility criteria
- Visual connection to SAP covariates (with mismatch warnings)
- Arm allocation weights

### Phase 5: Validation & Quality (Sprint E)

**E1: Stratification Coherence Checks**
Automated checks to run during validation:
- [ ] All stratification factors have ≥2 categories
- [ ] All factors appear in primary analysis model covariates (warn if missing)
- [ ] Stratification factors are consistent with eligibility criteria
- [ ] Block size is compatible with allocation ratio (block size must be multiple of sum of ratio weights)
- [ ] Number of strata cells doesn't exceed recommended limit (warn if >16 cells for <500 subjects)
- [ ] Adaptive designs have stopping rules specified
- [ ] IWRS system identified for central randomization claims

**E2: Cross-Protocol Benchmarking**
Build a reference database of stratification patterns by therapeutic area:
- Oncology: ECOG PS, prior lines, PD-L1 status, tumor type
- Diabetes: HbA1c range, prior antidiabetic therapy, renal function
- Cardiology: NYHA class, ejection fraction, prior MI

Use this to flag unusual patterns (e.g., a diabetes trial stratifying by tumor type).

---

## 4. Prioritized Roadmap

| Sprint | Items | Effort | Impact |
|--------|-------|--------|--------|
| **A (Schema + Extraction)** | A1-A3: Enhanced schema, multi-pass LLM, remove hardcoding | 2-3 days | HIGH — fixes hallucination risk + captures real data |
| **B (Cross-Phase Linking)** | B1-B4: Factor→eligibility, factor→SAP, scheme→arms, scheme→populations | 2 days | HIGH — enables coherence validation |
| **C (USDM + M11)** | C1-C3: USDM mapping, §4.3 composer, synopsis fix | 1-2 days | MEDIUM — regulatory compliance |
| **D (Web UI)** | D1-D2: StratificationSchemeView, cross-reference panel | 2 days | MEDIUM — user value |
| **E (Validation)** | E1-E2: Coherence checks, benchmarking | 1-2 days | HIGH — quality assurance |

**Total estimate**: 8-11 days across all sprints

---

## 5. Consensus & Key Decisions

### Agreed by all experts:

1. **Remove hardcoded category defaults immediately** — This is a hallucination risk. Categories must come from the protocol text.

2. **Merge dual extraction paths** — The study design phase and execution phase both extract randomization data independently. These should share a single canonical extraction with the execution phase enriching what the study design phase starts.

3. **Cross-phase linking is the highest-value improvement** — Connecting stratification factors to eligibility criteria and SAP covariates enables automated protocol coherence checking, which is the primary use case reviewers care about.

4. **Use extension attributes for detailed scheme** — USDM v4.0 doesn't have first-class stratification entities. Use `StudyCohort` for strata where possible, extensions for the full model.

5. **M11 §4.3 rendering is a regulatory gap** — The current "Stratification Indicator: Yes/No" doesn't meet ICH M11 requirements for §4.3. This needs structured content about method, factors, ratio, and concealment.

6. **Adaptive randomization is future scope** — The schema should support it (is_adaptive flag, adaptive_rules field) but the LLM extraction for adaptive designs can come later. Most protocols still use standard stratified block randomization.

### Decisions LOCKED (USDM v4.0 schema-aligned, 2026-02-22):

1. **StudyCohort per stratum: YES — one per top-level factor level, not per cross-cell.**
   - `StudyDesignPopulation.cohorts[]` → `StudyCohort` (0..*, line 6890) is the canonical path.
   - `StudyCohort.criterionIds[]` → `EligibilityCriterion` (0..*, Ref) links factors to eligibility.
   - `StudyCohort.characteristics[]` → `Characteristic` (0..*, Value) holds factor level definitions.
   - `StudyCohort.plannedEnrollmentNumber` (QuantityRange) holds per-stratum enrollment targets.
   - For a 2×3 stratification (age × region), create **5 cohorts** (2 age + 3 region), not 6 (2×3 cross-cells). The cell matrix goes in `x-stratification-scheme` extension.

2. **Coherence checks: WARNINGS, not blocking errors.**
   - All linking relationships are `0..*` (optional) in the USDM schema — `criterionIds`, `characteristics`, `cohorts` are all non-required.
   - A stratification factor without a linked criterion is valid USDM, just incomplete.
   - Matches CDISC CORE severity model (informational/warning for incomplete data, error for structural violations).

3. **IWRS export: Generic structured output via ExtensionAttribute.**
   - No USDM entity for IWRS/IXRS systems exists.
   - `TransitionRule` (C82567) on the randomization `StudyElement` for allocation description text.
   - `ExtensionAttribute` with URL `x-iwrs-configuration` for the structured scheme JSON.
   - No vendor lock-in — generic format consumable by any IWRS vendor.

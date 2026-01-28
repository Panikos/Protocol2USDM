# Referential Integrity Analysis Report

**Date**: January 7, 2026  
**Output Analyzed**: `Alexion_Wilsons_RETEST`

---

## Executive Summary

| Category | Status | Issues |
|----------|--------|--------|
| Epoch References | ✓ Good | 0 dangling |
| Encounter References | ✓ Good | 0 dangling |
| Activity References | ✓ Good | 0 dangling |
| Cross-File Consistency | ⚠ Issue | Epoch authority violation |
| Study Cells | ⚠ Issue | Missing cell for 1 epoch |
| Sequence Numbers | ⚠ Issue | All epochs missing sequence |

---

## 1. Epoch Integrity

### 1.1 Epoch Authority Violation (CRITICAL)

**Finding**: "Early Termination" exists as a separate epoch in `protocol_usdm.json` but is NOT present in:
- `4_header_structure.json` (7 epochs)
- `9_final_soa.json` (7 epochs)

| Source | Epochs |
|--------|--------|
| Header | Screening, C-I, Inpatient Period 1, OP, Inpatient Period 2, UNS, EOS or ET |
| Final SoA | Screening, C-I, Inpatient Period 1, OP, Inpatient Period 2, UNS, EOS or ET |
| USDM Output | Above + **Early Termination** (extra) |

**Root Cause**: The execution model enrichment adds "Early Termination" as a terminal epoch, overriding SoA authority.

**Fix Applied**: Added filter in `main_v2.py` (lines 1582-1614) to preserve only SoA-sourced epochs.

### 1.2 Epoch Sequence Numbers

**Finding**: All epochs have `sequenceNumber: N/A`

This affects:
- Epoch ordering in UI displays
- Traversal logic that depends on sequence

**Recommendation**: Derive sequence numbers from SoA column order.

### 1.3 UNS Epoch Usage

**Finding**: UNS epoch has:
- 1 encounter mapped to it
- 0 schedule instances

This is **expected** - UNS (Unscheduled) visits don't have pre-defined schedule instances.

---

## 2. Encounter Integrity

### 2.1 Reference Validity

| Metric | Value |
|--------|-------|
| Total Encounters | 23 |
| Encounters with epochId | 23 ✓ |
| Encounters referenced by instances | 22 |
| Unreferenced encounters | 1 (UNS) |

**All 212 schedule instances have valid `encounterId` references.**

### 2.2 Encounter-Epoch Distribution

| Epoch | Encounters |
|-------|------------|
| Inpatient Period 2 | 10 |
| Inpatient Period 1 | 6 |
| C-I | 2 |
| Screening | 2 |
| OP | 1 |
| EOS or ET | 1 |
| UNS | 1 |

---

## 3. Activity Integrity

### 3.1 Reference Validity

| Metric | Value |
|--------|-------|
| Total Activities | 45 |
| Activities referenced by instances | 35 |
| Unreferenced activities | 10 |

**All 212 schedule instances have valid `activityIds` references.**

### 3.2 Unreferenced Activities

These activities exist but have no schedule instances:
1. Safety Assessments / Laboratory Analyses
2. Safety Assessments
3. Other
4. Enrollment
5. Balance assessments
6. *(5 more)*

**Reason**: These are likely group headers or parent activities, not scheduled directly.

---

## 4. Study Cells Integrity

### 4.1 Cell Coverage

| Metric | Value |
|--------|-------|
| Arms | 1 |
| Epochs | 8 |
| Expected Cells | 8 |
| Actual Cells | 7 |

**Missing Cell**: "Early Termination" epoch has no study cell.

This is consistent with the epoch authority issue - "Early Termination" was added by enrichment but cells weren't created for it.

### 4.2 Existing Cells

All 7 SoA epochs have proper study cells:
- Screening ✓
- C-I ✓
- Inpatient Period 1 ✓
- OP ✓
- Inpatient Period 2 ✓
- UNS ✓
- EOS or ET ✓

---

## 5. Schedule Instance Distribution

### 5.1 By Epoch

| Epoch | Instances | % |
|-------|-----------|---|
| Inpatient Period 2 | 96 | 45% |
| Inpatient Period 1 | 59 | 28% |
| C-I | 20 | 9% |
| Screening | 20 | 9% |
| EOS or ET | 9 | 4% |
| OP | 8 | 4% |
| UNS | 0 | 0% |

### 5.2 By Encounter (Top 5)

| Encounter | Instances |
|-----------|-----------|
| Screening (-42 to -9) | 19 |
| Inpatient Period 2 (Day 23) | 14 |
| C-I (-8) | 12 |
| Inpatient Period 1 (Day 1) | 12 |
| Inpatient Period 2 (Day 26-28) | 11 |

---

## 6. ID Mapping Integrity

### 6.1 Coverage

| Entity | Mapped | Actual | Coverage |
|--------|--------|--------|----------|
| Epochs | 8 | 8 | 100% ✓ |
| Encounters | 23 | 23 | 100% ✓ |
| Activities | 36 | 45 | 80% |

**Note**: 9 activities not in mapping may be dynamically generated.

---

## 7. Recommendations

### 7.1 Critical (Fix Required)

1. **Epoch Authority**: ✅ Fixed - Filter non-SoA epochs after enrichment
2. **Study Cell for ET**: Will resolve automatically when Early Termination is filtered

### 7.2 Important (Should Fix)

3. **Epoch Sequence Numbers**: Derive from SoA column order during extraction
4. **Activity Mapping**: Ensure all activities have ID mappings

### 7.3 Minor (Nice to Have)

5. **Unused Activities**: Consider marking group headers with a flag
6. **Provenance File**: Ensure provenance is generated for all outputs

---

## 8. Data Flow Verification

```
4_header_structure.json
    └── columnHierarchy.epochs (7 epochs) ✓
           │
           ▼
9_final_soa.json  
    └── study.versions[0].studyDesigns[0].epochs (7 epochs) ✓
           │
           ▼
[Execution Model Enrichment] ← Adds "Early Termination" ⚠
           │
           ▼
[Epoch Filter] ← NEW FIX: Removes non-SoA epochs
           │
           ▼
protocol_usdm.json
    └── study.versions[0].studyDesigns[0].epochs (7 epochs after fix)
```

---

*Report generated by analyze_integrity.py and deep_integrity_check.py*

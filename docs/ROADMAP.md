# Protocol2USDM Roadmap

## Future Enhancements

### User Access Management & E-Signatures (Future)

**Status:** Future enhancement  
**Priority:** Medium  
**Added:** 2026-02-10

1. **User Access Management**
   - Role-based access control (RBAC) for protocol editing
   - User authentication and session management
   - Permission levels: viewer, editor, approver

2. **E-Signatures (21 CFR Part 11)**
   - Electronic signature capture on publish
   - Signature meaning (authored, reviewed, approved)
   - Full GxP compliance with audit trail integration

### Web UI Editing Improvements (In Progress)

**Status:** In progress  
**Priority:** High  
**Added:** 2026-02-10

1. **ID-Based Patch Paths** — Replace fragile array-index JSON Patches with entity ID-based paths (`@id:` syntax)
2. **Live Validation on Publish** — Run schema/USDM/CORE validators on candidate USDM before writing to disk
3. **Audit Trail** — Reason-for-change on publish, SHA-256 hash chain, change log
4. **Extended Editing Coverage** — Add/remove/reorder for objectives, endpoints, eligibility, interventions, narrative

### ARS Output Display Generation (Future)

**Status:** Future enhancement  
**Priority:** Low  
**Added:** 2026-01-31

#### Future Extensions

1. **Output Display Generation**
   - Extract table shell specifications from SAP
   - Map to ARS `Output` and `OutputDisplay` entities
   - Generate display sections and ordinal positioning

2. **Analysis-to-Data Traceability**
   - Link ARS analyses to ADaM dataset specifications
   - Generate `AnalysisDataset` and `AnalysisVariable` entities
   - Support WHERE clause extraction for analysis subsets

3. **ARS Validation Rules**
   - Add ARS conformance checking
   - Validate operation-method consistency
   - Check analysis-population linkages

#### References
- [CDISC ARS GitHub](https://github.com/cdisc-org/analysis-results-standard)
- [ARS Documentation](https://cdisc-org.github.io/analysis-results-standard/)
- [ARS Wiki](https://wiki.cdisc.org/display/ARSP/ARS-UG+Sections)

### Unscheduled Visit (UNS) — Full State Machine Modeling (In Progress)

**Status:** Phase 1 complete, Phase 2 pending  
**Priority:** Medium  
**Added:** 2026-02-11

1. **Phase 1 (Complete)** — Tag UNS encounters with `x-encounterUnscheduled` extension, visual distinction in SoA grid (amber dashed borders, ⚡ suffix)
2. **Phase 2 (Pending)** — Promote UNS to `ScheduledDecisionInstance` with reentrant branch semantics (returns to main timeline after event-driven visit)
3. **Phase 3 (Future)** — Timeline graph visualization of UNS branches in Cytoscape.js

---

## Completed Features

### v7.5.0 - NCI Code Audit & Verification (2026-02-11)
- ✅ Systematic audit of 141 NCI C-codes against EVS API
- ✅ Fixed 70+ fabricated/wrong codes across 20+ files
- ✅ `core/code_registry.py` — centralized CodeRegistry singleton
- ✅ `core/code_verification.py` — EVS-backed verification service
- ✅ `scripts/generate_code_registry.py` — generation pipeline with `--skip-verify`
- ✅ `web-ui/lib/codelist.generated.json` — UI-ready codelists
- ✅ UNS encounter tagging (Phase 1)

### v6.11.0 - CDISC ARS Deep Integration (2026-01-31)
- ✅ Full ARS model generation (`ars_generator.py`)
- ✅ ARS dataclasses: `ReportingEvent`, `Analysis`, `AnalysisSet`, `AnalysisMethod`, `Operation`
- ✅ ARS categorization support (by Reason, by Endpoint)
- ✅ STATO-to-ARS operation mapping
- ✅ ARS JSON output (`ars_reporting_event.json`)
- ✅ CDISC ARS tab in web UI with full visualization
- ✅ API endpoint for ARS data

### v6.10.0 - SAP Extraction with STATO/ARS (2026-01-31)
- ✅ Statistical methods with STATO ontology mapping
- ✅ Multiplicity adjustments extraction
- ✅ Sensitivity/subgroup analyses extraction
- ✅ Interim analysis plan extraction
- ✅ Sample size calculations extraction
- ✅ Basic ARS linkage fields
- ✅ SAP Data tab in web UI

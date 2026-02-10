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

---

## Completed Features

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

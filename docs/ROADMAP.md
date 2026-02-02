# Protocol2USDM Roadmap

## Future Enhancements

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

"""
Unit tests for rendering/composers.py — M11 entity composers.

Each composer is a pure function: USDM dict → formatted text string.
Tests use minimal synthetic USDM dicts (no LLM, no PDF, no files).
"""

import pytest

# ---------------------------------------------------------------------------
# Minimal synthetic USDM fixture
# ---------------------------------------------------------------------------

def _make_usdm(
    arms=None, objectives=None, endpoints=None, eligibility=None,
    interventions=None, narrative=None, population=None,
    indications=None, epochs=None, estimands=None,
    blinding=None, randomization=None, titles=None,
    identifiers=None, organizations=None,
    extension_attributes=None,
):
    """Build a minimal USDM dict for composer testing."""
    design = {}
    version = {}

    if arms is not None:
        design["studyArms"] = arms
    if epochs is not None:
        design["studyEpochs"] = epochs
    if indications is not None:
        design["indications"] = indications
    if blinding is not None:
        design["blindingSchema"] = blinding
    if randomization is not None:
        design["randomizationType"] = randomization
    if population is not None:
        design["population"] = population
    if objectives is not None:
        design["objectives"] = objectives
    if endpoints is not None:
        design["endpoints"] = endpoints
    if estimands is not None:
        design["estimands"] = estimands
    if extension_attributes is not None:
        design["extensionAttributes"] = extension_attributes

    if eligibility is not None:
        design["population"] = design.get("population", {})
        design["population"]["criterionIds"] = [c["id"] for c in eligibility]
        version["eligibilityCriterionItems"] = eligibility

    if interventions is not None:
        version["studyInterventions"] = interventions

    if narrative is not None:
        version["narrativeContentItems"] = narrative

    if titles is not None:
        version["titles"] = titles
    if identifiers is not None:
        version["studyIdentifiers"] = identifiers
    if organizations is not None:
        version["organizations"] = organizations

    version["studyDesigns"] = [design]

    return {"study": {"versions": [version]}}


# Reusable building blocks
SAMPLE_ARMS = [
    {"id": "arm_1", "name": "WTX101 15mg", "type": {"code": "C174266", "decode": "Experimental"}},
    {"id": "arm_2", "name": "Placebo", "type": {"code": "C174268", "decode": "Placebo Comparator"}},
]

SAMPLE_OBJECTIVES = [
    {
        "id": "obj_1",
        "objectiveText": "Evaluate efficacy of WTX101",
        "objectiveLevel": {"code": "C85826", "decode": "Primary"},
        "objectiveEndpoints": [
            {"endpointText": "Change from baseline in NCC at Week 48", "endpointLevel": {"code": "C94496", "decode": "Primary Endpoint"}},
        ],
    },
    {
        "id": "obj_2",
        "objectiveText": "Assess safety and tolerability",
        "objectiveLevel": {"code": "C85827", "decode": "Secondary"},
        "objectiveEndpoints": [
            {"endpointText": "Incidence of TEAEs", "endpointLevel": {"code": "C139173", "decode": "Secondary Endpoint"}},
        ],
    },
]

SAMPLE_ENDPOINTS = [
    {"id": "ep_1", "endpointText": "Change from baseline in NCC at Week 48", "endpointLevel": {"code": "C94496", "decode": "Primary Endpoint"}, "objectiveId": "obj_1"},
    {"id": "ep_2", "endpointText": "Incidence of TEAEs", "endpointLevel": {"code": "C139173", "decode": "Secondary Endpoint"}, "objectiveId": "obj_2"},
]

SAMPLE_ELIGIBILITY = [
    {"id": "eci_1", "name": "Age", "text": "Male or female patients aged ≥18 years",
     "instanceType": "EligibilityCriterionItem"},
    {"id": "eci_2", "name": "Diagnosis", "text": "Confirmed diagnosis of Wilson disease",
     "instanceType": "EligibilityCriterionItem"},
]

SAMPLE_INTERVENTIONS = [
    {"id": "int_1", "name": "WTX101", "description": "Bis-choline tetrathiomolybdate",
     "role": {"decode": "Investigational"}, "administrationIds": ["admin_1"]},
    {"id": "int_2", "name": "Placebo", "description": "Matching placebo tablets",
     "role": {"decode": "Placebo"}, "administrationIds": ["admin_2"]},
]

SAMPLE_POPULATION = {
    "id": "pop_1",
    "name": "Study Population",
    "includesHealthySubjects": False,
    "plannedEnrollmentNumber": {"maxValue": 150},
    "plannedAge": {
        "id": "age_1", "instanceType": "Range", "isApproximate": False,
        "minValue": {"id": "q_min", "value": 18, "unit": {"id": "u1", "standardCode": {"code": "C29848", "decode": "Years", "instanceType": "Code"}, "instanceType": "AliasCode"}, "instanceType": "Quantity"},
        "maxValue": {"id": "q_max", "value": 75, "unit": {"id": "u2", "standardCode": {"code": "C29848", "decode": "Years", "instanceType": "Code"}, "instanceType": "AliasCode"}, "instanceType": "Quantity"},
    },
    "plannedSex": [{"code": "C16576", "decode": "Female"}, {"code": "C20197", "decode": "Male"}],
}

SAMPLE_EPOCHS = [
    {"id": "epoch_1", "name": "Screening"},
    {"id": "epoch_2", "name": "Treatment"},
    {"id": "epoch_3", "name": "Follow-up"},
]

SAMPLE_INDICATIONS = [
    {"id": "ind_1", "name": "Wilson Disease", "description": "Hepatolenticular degeneration"},
]

SAMPLE_ESTIMANDS = [
    {
        "id": "est_1",
        "summaryMeasure": "Difference in means",
        "treatment": {"decode": "WTX101 15mg"},
        "variableOfInterest": {"text": "Change from baseline in NCC"},
        "population": {"text": "ITT population"},
        "intercurrentEvents": [
            {"name": "Treatment discontinuation", "strategy": {"decode": "Treatment Policy"}},
        ],
    },
]

SAMPLE_NARRATIVE = [
    {
        "id": "nc_7_1", "sectionNumber": "7", "sectionTitle": "Discontinuation of Trial Intervention",
        "text": "Subjects may discontinue study drug for safety reasons.",
        "sectionType": {"code": "DISCONTINUATION", "decode": "Discontinuation"},
    },
    {
        "id": "nc_9_1", "sectionNumber": "9", "sectionTitle": "Adverse Events",
        "text": "All adverse events will be collected from signing of informed consent.",
        "sectionType": {"code": "SAFETY", "decode": "Safety"},
    },
]


# ============================================================================
# Synopsis Composer
# ============================================================================

class TestComposeSynopsis:
    """Test _compose_synopsis (§1.1.2 Overall Design)."""

    def test_synopsis_with_full_data(self):
        from rendering.composers import _compose_synopsis
        usdm = _make_usdm(
            arms=SAMPLE_ARMS,
            population=SAMPLE_POPULATION,
            indications=SAMPLE_INDICATIONS,
            epochs=SAMPLE_EPOCHS,
            blinding={"standardCode": {"code": "C15228", "decode": "Double Blind Study"}},
            randomization={"code": "C25196", "decode": "Randomized"},
        )
        text = _compose_synopsis(usdm)
        assert "Overall Design" in text
        assert "Wilson Disease" in text
        assert "18 to 75" in text
        assert "Target: 150" in text
        assert "Number of Arms" in text
        assert "2" in text

    def test_synopsis_empty_usdm(self):
        from rendering.composers import _compose_synopsis
        text = _compose_synopsis({})
        # Empty USDM should return empty or minimal text
        assert isinstance(text, str)

    def test_synopsis_single_arm(self):
        from rendering.composers import _compose_synopsis
        usdm = _make_usdm(arms=[{"id": "arm_1", "name": "Treatment", "type": {}}])
        text = _compose_synopsis(usdm)
        assert "Control Type" in text
        assert "None" in text

    def test_synopsis_with_placebo_control(self):
        from rendering.composers import _compose_synopsis
        usdm = _make_usdm(arms=SAMPLE_ARMS)
        text = _compose_synopsis(usdm)
        assert "Placebo" in text

    def test_synopsis_epochs_duration(self):
        from rendering.composers import _compose_synopsis
        usdm = _make_usdm(epochs=SAMPLE_EPOCHS)
        text = _compose_synopsis(usdm)
        assert "Screening" in text
        assert "Treatment" in text
        assert "Follow-up" in text


# ============================================================================
# Objectives Composer
# ============================================================================

class TestComposeObjectives:
    """Test _compose_objectives (§3 Objectives and Endpoints)."""

    def test_objectives_with_data(self):
        from rendering.composers import _compose_objectives
        usdm = _make_usdm(objectives=SAMPLE_OBJECTIVES, endpoints=SAMPLE_ENDPOINTS)
        text = _compose_objectives(usdm)
        assert "Primary" in text
        assert "Evaluate" in text
        assert "NCC" in text  # endpoint text included

    def test_objectives_empty(self):
        from rendering.composers import _compose_objectives
        text = _compose_objectives({})
        assert isinstance(text, str)

    def test_objectives_no_endpoints(self):
        from rendering.composers import _compose_objectives
        # Objectives without objectiveEndpoints
        objs_no_ep = [
            {"id": "obj_1", "objectiveText": "Evaluate efficacy", "objectiveLevel": {"decode": "Primary"}},
        ]
        usdm = _make_usdm(objectives=objs_no_ep)
        text = _compose_objectives(usdm)
        assert "Primary" in text
        assert "Evaluate" in text


# ============================================================================
# Study Design Composer
# ============================================================================

class TestComposeStudyDesign:
    """Test _compose_study_design (§4 Trial Design)."""

    def test_study_design_with_arms(self):
        from rendering.composers import _compose_study_design
        usdm = _make_usdm(
            arms=SAMPLE_ARMS,
            epochs=SAMPLE_EPOCHS,
            blinding={"standardCode": {"decode": "Double Blind"}},
        )
        text = _compose_study_design(usdm)
        assert "WTX101" in text or "arm" in text.lower()

    def test_study_design_empty(self):
        from rendering.composers import _compose_study_design
        text = _compose_study_design({})
        assert isinstance(text, str)


# ============================================================================
# Eligibility Composer
# ============================================================================

class TestComposeEligibility:
    """Test _compose_eligibility (§5 Study Population)."""

    def test_eligibility_with_criteria(self):
        from rendering.composers import _compose_eligibility
        usdm = _make_usdm(eligibility=SAMPLE_ELIGIBILITY, population=SAMPLE_POPULATION)
        text = _compose_eligibility(usdm)
        assert isinstance(text, str)
        # Should mention age or criteria
        if text.strip():
            assert "18" in text or "Wilson" in text or "criteria" in text.lower() or "population" in text.lower()

    def test_eligibility_empty(self):
        from rendering.composers import _compose_eligibility
        text = _compose_eligibility({})
        assert isinstance(text, str)


# ============================================================================
# Interventions Composer
# ============================================================================

class TestComposeInterventions:
    """Test _compose_interventions (§6 Trial Interventions)."""

    def test_interventions_with_data(self):
        from rendering.composers import _compose_interventions
        usdm = _make_usdm(interventions=SAMPLE_INTERVENTIONS, arms=SAMPLE_ARMS)
        text = _compose_interventions(usdm)
        if text.strip():
            assert "WTX101" in text or "Intervention" in text

    def test_interventions_empty(self):
        from rendering.composers import _compose_interventions
        text = _compose_interventions({})
        assert text == "" or isinstance(text, str)


# ============================================================================
# Estimands Composer
# ============================================================================

class TestComposeEstimands:
    """Test _compose_estimands (§3.1 Estimands)."""

    def test_estimands_with_data(self):
        from rendering.composers import _compose_estimands
        usdm = _make_usdm(estimands=SAMPLE_ESTIMANDS)
        text = _compose_estimands(usdm)
        if text.strip():
            assert "Estimand" in text or "Treatment" in text or "WTX101" in text

    def test_estimands_empty(self):
        from rendering.composers import _compose_estimands
        text = _compose_estimands({})
        assert isinstance(text, str)

    def test_estimands_descriptive_study_no_estimands(self):
        """Descriptive study with no estimands should explain why per ICH E9(R1)."""
        from rendering.composers import _compose_estimands
        ext = [{
            "id": "ext_1",
            "url": "http://www.example.org/usdm/extensions/x-analysisApproach",
            "valueString": "descriptive",
        }]
        usdm = _make_usdm(extension_attributes=ext)
        text = _compose_estimands(usdm)
        assert "not formally defined" in text.lower() or "descriptive" in text.lower()
        assert "ICH E9" in text

    def test_estimands_confirmatory_study_no_estimands(self):
        """Confirmatory study with no estimands should note the gap."""
        from rendering.composers import _compose_estimands
        ext = [{
            "id": "ext_1",
            "url": "http://www.example.org/usdm/extensions/x-analysisApproach",
            "valueString": "confirmatory",
        }]
        usdm = _make_usdm(extension_attributes=ext)
        text = _compose_estimands(usdm)
        assert "no estimands" in text.lower() or "not identified" in text.lower()
        assert "ICH E9" in text

    def test_estimands_renders_all_e9_attributes(self):
        """Estimands with full ICH E9(R1) data should render all 5 attributes."""
        from rendering.composers import _compose_estimands
        estimands = [{
            "id": "est_1",
            "name": "Primary Efficacy Estimand",
            "populationSummary": "ITT Population",
            "analysisPopulation": "Intent-to-Treat",
            "treatment": "Drug X 100mg vs Placebo",
            "variableOfInterest": "Change from baseline in HbA1c at Week 24",
            "summaryMeasure": "Difference in LS means",
            "intercurrentEvents": [
                {"id": "ice_1", "name": "Treatment discontinuation",
                 "text": "Discontinues before Week 24", "strategy": "Treatment Policy"},
                {"id": "ice_2", "name": "Rescue medication",
                 "text": "Uses rescue medication", "strategy": "Hypothetical"},
            ],
            "instanceType": "Estimand",
        }]
        usdm = _make_usdm(estimands=estimands)
        text = _compose_estimands(usdm)
        assert "ICH E9" in text
        assert "Population" in text
        assert "Treatment" in text
        assert "Variable of Interest" in text
        assert "Summary Measure" in text
        assert "Intercurrent Events" in text
        assert "Treatment discontinuation" in text
        assert "Rescue medication" in text


# ============================================================================
# Discontinuation Composer
# ============================================================================

class TestComposeDiscontinuation:
    """Test _compose_discontinuation (§7 Discontinuation)."""

    def test_discontinuation_with_narrative(self):
        from rendering.composers import _compose_discontinuation
        usdm = _make_usdm(narrative=SAMPLE_NARRATIVE)
        text = _compose_discontinuation(usdm)
        if text.strip():
            assert "discontinu" in text.lower() or "safety" in text.lower()

    def test_discontinuation_empty(self):
        from rendering.composers import _compose_discontinuation
        text = _compose_discontinuation({})
        assert isinstance(text, str)

    def test_discontinuation_keyword_fallback_for_untagged_items(self):
        from rendering.composers import _compose_discontinuation
        usdm = _make_usdm(narrative=[
            {
                "id": "nc_x",
                "sectionNumber": "6.8",
                "sectionTitle": "Treatment Discontinuation",
                "text": "Participants may withdraw early for safety reasons.",
            }
        ])
        text = _compose_discontinuation(usdm)
        assert "discontinu" in text.lower() or "withdraw" in text.lower()


# ============================================================================
# Safety Composer
# ============================================================================

class TestComposeSafety:
    """Test _compose_safety (§9 Adverse Events / Safety)."""

    def test_safety_with_narrative(self):
        from rendering.composers import _compose_safety
        usdm = _make_usdm(narrative=SAMPLE_NARRATIVE)
        text = _compose_safety(usdm)
        if text.strip():
            assert "adverse" in text.lower() or "safety" in text.lower()

    def test_safety_empty(self):
        from rendering.composers import _compose_safety
        text = _compose_safety({})
        assert isinstance(text, str)

    def test_safety_keyword_fallback_for_untagged_items(self):
        from rendering.composers import _compose_safety
        usdm = _make_usdm(narrative=[
            {
                "id": "nc_y",
                "sectionNumber": "6.9",
                "sectionTitle": "Safety Monitoring",
                "text": "All adverse events are collected and reported.",
            }
        ])
        text = _compose_safety(usdm)
        assert "adverse" in text.lower() or "safety" in text.lower()


# ============================================================================
# Statistics Composer
# ============================================================================

class TestComposeStatistics:
    """Test _compose_statistics (§10 Statistical Considerations)."""

    def test_statistics_with_population(self):
        from rendering.composers import _compose_statistics
        usdm = _make_usdm(population=SAMPLE_POPULATION)
        text = _compose_statistics(usdm)
        assert isinstance(text, str)

    def test_statistics_empty(self):
        from rendering.composers import _compose_statistics
        text = _compose_statistics({})
        assert isinstance(text, str)

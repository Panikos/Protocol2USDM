"""Regression tests for main_v3 orchestration helper refactor."""

import json
import os
import re
import sys
from types import SimpleNamespace
from types import ModuleType

from main_v3 import (
    _build_parser,
    _resolve_output_dir,
    _parse_soa_pages,
    _has_explicit_phase_selection,
    _enable_complete_mode,
    _build_phases_to_run,
    _is_pipeline_success,
    _run_soa_stage,
    _run_expansion_stages,
    _combine_validate_and_render,
)


def _parse_default_args(extra: list[str] | None = None):
    parser = _build_parser()
    argv = ["protocol.pdf"]
    if extra:
        argv.extend(extra)
    return parser.parse_args(argv)


def test_build_parser_contains_expected_options():
    parser = _build_parser()
    opts = parser._option_string_actions
    assert "--full-protocol" in opts
    assert "--expansion-only" in opts
    assert "--sap" in opts
    assert "--sites" in opts
    assert "--json-log" in opts


def test_resolve_output_dir_uses_explicit_value():
    assert _resolve_output_dir("C:/tmp/protocol.pdf", "custom/output") == "custom/output"


def test_resolve_output_dir_generates_timestamped_default():
    out = _resolve_output_dir("C:/tmp/my_protocol.pdf", None)
    assert out.startswith(f"output{os.sep}my_protocol_")
    assert re.search(r"\d{8}_\d{6}$", out)


def test_parse_soa_pages_returns_zero_indexed_pages():
    assert _parse_soa_pages("1, 2,10") == [0, 1, 9]


def test_parse_soa_pages_raises_on_invalid_value():
    try:
        _parse_soa_pages("1,a,3")
        raise AssertionError("Expected ValueError for non-integer page token")
    except ValueError:
        pass


def test_has_explicit_phase_selection_defaults_false():
    args = _parse_default_args()
    assert _has_explicit_phase_selection(args) is False


def test_has_explicit_phase_selection_detects_set_flag():
    args = _parse_default_args(["--metadata"])
    assert _has_explicit_phase_selection(args) is True


def test_has_explicit_phase_selection_detects_conditional_source_path():
    args = _parse_default_args(["--sap", "sap.pdf"])
    assert _has_explicit_phase_selection(args) is True


def test_enable_complete_mode_sets_all_dependent_flags_true():
    args = _parse_default_args()
    _enable_complete_mode(args)
    assert args.full_protocol is True
    assert args.soa is True
    assert args.enrich is True
    assert args.validate_schema is True
    assert args.conformance is True


def test_build_phases_to_run_uses_matching_flags():
    args = _parse_default_args(["--metadata"])
    phases = _build_phases_to_run(args, ["metadata", "study_design", "execution"])
    assert phases["metadata"] is True
    assert phases["study_design"] is False
    assert phases["execution"] is False


def test_build_phases_to_run_full_protocol_enables_all():
    args = _parse_default_args(["--full-protocol"])
    phases = _build_phases_to_run(args, ["metadata", "study_design", "execution"])
    assert phases["metadata"] is True
    assert phases["study_design"] is True
    assert phases["execution"] is True


def test_build_phases_to_run_does_not_force_sap_sites_without_sources():
    args = _parse_default_args(["--full-protocol"])
    phases = _build_phases_to_run(args, ["metadata", "sap", "sites"])
    assert phases["metadata"] is True
    assert phases["sap"] is False
    assert phases["sites"] is False


def test_build_phases_to_run_enables_sap_sites_when_sources_provided():
    args = _parse_default_args(["--metadata", "--sap", "sap.pdf", "--sites", "sites.csv"])
    phases = _build_phases_to_run(args, ["metadata", "sap", "sites"])
    assert phases["metadata"] is True
    assert phases["sap"] is True
    assert phases["sites"] is True


def test_is_pipeline_success_true_when_all_successful():
    result = SimpleNamespace(success=True)
    expansion_results = {
        "metadata": SimpleNamespace(success=True),
        "_pipeline_context": object(),
    }
    assert _is_pipeline_success(result, expansion_results) is True


def test_is_pipeline_success_false_on_failed_expansion_phase():
    result = SimpleNamespace(success=True)
    expansion_results = {
        "metadata": SimpleNamespace(success=False),
    }
    assert _is_pipeline_success(result, expansion_results) is False


def test_run_soa_stage_loads_existing_soa_when_not_running_extraction(tmp_path, monkeypatch):
    expected = {"study": {"id": "study_1"}}
    soa_path = tmp_path / "9_final_soa.json"
    soa_path.write_text(json.dumps(expected), encoding="utf-8")

    monkeypatch.setattr("main_v3._merge_header_footnotes", lambda soa, _out, _pdf: soa)

    args = _parse_default_args()
    result, soa_data = _run_soa_stage(
        args=args,
        output_dir=str(tmp_path),
        soa_pages=None,
        config=SimpleNamespace(model_name="test"),
        run_soa=False,
    )

    assert result is None
    assert soa_data == expected


def test_run_soa_stage_runs_extractor_and_reads_output(tmp_path, monkeypatch):
    expected = {"study": {"id": "study_1"}}
    soa_path = tmp_path / "soa.json"
    soa_path.write_text(json.dumps(expected), encoding="utf-8")
    fake_result = SimpleNamespace(success=True, output_path=str(soa_path))

    monkeypatch.setattr("main_v3.run_from_files", lambda **_kwargs: fake_result)
    monkeypatch.setattr("main_v3._merge_header_footnotes", lambda soa, _out, _pdf: soa)
    monkeypatch.setattr("main_v3._print_soa_results", lambda _result: None)

    args = _parse_default_args()
    result, soa_data = _run_soa_stage(
        args=args,
        output_dir=str(tmp_path),
        soa_pages=[0, 1],
        config=SimpleNamespace(model_name="test"),
        run_soa=True,
    )

    assert result is fake_result
    assert soa_data == expected


def test_run_expansion_stages_returns_empty_when_disabled():
    args = _parse_default_args()
    expansion = _run_expansion_stages(
        args=args,
        output_dir="output/test",
        config=SimpleNamespace(model_name="test"),
        soa_data=None,
        phases_to_run={},
        run_any_expansion=False,
    )
    assert expansion == {}


def test_run_expansion_stages_parallel_forwards_conditional_paths(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, usage_tracker=None):
            captured["usage_tracker_set"] = usage_tracker is not None

        def run_phases_parallel(self, **kwargs):
            captured["kwargs"] = kwargs
            return {"metadata": SimpleNamespace(success=True)}

        def save_provenance(self, output_dir):
            captured["saved_to"] = output_dir

    monkeypatch.setattr("main_v3.PipelineOrchestrator", FakeOrchestrator)

    args = _parse_default_args(["--parallel", "--sap", "sap.pdf", "--sites", "sites.csv"])
    expansion = _run_expansion_stages(
        args=args,
        output_dir="output/test",
        config=SimpleNamespace(model_name="test"),
        soa_data={"study": {}},
        phases_to_run={"metadata": True, "sap": True, "sites": True},
        run_any_expansion=True,
    )

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["sap_path"] == "sap.pdf"
    assert kwargs["sites_path"] == "sites.csv"
    assert captured["saved_to"] == "output/test"
    assert "metadata" in expansion


def test_run_expansion_stages_sequential_calls_run_phases(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, usage_tracker=None):
            captured["usage_tracker_set"] = usage_tracker is not None

        def run_phases(self, **kwargs):
            captured["kwargs"] = kwargs
            return {"metadata": SimpleNamespace(success=True)}

        def run_phases_parallel(self, **kwargs):
            raise AssertionError("parallel path should not be used in this test")

        def save_provenance(self, output_dir):
            captured["saved_to"] = output_dir

    monkeypatch.setattr("main_v3.PipelineOrchestrator", FakeOrchestrator)

    args = _parse_default_args(["--metadata"])
    expansion = _run_expansion_stages(
        args=args,
        output_dir="output/test",
        config=SimpleNamespace(model_name="test"),
        soa_data={"study": {}},
        phases_to_run={"metadata": True},
        run_any_expansion=True,
    )

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["phases_to_run"]["metadata"] is True
    assert captured["saved_to"] == "output/test"
    assert "metadata" in expansion


def test_run_expansion_stages_save_provenance_failure_is_non_blocking(monkeypatch):
    class FakeOrchestrator:
        def __init__(self, usage_tracker=None):
            pass

        def run_phases(self, **kwargs):
            return {"metadata": SimpleNamespace(success=True)}

        def save_provenance(self, output_dir):
            raise RuntimeError("save failed")

    monkeypatch.setattr("main_v3.PipelineOrchestrator", FakeOrchestrator)

    args = _parse_default_args(["--metadata"])
    expansion = _run_expansion_stages(
        args=args,
        output_dir="output/test",
        config=SimpleNamespace(model_name="test"),
        soa_data={"study": {}},
        phases_to_run={"metadata": True},
        run_any_expansion=True,
    )

    assert expansion["metadata"].success is True


def test_combine_validate_and_render_returns_empty_tuple_when_skipped():
    args = _parse_default_args(["--metadata"])
    args.full_protocol = False
    combined_usdm_path, schema_validation_result, schema_fixer_result, usdm_result = _combine_validate_and_render(
        args=args,
        output_dir="output/test",
        soa_data=None,
        expansion_results={},
        config=SimpleNamespace(model_name="test"),
        run_any_expansion=False,
    )

    assert combined_usdm_path is None
    assert schema_validation_result is None
    assert schema_fixer_result is None
    assert usdm_result is None


def test_combine_validate_and_render_happy_path_writes_fixed_usdm(tmp_path, monkeypatch):
    output_path = tmp_path / "protocol_usdm.json"
    combined = {"study": {"id": "raw"}}
    fixed = {"study": {"id": "fixed"}}

    schema_validation_result = SimpleNamespace(valid=True, usdm_version_expected="4.0", error_count=0, warning_count=0)
    schema_fixer_result = SimpleNamespace(fixed_issues=0)
    usdm_result = SimpleNamespace(valid=True, error_count=0, warning_count=0, issues=[])

    monkeypatch.setattr("main_v3.combine_to_full_usdm", lambda *_args, **_kwargs: (combined, str(output_path)))
    monkeypatch.setattr(
        "main_v3.validate_and_fix_schema",
        lambda *_args, **_kwargs: (fixed, schema_validation_result, schema_fixer_result, usdm_result, {}),
    )

    captured = {"saved": False}
    monkeypatch.setattr("main_v3._save_schema_validation", lambda *_args, **_kwargs: captured.__setitem__("saved", True))

    fake_renderer = ModuleType("rendering.m11_renderer")
    fake_renderer.render_m11_docx = lambda *_args, **_kwargs: SimpleNamespace(
        success=True,
        sections_with_content=1,
        sections_rendered=1,
        total_words=42,
    )
    monkeypatch.setitem(sys.modules, "rendering.m11_renderer", fake_renderer)

    args = _parse_default_args(["--full-protocol"])
    out_path, out_schema, out_fixer, out_usdm = _combine_validate_and_render(
        args=args,
        output_dir=str(tmp_path),
        soa_data={"study": {}},
        expansion_results={"metadata": SimpleNamespace(success=True)},
        config=SimpleNamespace(model_name="test"),
        run_any_expansion=True,
    )

    assert out_path == str(output_path)
    assert out_schema is schema_validation_result
    assert out_fixer is schema_fixer_result
    assert out_usdm is usdm_result
    assert captured["saved"] is True

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == fixed

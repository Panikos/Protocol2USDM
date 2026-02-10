import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import pipeline_api


def test_run_pipeline_uses_given_model_and_disables_viewer(monkeypatch, tmp_path):
    """run_pipeline should delegate to process_single_pdf with correct args."""
    pdf_path = tmp_path / "protocol.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")

    called = {}

    def fake_process(pdf, model_name, launch_viewer=True, exit_on_failure=True):
        called["args"] = (str(pdf), model_name, launch_viewer, exit_on_failure)
        return "output/final.json"

    monkeypatch.setattr(pipeline_api, "process_single_pdf", fake_process)

    result = pipeline_api.run_pipeline(str(pdf_path), model="gpt-4o")

    assert result == "output/final.json"
    assert called["args"][0] == str(pdf_path)
    assert called["args"][1] == "gpt-4o"
    # API should disable viewer and exit-on-failure for programmatic use
    assert called["args"][2] is False  # launch_viewer
    assert called["args"][3] is False  # exit_on_failure


def test_run_pipeline_propagates_errors(monkeypatch, tmp_path):
    """run_pipeline should surface exceptions from process_single_pdf."""
    pdf_path = tmp_path / "protocol.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")

    def fake_process(*args, **kwargs):
        raise RuntimeError("pipeline boom")

    monkeypatch.setattr(pipeline_api, "process_single_pdf", fake_process)

    with pytest.raises(RuntimeError, match="pipeline boom"):
        pipeline_api.run_pipeline(str(pdf_path), model="gpt-5.1")

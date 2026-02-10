import os
import sys
import types
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_mod


def test_main_processes_each_pdf(tmp_path):
    """main.py should call process_single_pdf once for every PDF discovered."""
    # Create three dummy PDF files in a temp dir
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    pdf_files = [pdf_dir / f"file{i}.pdf" for i in range(3)]
    for p in pdf_files:
        p.write_bytes(b"%PDF-1.4 dummy content")

    # Monkeypatch argv to simulate CLI call
    test_args = ["main.py", str(pdf_dir)]

    with mock.patch.object(sys, "argv", test_args):
        called = []

        def fake_process(pdf_path, model):
            called.append(pdf_path)

        with mock.patch.object(main_mod, "process_single_pdf", side_effect=fake_process):
            # Run main() – should not raise
            main_mod.main()

    # Ensure each of the three PDFs was processed
    assert len(called) == 3
    assert set(map(os.path.abspath, called)) == set(map(str, pdf_files))

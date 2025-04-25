# Protocol2USDMv3

## Overview
Protocol2USDMv3 is an automated pipeline for extracting, validating, and structuring the Schedule of Activities (SoA) from clinical trial protocol PDFs, outputting data conformant to the USDM v4.0 model. The workflow combines LLM text and vision extraction, robust validation, and advanced mapping/regeneration tools for maximum reliability.

## Key Features
- **Automated SoA Extraction**: Extracts SoA tables from protocol PDFs using both LLM text and vision analysis (GPT-4o recommended).
- **Full Timepoint Preservation**: Prompts and postprocessing logic ensure that *all* extracted timepoints (including ranges and non-canonical labels) are preserved throughout the workflow. No timepoints are dropped or merged unless their IDs and labels are *exact* duplicates.
- **Timepoint Audit & Reconciliation**: Includes an audit script (`audit_timepoints.py`) that compares timepoints across extraction steps and reports any discrepancies, helping you identify and restore any lost timepoints.
- **Robust Dual-Path Workflow**: Parallel extraction from PDF text and images, with downstream LLM-based adjudication and merging.
- **Entity Mapping Regeneration**: Regenerate `soa_entity_mapping.json` from the latest USDM Excel mapping (`USDM_CT.xlsx`) at any time using `generate_soa_entity_mapping.py`. The mapping is automatically preserved during cleanup.
- **Validation & Error Handling**: Validates all outputs against the USDM OpenAPI schema and mapping. The pipeline is resilient to missing or malformed fields (e.g., missing timepoint IDs) and will warn and continue instead of crashing.
- **Modular & Extensible**: All steps are modular scripts, easily customizable for your workflow.

## Installation
```bash
pip install -r requirements.txt
```

## Usage
1. Place your protocol PDF in the project directory.
2. Ensure your `.env` file contains your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-...
   ```
3. (Optional) Regenerate the entity mapping from Excel:
   ```bash
   python generate_soa_entity_mapping.py
   # This reads temp/USDM_CT.xlsx and writes soa_entity_mapping.json
   ```
4. Run the main workflow:
   ```bash
   python main.py <your_protocol.pdf>
   ```

## How to Select the LLM Model

You can specify which OpenAI model (e.g., `gpt-4o`, `gpt-3o`, or any other supported model) is used for all LLM-powered pipeline steps. This applies to `main.py`, `find_soa_pages.py`, and all extraction/reconciliation scripts.

**Option 1: Command-line argument**
```bash
python main.py <your_protocol.pdf> --model o3
python main.py <your_protocol.pdf> --model o3-mini-high
python main.py <your_protocol.pdf> --model gpt-4o
```

**Option 2: Environment variable**
```bash
set OPENAI_MODEL=o3  # Windows
export OPENAI_MODEL=o3  # Linux/Mac
python main.py <your_protocol.pdf>
```

If not specified, the default is `o3`. The selected model will be used for both text and vision extraction, as well as reconciliation. If `o3` fails, the pipeline will automatically retry with `o3-mini-high`.

5. Outputs:
   - `soa_text.json`: SoA extracted from PDF text.
   - `soa_vision.json`: SoA extracted from images (vision).
   - `soa_vision_fixed.json` and `soa_text_fixed.json`: Post-processed, normalized outputs.
   - `soa_final.json`: (If adjudication/merging is enabled) LLM-adjudicated, merged SoA.
   - `audit_timepoints_report.json`: (Optional) Audit report showing any timepoints lost or altered between extraction and final output.
   - (Stub) HTML/Markdown rendering for review.

## How to Run the Streamlit SoA Review App

You can launch the interactive SoA review UI at any time to visualize and explore any SoA output JSON file:

```bash
streamlit run soa_streamlit_viewer.py
```

- By default, you can select any output file (e.g., `STEP5_soa_final.json`) from the UI sidebar.
- The app supports all USDM/M11-compliant outputs and will auto-detect the timeline structure.
- You can also set the model for any LLM-powered features in the viewer using the same `--model` argument or `OPENAI_MODEL` environment variable if applicable.

Visit [http://localhost:8501](http://localhost:8501) in your browser after running the above command.

## Project Structure
- `main.py` — Orchestrates the full workflow.
- `generate_soa_entity_mapping.py` — Regenerates `soa_entity_mapping.json` from `USDM_CT.xlsx`.
- `generate_soa_llm_prompt.py` — Generates LLM prompt instructions from the mapping.
- `find_soa_pages.py` — Finds candidate SoA pages in PDFs.
- `extract_pdf_pages_as_images.py` — Extracts PDF pages as images.
- `send_pdf_to_openai.py` — LLM text-based SoA extraction (GPT-4o, max_tokens=16384).
- `vision_extract_soa.py` — LLM vision-based SoA extraction (GPT-4o, max_tokens=16384).
- `soa_postprocess_consolidated.py` — Consolidates and normalizes extracted SoA JSON, robust to missing/misnamed keys.
- `soa_extraction_validator.py` — Validates output against USDM mapping and schema.
- `reconcile_soa_llm.py` — (Optional) LLM-based adjudication/merging of text/vision outputs.
- `requirements.txt` — All dependencies listed here.
- `temp/` — Place `USDM_CT.xlsx` here for mapping regeneration.

## Model & Token Settings
- **o3** is the default and recommended model for both text and vision extraction. If unavailable, the pipeline will automatically retry with `o3-mini-high`. `gpt-4o` is also supported if available.
- The pipeline automatically sets `max_tokens=90000` for `o3` and `o3-mini-high`, or `16384` for `gpt-4o`.
- All scripts respect the `--model` command-line argument or `OPENAI_MODEL` environment variable.
- The pipeline prints which model is being used and if fallback is triggered.
- If you see truncation warnings, consider splitting large PDFs or reducing prompt size.

## Troubleshooting
- **KeyError: 'plannedTimepointId'**: The pipeline now skips and warns on timepoints missing both `plannedTimepointId` and `plannedVisitId`.
- **LLM Output Truncation**: The pipeline uses the maximum allowed tokens for completions, but very large protocols may still require splitting.
- **Mapping Issues**: Regenerate `soa_entity_mapping.json` anytime the Excel mapping changes.
- **Validation**: All outputs are validated against both the mapping and USDM schema. Warnings are issued for missing or non-conformant fields.

## Streamlit SoA Viewer & Audit
- `soa_streamlit_viewer.py` provides an interactive web-based interface for visualizing and reviewing SoA extraction results.
- **How to launch:**
  ```bash
  streamlit run soa_streamlit_viewer.py
  ```
- The viewer allows you to:
  - Load and inspect `soa_text.json`, `soa_vision.json`, `soa_final.json`, or any other SoA output file.
  - Browse entities, activities, and timepoints in a user-friendly format.
  - See which timepoints were dropped or merged during processing (if any) and review the audit report.
  - Quickly identify extraction issues or missing data.
- Useful for quality control, annotation, and sharing results with non-technical stakeholders.

## Notes
- The workflow is fully automated and robust to both text-based and image-based PDFs.
- For best results, use GPT-o-3 or a model with vision capabilities for image-based adjudication.
- Defensive error handling: if the LLM output is empty or invalid, raw output is saved to `llm_raw_output.txt` (and cleaned to `llm_cleaned_output.txt` if needed) for debugging.
- Prompts instruct the LLM to use table headers exactly as they appear in the protocol as timepoint labels (no canonicalization), and to output only valid JSON. A `table_headers` array is included for traceability.
- CORE rule validation is currently a stub; integrate your rule set as needed.
- Deprecated scripts are in the `deprecated/` folder and should not be used in production.

## License
None. Contact author for permission to use.

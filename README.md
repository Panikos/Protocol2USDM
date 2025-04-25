# Protocol2USDMv3

## Overview
Protocol2USDMv3 is an automated pipeline for extracting, validating, and structuring the Schedule of Activities (SoA) from clinical trial protocol PDFs, outputting data conformant to the USDM v4.0 model. The workflow combines LLM text and vision extraction, robust validation, and advanced mapping/regeneration tools for maximum reliability.

## Key Features
- **Automated SoA Extraction**: Extracts SoA tables from protocol PDFs using both LLM text and vision analysis (GPT-4o recommended).
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

You can specify which OpenAI model (e.g., `gpt-4o` or `gpt-3o`) is used for all LLM-powered pipeline steps. This works for `main.py`, `find_soa_pages.py`, and all other scripts in the pipeline.

**Option 1: Command-line argument**
```bash
python main.py <your_protocol.pdf> --model gpt-3o
python find_soa_pages.py <your_protocol.pdf> --model gpt-3o
```

**Option 2: Environment variable**
```bash
set OPENAI_MODEL=gpt-3o  # Windows
export OPENAI_MODEL=gpt-3o  # Linux/Mac
python main.py <your_protocol.pdf>
```

If not specified, the default is `gpt-4o`.

5. Outputs:
   - `soa_text.json`: SoA extracted from PDF text.
   - `soa_vision.json`: SoA extracted from images (vision).
   - `soa_vision_fixed.json` and `soa_text_fixed.json`: Post-processed, normalized outputs.
   - `soa_final.json`: (If adjudication/merging is enabled) LLM-adjudicated, merged SoA.
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
- **GPT-4o** is recommended for both text and vision extraction.
- The pipeline automatically sets `max_tokens=16384` (the current GPT-4o completion limit).
- If you see truncation warnings, consider splitting large PDFs or reducing prompt size.

## Troubleshooting
- **KeyError: 'plannedTimepointId'**: The pipeline now skips and warns on timepoints missing both `plannedTimepointId` and `plannedVisitId`.
- **LLM Output Truncation**: The pipeline uses the maximum allowed tokens for completions, but very large protocols may still require splitting.
- **Mapping Issues**: Regenerate `soa_entity_mapping.json` anytime the Excel mapping changes.
- **Validation**: All outputs are validated against both the mapping and USDM schema. Warnings are issued for missing or non-conformant fields.

## Streamlit SoA Viewer
- `soa_streamlit_viewer.py` provides an interactive web-based interface for visualizing and reviewing SoA extraction results.
- **How to launch:**
  ```bash
  streamlit run soa_streamlit_viewer.py
  ```
- The viewer allows you to:
  - Load and inspect `soa_text.json`, `soa_vision.json`, or any other SoA output file.
  - Browse entities, activities, and timepoints in a user-friendly format.
  - Quickly identify extraction issues or missing data.
- Useful for quality control, annotation, and sharing results with non-technical stakeholders.

## Notes
- The workflow is fully automated and robust to both text-based and image-based PDFs.
- For best results, use GPT-4o or a model with vision capabilities for image-based adjudication.
- CORE rule validation is currently a stub; integrate your rule set as needed.
- Deprecated scripts are in the `deprecated/` folder and should not be used in production.

## License
None. Contact author for permission to use.

import subprocess
import sys
import os
import json
import glob
import logging
try:
    from tqdm import tqdm
except ImportError:  # Fallback when tqdm not installed
    def tqdm(iterable, **kwargs):
        return iterable
import shutil

# Configure logging
logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure all output is UTF-8 safe for Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_script(script, args=None):
    """Run a script and return (success, output)"""
    cmd = [sys.executable, script]
    if args:
        cmd.extend(args)
    try:
        # Set cwd to the directory of the main script to ensure relative paths work
        cwd = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True, cwd=cwd)
        
        # Print stderr for logging purposes, even on success
        if result.stderr:
            print(f"--- Log from {script} ---\n{result.stderr}\n--- End log ---", file=sys.stderr)

        # Print stdout for the actual output
        if result.stdout:
            print(f"[SUCCESS] {script} output:\n{result.stdout}")
        else:
            print(f"[SUCCESS] {script} completed with no output.")

        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {script} failed with exit code {e.returncode}")
        if e.stdout:
            print(f"[STDOUT]:\n{e.stdout}")
        if e.stderr:
            print(f"[STDERR]:\n{e.stderr}")
        return False, e.stdout + '\n' + (e.stderr or '')

def cleanup_outputs(output_dir):
    """Clears the output directory before a new run."""
    if os.path.exists(output_dir):
        print(f"[INFO] Cleaning up output directory: {output_dir}")
        for fname in os.listdir(output_dir):
            fpath = os.path.join(output_dir, fname)
            try:
                if os.path.isfile(fpath) or os.path.islink(fpath):
                    os.unlink(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
            except Exception as e:
                print(f'[WARN] Failed to delete {fpath}. Reason: {e}')

def run_struct_validation(json_path, step_label, summary_data):
    """Run structural linkage validator and append result to summary_data."""
    print(f"\n[VALIDATE] {step_label} – parent/child linkage check...")
    success, _ = run_script("validate_soa_structure.py", [json_path])
    summary_data.append({
        "step": f"{step_label} Link Validation",
        "inputs": [json_path],
        "outputs": [],
        "status": "Success" if success else "Failed"
    })
    if not success:
        raise RuntimeError(f"{step_label} linkage validation failed.")


def print_summary(summary_data):
    """Prints a formatted summary of the pipeline execution."""
    print("\n" + "="*80)
    print("PIPELINE EXECUTION SUMMARY".center(80))
    print("="*80)
    for item in summary_data:
        status = item.get('status', 'Unknown')
        step = item.get('step', 'Unnamed Step')
        inputs = ', '.join(item.get('inputs', []))
        outputs = ', '.join(item.get('outputs', []))
        
        print(f"| Step:   {step:<68} |")
        print(f"| Status: {status:<68} |")
        if inputs:
            print(f"| Inputs: {inputs:<68} |")
        if outputs:
            print(f"| Outputs: {outputs:<67} |")
        print("-"*80)

# Default model preference (can be overridden via --model)
MODEL_NAME = 'gemini-2.5-pro'

def process_single_pdf(pdf_path, model_name):
    logger.info("Processing %s ...", pdf_path)
    global MODEL_NAME
    MODEL_NAME = model_name  # Override global model name for this run
    # Propagate model choice to downstream subprocesses via environment variable used in helper defaults
    os.environ['OPENAI_MODEL'] = MODEL_NAME
    PDF_PATH = pdf_path  # Retain legacy variable name for minimal diff
    
    
    
    

    
    protocol_name = os.path.splitext(os.path.basename(PDF_PATH))[0]
    OUTPUT_DIR = os.path.join("output", protocol_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    PATHS = {
        "prompt": os.path.join(OUTPUT_DIR, "1_llm_prompt.txt"),
        "soa_pages": os.path.join(OUTPUT_DIR, "2_soa_pages.json"),
        "images_dir": os.path.join(OUTPUT_DIR, "3_soa_images"),
        "header_structure": os.path.join(OUTPUT_DIR, "4_soa_header_structure.json"),
        "raw_text": os.path.join(OUTPUT_DIR, "5_raw_text_soa.json"),
        "raw_vision": os.path.join(OUTPUT_DIR, "6_raw_vision_soa.json"),
        "postprocessed_text": os.path.join(OUTPUT_DIR, "7_postprocessed_text_soa.json"),
        "postprocessed_vision": os.path.join(OUTPUT_DIR, "8_postprocessed_vision_soa.json"),
        "final_soa": os.path.join(OUTPUT_DIR, "9_reconciled_soa.json"),
    }
    os.makedirs(PATHS["images_dir"], exist_ok=True)

    summary_data = []

    try:
        cleanup_outputs(OUTPUT_DIR)

        # Initialize status flags
        text_soa_ok = False
        vision_soa_ok = False

        # Step 1: Generate Prompt
        step1_info = {"step": "1. Generate LLM Prompt", "inputs": ["soa_entity_mapping.json"], "outputs": [PATHS["prompt"]]}
        print("\n[STEP 1] Generating up-to-date LLM prompt from mapping...")
        success, _ = run_script("generate_soa_llm_prompt.py", ["--output", PATHS["prompt"]])
        step1_info["status"] = "Success" if success else "Failed"
        summary_data.append(step1_info)
        if not success: raise RuntimeError("Prompt generation failed.")

        # Step 2: Find SoA Pages
        step2_info = {"step": "2. Find SoA Pages", "inputs": [PDF_PATH, PATHS["prompt"]], "outputs": [PATHS["soa_pages"]]}
        print("\n[STEP 2] Finding SoA pages...")
        # The updated script prints comma-separated page indices to stdout
        success, output = run_script("find_soa_pages.py", ["--pdf-path", PDF_PATH, "--model", MODEL_NAME, "--prompt-file", PATHS["prompt"]])
        if success:
            try:
                # Parse the output and save to the JSON file for subsequent steps
                page_indices = [int(p) for p in output.strip().split(',') if p.strip()]
                if not page_indices:
                    print("[WARN] find_soa_pages.py ran successfully but found no SoA pages.")
                    # Write an empty list to the file to allow graceful handling downstream
                    with open(PATHS["soa_pages"], 'w') as f:
                        json.dump({"soa_pages": []}, f)
                else:
                    with open(PATHS["soa_pages"], 'w') as f:
                        json.dump({"soa_pages": page_indices}, f)
                step2_info["status"] = "Success"
            except (ValueError, IndexError) as e:
                print(f"[ERROR] Failed to parse output from find_soa_pages.py: {e}")
                print(f"[RAW_OUTPUT]:\n{output}")
                success = False
                step2_info["status"] = "Failed"
        else:
            step2_info["status"] = "Failed"
        
        summary_data.append(step2_info)
        if not success: raise RuntimeError("Find SoA pages failed.")

        # Step 3: Extract PDF pages as images
        step3_info = {"step": "3. Extract SoA Images", "inputs": [PDF_PATH, PATHS["soa_pages"]], "outputs": [PATHS["images_dir"]]}
        print("\n[STEP 3] Extracting SoA pages as images...")
        success, _ = run_script("extract_pdf_pages_as_images.py", [PDF_PATH, "--pages-file", PATHS["soa_pages"], "--output-dir", PATHS["images_dir"]])
        step3_info["status"] = "Success" if success else "Failed"
        summary_data.append(step3_info)
        if not success: raise RuntimeError("Image extraction failed.")

        # Step 4: Analyze SoA Header Structure
        step4_info = {"step": "4. Analyze SoA Header", "inputs": [PATHS["images_dir"]], "outputs": [PATHS["header_structure"]]}
        print("\n[STEP 4] Analyzing SoA header structure from images...")
        # Corrected script name from analyze_soa_header.py to analyze_soa_structure.py
        success, _ = run_script("analyze_soa_structure.py", ["--images-dir", PATHS["images_dir"], "--output", PATHS["header_structure"], "--model", MODEL_NAME])
        step4_info["status"] = "Success" if success else "Failed"
        summary_data.append(step4_info)
        if not success: raise RuntimeError("Header analysis failed.")

        # Step 5: Text-based Extraction
        step5_info = {"step": "5. Extract SoA from Text", "inputs": [PDF_PATH, PATHS["prompt"]], "outputs": [PATHS["raw_text"]]}
        print("\n[STEP 5] Extracting SoA from PDF text...")
        text_args = [
            "--pdf-path", PDF_PATH,
            "--output", PATHS["raw_text"],
            "--model", MODEL_NAME,
            "--prompt-file", PATHS["prompt"],
            "--header-structure-file", PATHS["header_structure"],
            "--soa-pages-file", PATHS["soa_pages"]
        ]
        success, _ = run_script("send_pdf_to_llm.py", text_args)
        text_soa_ok = success
        step5_info["status"] = "Success" if text_soa_ok else "Failed"
        summary_data.append(step5_info)
        if text_soa_ok:
            run_struct_validation(PATHS["raw_text"], "Step 5 Raw Text", summary_data)
        print(f"[DEBUG] Status of text_soa_ok after Step 5: {text_soa_ok}")

        # Step 6: Vision-based Extraction
        step6_info = {"step": "6. Vision Extraction", "inputs": [PATHS["images_dir"], PATHS["prompt"], PATHS["header_structure"]], "outputs": [PATHS["raw_vision"]]}
        print("\n[STEP 6] Extracting SoA from images...")
        vision_args = [
            "--images-dir", PATHS["images_dir"],
            "--output", PATHS["raw_vision"],
            "--model", MODEL_NAME,
            "--prompt-file", PATHS["prompt"],
            "--header-structure-file", PATHS["header_structure"]
        ]
        vision_soa_ok, _ = run_script("vision_extract_soa.py", vision_args)
        step6_info["status"] = "Success" if vision_soa_ok else "Failed"
        summary_data.append(step6_info)
        if vision_soa_ok:
            run_struct_validation(PATHS["raw_vision"], "Step 6 Raw Vision", summary_data)
        if not vision_soa_ok: raise RuntimeError("Vision SoA extraction failed.")

        # Step 7: Text Post-processing
        print(f"[DEBUG] Checking text_soa_ok before Step 7: {text_soa_ok}")
        step7_info = {"step": "7. Post-process Text SoA", "inputs": [PATHS["raw_text"]], "outputs": [PATHS["postprocessed_text"]]}
        if text_soa_ok:
            print("\n[STEP 7] Consolidating and normalizing text output...")
            success, _ = run_script("soa_postprocess_consolidated.py", [PATHS["raw_text"], PATHS["postprocessed_text"], PATHS["header_structure"]])
            # Validate against header structure
            if success:
                run_script("soa_validate_header.py", ["--soa-file", PATHS["postprocessed_text"], "--header-structure", PATHS["header_structure"], "--output", PATHS["postprocessed_text"]])
            step7_info["status"] = "Success" if success else "Warning (Failed)"
        else:
            step7_info["status"] = "Skipped"
        summary_data.append(step7_info)
        if text_soa_ok and step7_info["status"] == "Success":
            run_struct_validation(PATHS["postprocessed_text"], "Step 7 Postprocessed Text", summary_data)

        # Step 8: Vision Post-processing
        step8_info = {"step": "8. Post-process Vision SoA", "inputs": [PATHS["raw_vision"]], "outputs": [PATHS["postprocessed_vision"]]}
        if vision_soa_ok:
            print("\n[STEP 8] Consolidating and normalizing vision output...")
            success, _ = run_script("soa_postprocess_consolidated.py", [PATHS["raw_vision"], PATHS["postprocessed_vision"], PATHS["header_structure"]])
            if success:
                run_script("soa_validate_header.py", ["--soa-file", PATHS["postprocessed_vision"], "--header-structure", PATHS["header_structure"], "--output", PATHS["postprocessed_vision"]])
            step8_info["status"] = "Success" if success else "Failed"
        else:
            step8_info["status"] = "Skipped"
        summary_data.append(step8_info)
        if vision_soa_ok and step8_info["status"] == "Success":
            run_struct_validation(PATHS["postprocessed_vision"], "Step 8 Postprocessed Vision", summary_data)
        if step8_info["status"] == "Failed": raise RuntimeError("Vision SoA post-processing failed.")

        # Step 9: Reconciliation
        step9_inputs = [PATHS["postprocessed_vision"], PATHS["postprocessed_text"]]
        step9_info = {"step": "9. LLM Reconciliation", "inputs": step9_inputs, "outputs": [PATHS["final_soa"]]}
        
        if os.path.exists(PATHS["postprocessed_vision"]) and os.path.exists(PATHS["postprocessed_text"]):
            print("\n[STEP 9] LLM-based reconciliation...")
            reconciliation_args = [
                "--output", PATHS["final_soa"], 
                "--model", MODEL_NAME,
                "--vision-input", PATHS["postprocessed_vision"],
                "--text-input", PATHS["postprocessed_text"]
            ]
            success, _ = run_script("reconcile_soa_llm.py", reconciliation_args)
            step9_info["status"] = "Success" if success else "Failed"
        else:
            print("\n[STEP 9] Skipping LLM-based reconciliation... One or both inputs missing.")
            if os.path.exists(PATHS["postprocessed_vision"]):
                # Copy vision file but preserve provenance from text if available
                try:
                    with open(PATHS["postprocessed_vision"], "r", encoding="utf-8") as vf:
                        vision_data = json.load(vf)
                    with open(PATHS["postprocessed_text"], "r", encoding="utf-8") as tf:
                        text_data = json.load(tf)
                    if isinstance(vision_data, dict) and isinstance(text_data, dict):
                        if 'p2uProvenance' not in vision_data and 'p2uProvenance' in text_data:
                            vision_data['p2uProvenance'] = text_data['p2uProvenance']
                        # Also copy other meta keys that drive viewer features
                        for _meta in (
                            'p2uOrphans',
                            'p2uGroupConflicts',
                            'p2uTimelineOrderIssues',
                        ):
                            if _meta not in vision_data and _meta in text_data:
                                vision_data[_meta] = text_data[_meta]
                    with open(PATHS["final_soa"], "w", encoding="utf-8") as out_f:
                        json.dump(vision_data, out_f, indent=2, ensure_ascii=False)
                except Exception as e:
                    # Fallback to simple copy if anything goes wrong
                    shutil.copy(PATHS["postprocessed_vision"], PATHS["final_soa"])
                    print(f"[WARN] Enhanced copy failed, used simple copy: {e}")
                step9_info["status"] = "Skipped (Used Vision)"
                success = True
            else:
                step9_info["status"] = "Skipped (No Inputs)"
                success = False
        summary_data.append(step9_info)
        if step9_info["status"] == "Success":
            run_struct_validation(PATHS["final_soa"], "Step 9 Reconciled", summary_data)
        if not success: raise RuntimeError("LLM reconciliation failed or was skipped.")

        # Step 10: Final Validation
        step10_info = {"step": "10. Final Validation", "inputs": [PATHS["final_soa"]], "outputs": []}
        print("\n[STEP 10] Final validation...")
        success, _ = run_script("validate_usdm_schema.py", [PATHS["final_soa"], "Wrapper-Input"])
        step10_info["status"] = "Success" if success else "Failed"
        summary_data.append(step10_info)
        if not success: raise RuntimeError("Final SoA validation failed.")

        print("\n[ALL STEPS COMPLETE]")
        print(f"\n[INFO] Final output available at: {PATHS['final_soa']}")
        print("\n[INFO] Launching interactive SoA review UI (Streamlit)...")
        subprocess.Popen([sys.executable, "-m", "streamlit", "run", "soa_streamlit_viewer.py", "--", PATHS["final_soa"]], encoding="utf-8")
        print("[INFO] Visit http://localhost:8501 in your browser to review the SoA.")

    except (RuntimeError, Exception) as e:
        print(f"\n[FATAL] Pipeline execution halted: {e}")
        if summary_data and summary_data[-1]['status'] not in ['Failed', 'Warning (Failed)', 'Skipped']:
             summary_data[-1]['status'] = 'Failed'

    finally:
        print_summary(summary_data)
        if any(s.get('status') == 'Failed' for s in summary_data):
            print("\n[FATAL] Pipeline finished with one or more failed steps.")
            sys.exit(1)

def main():
    import argparse, pathlib
    parser = argparse.ArgumentParser(description="Run the SoA extraction pipeline on one or more PDFs or directories.")
    parser.add_argument("inputs", nargs="+", help="PDF file(s) or directory(ies) containing PDFs")
    parser.add_argument("--model", default=MODEL_NAME, help="LLM model to use (default: gemini-2.5-pro)")
    args = parser.parse_args()

    pdf_list = []
    for p in args.inputs:
        abs_p = os.path.abspath(p)
        if os.path.isdir(abs_p):
            pdf_list.extend([str(pathlib.Path(abs_p)/f) for f in os.listdir(abs_p) if f.lower().endswith('.pdf')])
        else:
            pdf_list.append(abs_p)

    if not pdf_list:
        logger.error("No PDF files found in the supplied inputs.")
        sys.exit(1)

    for pdf in tqdm(pdf_list, desc="Processing PDFs"):
        try:
            process_single_pdf(pdf, args.model)
        except Exception as e:
            logger.error("Pipeline failed for %s: %s", pdf, e)

if __name__ == "__main__":
    main()

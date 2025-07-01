import subprocess
import sys
import os
import json

# Ensure all output is UTF-8 safe for Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_script(script, args=None):
    """Run a script and return (success, output)"""
    cmd = [sys.executable, script]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        try:
            print(f"[SUCCESS] {script} output:\n{result.stdout}")
        except UnicodeEncodeError:
            print(f"[SUCCESS] {script} output (UTF-8 chars replaced):\n{result.stdout.encode('utf-8', errors='replace').decode('utf-8')}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {script} failed with exit code {e.returncode}")
        if e.stdout:
            print(f"[STDOUT]:\n{e.stdout}")
        if e.stderr:
            print(f"[STDERR]:\n{e.stderr}")
        return False, e.stdout + '\n' + (e.stderr or '')


import glob
import shutil
import subprocess

def cleanup_outputs():
    # Delete all .json files except requirements.json and soa_entity_mapping.json
    for f in glob.glob('*.json'):
        if f not in ['requirements.json', 'soa_entity_mapping.json']:
            try:
                os.remove(f)
            except Exception as e:
                print(f"[WARN] Could not delete {f}: {e}")
    # Clear soa_images directory
    img_dir = 'soa_images'
    if os.path.exists(img_dir):
        for fname in os.listdir(img_dir):
            fpath = os.path.join(img_dir, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
            except Exception as e:
                print(f"[WARN] Could not delete {fpath}: {e}")


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

MODEL_NAME = 'gpt-4o'

def main():
    global MODEL_NAME
    import argparse
    parser = argparse.ArgumentParser(description="Run the SoA extraction pipeline.")
    parser.add_argument("pdf_path", help="Path to the protocol PDF")
    parser.add_argument("--model", default=MODEL_NAME, help="OpenAI model to use (default: gpt-4o)")
    parser.add_argument("--batch-size", type=int, default=None, help="Images per vision-model batch (default: all)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker threads for vision batches")
    args = parser.parse_args()
    MODEL_NAME = args.model
    PDF_PATH = os.path.abspath(args.pdf_path)
    SOA_IMAGES_DIR = "./soa_images"
    summary_data = []

    try:
        cleanup_outputs()

        # Step 1: Text Extraction
        step1_info = {"step": "1. Text Extraction", "inputs": [PDF_PATH], "outputs": ["STEP1_soa_text.json"]}
        print("\n[STEP 1] Extracting SoA from PDF text...")
        success, output = run_script("send_pdf_to_openai.py", [PDF_PATH, "--model", MODEL_NAME, "--output", "STEP1_soa_text.json"])
        if success:
            step1_info["status"] = "Success"
        else:
            step1_info["status"] = "Failed"
        summary_data.append(step1_info)
        if not success:
            raise RuntimeError("Text extraction failed.")

        # Step 2: Generate Prompt
        step2_info = {"step": "2. Generate LLM Prompt", "inputs": ["soa_entity_mapping.json"], "outputs": ["llm_soa_prompt.txt"]}
        print("\n[STEP 2] Generating up-to-date LLM prompt from mapping...")
        success, _ = run_script("generate_soa_llm_prompt.py")
        step2_info["status"] = "Success" if success else "Skipped/Failed"
        summary_data.append(step2_info)

        # Step 3: Find SoA Pages
        step3_info = {"step": "3. Find SoA Pages", "inputs": [PDF_PATH]}
        print("\n[STEP 3] Identifying SOA pages in PDF...")
        success, output = run_script("find_soa_pages.py", [PDF_PATH, "--model", MODEL_NAME])
        page_str = ""
        if success:
            try:
                page_str = output.strip().split('\n')[-1]
                page_numbers = [int(p.strip()) for p in page_str.split(',') if p.strip().isdigit()]
                if not page_numbers: raise ValueError("No valid page numbers found.")
                print(f"[INFO] Found SoA on pages: {page_numbers}")
                step3_info["status"] = "Success"
                step3_info["outputs"] = [f"Page numbers: {page_str}"]
            except Exception as e:
                success = False
                print(f"[FATAL] Could not parse page numbers: {e}")
        if not success:
            step3_info["status"] = "Failed"
        summary_data.append(step3_info)
        if not success:
            raise RuntimeError("SOA page identification failed.")

        # Step 4: Extract Images
        image_paths = []
        step4_info = {"step": "4. Extract Images", "inputs": [PDF_PATH], "outputs": [], "status": "Skipped"}
        if page_numbers:
            print("\n[STEP 4] Extracting SoA pages as images...")
            os.makedirs(SOA_IMAGES_DIR, exist_ok=True)
            # Pass pages as individual arguments
            page_args = [str(p) for p in page_numbers]
            success, img_output = run_script("extract_pdf_pages_as_images.py", [PDF_PATH, "--outdir", SOA_IMAGES_DIR, "--pages"] + page_args)
            if success:
                # Parse the output to find the generated image files
                image_paths = [line.split(" ")[-1] for line in img_output.strip().split('\n') if "Extracted page" in line]
                step4_info["outputs"] = [os.path.basename(f) for f in image_paths]
                step4_info["status"] = "Success"
            else:
                step4_info["status"] = "Failed"
            summary_data.append(step4_info)
            if not success:
                raise RuntimeError("Image extraction failed.")

        # Step 5: Vision Extraction
        step5_info = {"step": "5. Vision Extraction", "inputs": image_paths + ["llm_soa_prompt.txt"], "outputs": ["STEP2_soa_vision.json"]}
        print("\n[STEP 5] Extracting SoA from images using vision model...")
        vision_args = image_paths + ["--model", MODEL_NAME, "--output", "STEP2_soa_vision.json", "--prompt-file", "llm_soa_prompt.txt"]
        if args.batch_size is not None:
            vision_args += ["--batch-size", str(args.batch_size)]
        vision_args += ["--workers", str(args.workers)]
        success, _ = run_script("vision_extract_soa.py", vision_args)
        if success:
            step5_info["status"] = "Success"
        else:
            step5_info["status"] = "Failed"
        summary_data.append(step5_info)
        if not success:
            raise RuntimeError("Vision extraction failed.")

        # Step 6: Post-process Vision
        step6_info = {"step": "6. Post-process & Validate Vision SoA", "inputs": ["STEP2_soa_vision.json"], "outputs": ["STEP3_soa_vision_fixed.json"]}
        print("\n[STEP 6] Consolidating and normalizing vision output...")
        success, _ = run_script("soa_postprocess_consolidated.py", ["STEP2_soa_vision.json", "STEP3_soa_vision_fixed.json"])
        if not success:
            step6_info["status"] = "Failed (Post-process)"
            summary_data.append(step6_info)
            raise RuntimeError("Vision SoA post-processing failed.")
        
        success, _ = run_script("soa_extraction_validator.py", ["STEP3_soa_vision_fixed.json"])
        if not success:
            step6_info["status"] = "Failed (Mapping Validation)"
            summary_data.append(step6_info)
            raise RuntimeError("Vision SoA mapping validation failed.")
            
        success, _ = run_script("validate_usdm_schema.py", ["STEP3_soa_vision_fixed.json", "Wrapper-Input"])
        if not success:
            step6_info["status"] = "Failed (Schema Validation)"
            summary_data.append(step6_info)
            raise RuntimeError("Vision SoA schema validation failed.")
        step6_info["status"] = "Success"
        summary_data.append(step6_info)

        # Step 7: Post-process Text
        step7_info = {"step": "7. Post-process & Validate Text SoA", "inputs": ["STEP1_soa_text.json"], "outputs": ["STEP4_soa_text_fixed.json"], "status": "Skipped"}
        if os.path.exists("STEP1_soa_text.json"):
            print("\n[STEP 7] Consolidating and normalizing text output...")
            success, _ = run_script("soa_postprocess_consolidated.py", ["STEP1_soa_text.json", "STEP4_soa_text_fixed.json"])
            if success:
                success, _ = run_script("soa_extraction_validator.py", ["STEP4_soa_text_fixed.json"])
                if success:
                    success, _ = run_script("validate_usdm_schema.py", ["STEP4_soa_text_fixed.json", "Wrapper-Input"])
                    if success:
                        step7_info["status"] = "Success"
                    else:
                        step7_info["status"] = "Warning (Schema Validation Failed)"
                else:
                    step7_info["status"] = "Warning (Mapping Validation Failed)"
            else:
                step7_info["status"] = "Warning (Post-process Failed)"
        summary_data.append(step7_info)

        # Step 8: Reconciliation
        step8_inputs = ["STEP3_soa_vision_fixed.json"]
        if os.path.exists("STEP4_soa_text_fixed.json"):
            step8_inputs.append("STEP4_soa_text_fixed.json")
        step8_info = {"step": "8. LLM Reconciliation", "inputs": step8_inputs, "outputs": ["STEP5_soa_final.json"]}
        print("\n[STEP 8] LLM-based reconciliation...")
        reconciliation_args = ["--vision", "STEP3_soa_vision_fixed.json", "--output", "STEP5_soa_final.json", "--model", MODEL_NAME]
        if os.path.exists("STEP4_soa_text_fixed.json"):
            reconciliation_args.extend(["--text", "STEP4_soa_text_fixed.json"])
        success, _ = run_script("reconcile_soa_llm.py", reconciliation_args)
        if success:
            step8_info["status"] = "Success"
        else:
            step8_info["status"] = "Failed"
        summary_data.append(step8_info)
        if not success:
            raise RuntimeError("LLM reconciliation failed.")

        # Step 9: Final Validation
        step9_info = {"step": "9. Final Validation", "inputs": ["STEP5_soa_final.json"], "outputs": []}
        print("\n[STEP 9] Final validation...")
        success, _ = run_script("validate_usdm_schema.py", ["STEP5_soa_final.json", "Wrapper-Input"])
        if success:
            step9_info["status"] = "Success"
        else:
            step9_info["status"] = "Failed"
        summary_data.append(step9_info)
        if not success:
            raise RuntimeError("Final SoA validation failed.")

        print("\n[ALL STEPS COMPLETE]")
        # Launch Streamlit SoA reviewer with final output
        print("\n[INFO] Launching interactive SoA review UI (Streamlit)...")
        subprocess.Popen(["streamlit", "run", "soa_streamlit_viewer.py"], encoding="utf-8")
        print("[INFO] Visit http://localhost:8501 in your browser to review the SoA.")

    except (RuntimeError, Exception) as e:
        print(f"\n[FATAL] Pipeline execution halted: {e}")
        # Ensure the last failed step is marked as failed if it wasn't already
        if summary_data and summary_data[-1]['status'] not in ['Failed', 'Warning']:
             summary_data[-1]['status'] = 'Failed'

    finally:
        print_summary(summary_data)

if __name__ == "__main__":
    main()

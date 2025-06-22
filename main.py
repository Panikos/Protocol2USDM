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
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        try:
            print(f"[ERROR] {script} failed:\n{e.stderr}")
        except UnicodeEncodeError:
            print(f"[ERROR] {script} failed (UTF-8 chars replaced):\n{e.stderr.encode('utf-8', errors='replace').decode('utf-8')}")
        return False, e.stderr


import glob
import shutil
import subprocess

def cleanup_outputs():
    # Delete all .json files except requirements.json
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


MODEL_NAME = 'gpt-4o'

def main():
    global MODEL_NAME
    import argparse
    parser = argparse.ArgumentParser(description="Run the SoA extraction pipeline.")
    parser.add_argument("pdf_path", help="Path to the protocol PDF")
    parser.add_argument("--model", default=MODEL_NAME, help="OpenAI model to use (default: gpt-4o)")
    args = parser.parse_args()
    MODEL_NAME = args.model
    PDF_PATH = args.pdf_path
    SOA_IMAGES_DIR = "./soa_images"
    # Cleanup outputs before starting
    cleanup_outputs()

    # 1. Extract SoA from text (PDF)
    print("\n[STEP 1] Extracting SoA from PDF text...")
    print("[INFO] INPUT: PDF file:", PDF_PATH)
    print("[INFO] OUTPUT: STEP1_soa_text.json")
    success, output = run_script("send_pdf_to_openai.py")
    actual_model = None
    if output:
        for line in output.splitlines():
            if line.startswith('[ACTUAL_MODEL_USED]'):
                actual_model = line.split(']', 1)[-1].strip()
                break
    if actual_model:
        print(f"[INFO] Actual OpenAI model used: {actual_model}")
    else:
        print("[WARNING] Could not determine actual model used from send_pdf_to_openai.py output.")
    if not success:
        print("[FATAL] Text extraction failed. Aborting.")
        return

    # 2. (Optional) Regenerate LLM prompt from mapping
    print("\n[STEP 2] Generating up-to-date LLM prompt from mapping...")
    print("[INFO] INPUT: soa_entity_mapping.json")
    print("[INFO] OUTPUT: llm_soa_prompt.txt")
    run_script("generate_soa_llm_prompt.py")

    # 3. Find SOA pages
    print("\n[STEP 3] Identifying SOA pages in PDF...")
    print("[INFO] INPUT: PDF file:", PDF_PATH)
    result = subprocess.run([sys.executable, "find_soa_pages.py", PDF_PATH], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("[FATAL] SOA page identification failed:", result.stderr)
        return
    if result.stdout is not None:
        page_line = result.stdout.strip().split("\n")[-1]
    else:
        print("[ERROR] No output from find_soa_pages.py subprocess.")
        return
    if not page_line or not any(x.isdigit() for x in page_line.split(",")):
        print("[FATAL] No SOA pages found.")
        return
    soa_pages = [int(x) for x in page_line.split(",") if x.strip().isdigit()]
    print(f"[INFO] SOA pages: {soa_pages}")

    # 4. Extract those pages as images
    print("\n[STEP 4] Extracting SOA pages as images...")
    print("[INFO] INPUT: PDF file:", PDF_PATH)
    print("[INFO] OUTPUT: ./soa_images/soa_page_*.png")
    page_str = ",".join(str(p) for p in soa_pages)
    result = subprocess.run([sys.executable, "extract_pdf_pages_as_images.py", PDF_PATH, page_str, SOA_IMAGES_DIR], capture_output=True, text=True)
    if result.returncode != 0:
        print("[FATAL] Image extraction failed:", result.stderr)
        return
    image_paths = [x for x in result.stdout.strip().split(",") if x]
    print(f"[INFO] Extracted images: {image_paths}")

    # 5. Extract SoA from images (vision)
    print("\n[STEP 5] Extracting SoA from protocol images...")
    print("[INFO] INPUT: Images:", image_paths)
    print("[INFO] OUTPUT: STEP2_soa_vision.json")
    vision_args = image_paths + ["--output", "STEP2_soa_vision.json"]
    success, _ = run_script("vision_extract_soa.py", vision_args)
    if not success:
        print("[FATAL] Vision extraction failed. Aborting.")
        return

    # 6. Postprocess and consolidate SoA vision extraction
    print("\n[STEP 6] Consolidating and normalizing STEP2_soa_vision.json...")
    print("[INFO] INPUT: STEP2_soa_vision.json")
    print("[INFO] OUTPUT: STEP3_soa_vision_fixed.json")
    success, _ = run_script("soa_postprocess_consolidated.py", ["STEP2_soa_vision.json", "STEP3_soa_vision_fixed.json"])
    if not success:
        print("[FATAL] STEP2_soa_vision.json post-processing failed. Aborting.")
        return
    print("[STEP 6b] Validating STEP3_soa_vision_fixed.json against mapping...")
    print("[INFO] INPUT: STEP3_soa_vision_fixed.json, soa_entity_mapping.json")
    success, _ = run_script("soa_extraction_validator.py", ["STEP3_soa_vision_fixed.json"])
    if not success:
        print("[FATAL] STEP3_soa_vision_fixed.json failed mapping validation. Aborting.")
        return
    print("\n[STEP 7] Consolidating and normalizing STEP1_soa_text.json...")
    print("[INFO] INPUT: STEP1_soa_text.json")
    print("[INFO] OUTPUT: STEP4_soa_text_fixed.json")
    success, _ = run_script("soa_postprocess_consolidated.py", ["STEP1_soa_text.json", "STEP4_soa_text_fixed.json"])
    if not success:
        print("[FATAL] STEP1_soa_text.json post-processing failed. Aborting.")
        return
    print("[STEP 7b] Validating STEP4_soa_text_fixed.json against mapping...")
    print("[INFO] INPUT: STEP4_soa_text_fixed.json, soa_entity_mapping.json")
    success, _ = run_script("soa_extraction_validator.py", ["STEP4_soa_text_fixed.json"])
    if not success:
        print("[FATAL] STEP4_soa_text_fixed.json failed mapping validation. Aborting.")
        return

    # 8. LLM-based reconciliation
    print("\n[STEP 8] LLM-based reconciliation of text and vision outputs...")
    print("[INFO] INPUT: STEP4_soa_text_fixed.json, STEP3_soa_vision_fixed.json")
    print("[INFO] OUTPUT: STEP5_soa_final.json")
    result = subprocess.run([sys.executable, "reconcile_soa_llm.py", "--text", "STEP4_soa_text_fixed.json", "--vision", "STEP3_soa_vision_fixed.json", "--output", "STEP5_soa_final.json"], capture_output=True, text=True)
    if result.returncode != 0:
        print("[FATAL] LLM reconciliation failed:", result.stderr)
        return
    print(result.stdout)

    print("\n[ALL STEPS COMPLETE]")

    # Launch Streamlit SoA reviewer with final output
    print("\n[INFO] Launching interactive SoA review UI (Streamlit)...")
    subprocess.Popen(["streamlit", "run", "soa_streamlit_viewer.py"], encoding="utf-8")  # Non-blocking
    print("[INFO] Visit http://localhost:8501 in your browser to review the SoA.")

if __name__ == "__main__":
    main()

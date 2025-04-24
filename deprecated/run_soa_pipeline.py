import sys
import subprocess
import os

def run(cmd, check=True):
    print(f"[RUN] {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed: {cmd}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run full SoA extraction pipeline: LLM extraction, postprocess, validate.")
    parser.add_argument("image_paths", nargs="*", help="Image files for LLM extraction (optional)")
    parser.add_argument("--input_json", help="Existing SoA JSON to process (optional)")
    parser.add_argument("--output", default="soa_final.json", help="Final output file")
    args = parser.parse_args()

    # Step 1: LLM extraction (if images provided)
    if args.image_paths:
        img_args = ' '.join(args.image_paths)
        run(f"python vision_extract_soa.py {img_args} --output soa_llm.json")
        input_json = "soa_llm.json"
    elif args.input_json:
        input_json = args.input_json
    else:
        print("[ERROR] Must provide either image_paths or --input_json")
        sys.exit(1)

    # Step 2: Postprocess/normalize
    run(f"python soa_postprocess_consolidated.py {input_json} soa_post.json")

    # Step 3: Mapping-based validation
    run(f"python soa_extraction_validator.py soa_post.json")

    # Step 4: OpenAPI schema validation (optional, if schema and validator available)
    if os.path.exists("validate_usdm_json.py"):
        run(f"python validate_usdm_json.py 'USDM OpenAPI schema/USDM_API.json' soa_post.json", check=False)

    # Step 5: Copy to final output
    os.replace("soa_post.json", args.output)
    print(f"[PIPELINE SUCCESS] Final validated SoA written to {args.output}")

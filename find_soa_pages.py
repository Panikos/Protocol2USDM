import os
import sys
import json
import base64
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import fitz  # PyMuPDF
import textwrap
from openai import OpenAI
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIG ---
KEYWORDS = [
    "schedule of activities",
    "soa",
    "assessment schedule",
    "visit schedule",
    "study calendar",
    "assessment table",
    "timing of procedures",
    "time and events",
    "table of assessments",
    "Schedule of Events"
]
KEYWORDS = [k.lower() for k in KEYWORDS]

# --- ENV SETUP ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

google_api_key = os.environ.get("GOOGLE_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)

# --- FUNCTIONS ---
def extract_page_texts(pdf_path):
    doc = fitz.open(pdf_path)
    return [page.get_text() for page in doc]

def keyword_filter(page_texts):
    candidates = []
    for i, text in enumerate(page_texts):
        text_lc = text.lower()
        if any(kw in text_lc for kw in KEYWORDS):
            candidates.append(i)
    return candidates

import time

def llm_is_soa_page(page_text, model, prompt_content):
    """Asks the LLM if a page contains SoA content, using the main prompt for context."""
    unique_run_id = f"RunID:{time.time()}"
    
    if prompt_content:
        system_prompt = textwrap.dedent(f"""
            You are an expert document analysis assistant for clinical trial protocols. Your task is to determine if the provided text from a single page contains the primary 'Schedule of Activities' (SoA) table.

            **CRITICAL INSTRUCTIONS:**
            1.  The SoA is a specific, detailed table, often spanning multiple pages, that lists study visits, timepoints, and all procedures performed at each visit.
            2.  You MUST respond 'yes' if the page contains the title 'Schedule of Activities' (or similar) and the beginning of the main SoA table, or if it contains a clear continuation of that table from a previous page. The page must show a tabular structure with rows and columns for visits and procedures.
            3.  You MUST respond 'no' if the page only contains mentions of activities, a list of abbreviations, a table of contents, a list of figures, or general descriptions of the study design.
            4.  A page that only MENTIONS 'Schedule of Activities' but does not SHOW the actual table is NOT the SoA table. You must respond 'no'.
            5.  Footnotes or definitions pages are NOT the SoA table itself. You must respond 'no'.
            6.  Your response MUST be a single word: 'yes' or 'no'. Do not provide any other explanation.

            Here is the schema context for the key SoA-related entities, which may appear in the table:
            ---
            {prompt_content}
            ---
        """)
    else: # Fallback to the old prompt if no context is provided
        system_prompt = textwrap.dedent("""
            You are a text classification assistant. Your only task is to determine if the text from a clinical trial protocol page contains the 'Schedule of Activities' (SoA).
            The SoA can be a table, a title, or a header.
            IMPORTANT: A 'Table of Contents' page is NOT a Schedule of Activities, even if it lists the SoA as a section. If the page is a Table of Contents, respond 'no'.
            If the text contains 'Schedule of Activities', 'SoA', 'Schedule of Events', or a similar title, OR if it contains a table with visits, timepoints, and medical procedures, you must respond 'yes'.
            Otherwise, respond 'no'.
            Your response must be a single word: 'yes' or 'no'.
        """)

    user_content = f"Page Text:\n{textwrap.shorten(page_text, width=12000)}\n{unique_run_id}"
    
    params = dict(model=model, messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ])

    if model != "o3":
        params["temperature"] = 0
    if model in ['o3', 'o3-mini', 'o3-mini-high']:
        params['max_completion_tokens'] = 5
    else:
        params['max_tokens'] = 5

    print(f"[DEBUG] Sending request to {model} for page adjudication...", file=sys.stderr)
    try:
        if 'gemini' in model.lower():
            if not google_api_key:
                raise ValueError("GOOGLE_API_KEY not set for Gemini model")
            gemini_model = genai.GenerativeModel(model)
            full_prompt = f"{params['messages'][0]['content']}\n\n{params['messages'][1]['content']}"
            response = gemini_model.generate_content(full_prompt)
            answer = response.text.strip().lower()
        else:
            response = openai_client.chat.completions.create(**params)
            answer = response.choices[0].message.content.strip().lower()
        
        print(f"[DEBUG] Received response from {model}.", file=sys.stderr)
        return answer.startswith('yes')
    except Exception as e:
        print(f"[ERROR] LLM API call failed: {e}", file=sys.stderr)
        return False

def llm_is_soa_page_image(pdf_path, page_num, model):
    """Send image of a PDF page to a vision API and ask if it contains the SOA table."""
    import tempfile
    import fitz
    import time
    import uuid
    import mimetypes
    from pathlib import Path

    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=200)
    
    # Create a temporary file to save the image
    tmp_path = os.path.join(tempfile.gettempdir(), f"soa_page_{uuid.uuid4().hex}.png")
    try:
        pix.save(tmp_path)
        image_path = tmp_path
    except Exception as e:
        print(f"[FATAL] Could not create/save temp PNG for LLM vision adjudication: {e}", file=sys.stderr)
        return False

    unique_run_id = f"RunID:{time.time()}"
    system_prompt = (
        "You are an expert visual analysis assistant for clinical trial documents. Your task is to determine if the provided image of a single page contains the primary 'Schedule of Activities' (SoA) table.\n"
        "**CRITICAL VISUAL INSTRUCTIONS:**\n"
        "1.  The SoA is a specific, detailed **grid-like table**, often spanning multiple pages. It has columns for visits/timepoints and rows for specific medical procedures.\n"
        "2.  You MUST respond 'yes' ONLY if the image shows this characteristic grid structure. Look for a table with headers like 'Visit', 'Week', 'Day', and a list of procedures like 'Physical Exam', 'Blood Sample', 'ECG'.\n"
        "3.  You MUST respond 'no' if the image shows a flowchart, a study design schematic, a list of objectives, a table of contents, or any other diagram that is not the main SoA grid.\n"
        "4.  A page that only MENTIONS 'Schedule of Activities' in text but does not SHOW the actual table grid is NOT the SoA. You must respond 'no'.\n"
        "5.  Your response MUST be a single word: 'yes' or 'no'. Do not provide any other explanation.\n"
        f"RunID: {unique_run_id}"
    )

    answer = ""
    try:
        if 'gemini' in model.lower():
            gemini_model = genai.GenerativeModel(model)
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image'):
                 print(f"[ERROR] Invalid mime type for image {image_path}", file=sys.stderr)
                 return False
            image_part = {'mime_type': mime_type, 'data': Path(image_path).read_bytes()}
            response = gemini_model.generate_content([system_prompt, image_part])
            answer = response.text.strip().lower()
        else:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            with open(image_path, 'rb') as imgf:
                img_b64 = base64.b64encode(imgf.read()).decode('utf-8')
            image_url = f"data:image/png;base64,{img_b64}"
            
            params = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "detail": "low"},
                            },
                        ],
                    }
                ],
                max_tokens=5,
                temperature=0
            )
            response = client.chat.completions.create(**params)
            answer = response.choices[0].message.content.strip().lower()

    except Exception as e:
        print(f"[ERROR] LLM API call failed: {e}", file=sys.stderr)
        answer = "no" # Default to no on error to avoid false positives
    finally:
        # Cleanup the temp file
        try:
            os.remove(image_path)
        except Exception as e:
            print(f"[WARN] Failed to remove temp file {image_path}: {e}", file=sys.stderr)

    return answer.startswith('yes')


print("[DEBUG] find_soa_pages.py script execution started.", file=sys.stderr, flush=True)

def main():
    print("[DEBUG] find_soa_pages.py main() started", file=sys.stderr, flush=True)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(description="Find SOA pages in a PDF.")
    parser.add_argument("--pdf-path", required=True, help="Path to the PDF file")
    parser.add_argument("--prompt-file", help="Path to the LLM prompt file for context")
    parser.add_argument("--max-pages", type=int, default=30, help="Max pages to check with LLM if keyword filter fails")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="LLM model to use (e.g., gpt-4o, gemini-2.5-pro)")
    args = parser.parse_args()

    # Ensure pdf_path is absolute
    pdf_path = args.pdf_path
    if not os.path.exists(pdf_path):
        print(f"[FATAL] PDF file not found at: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    MODEL_NAME = args.model
    print(f"[INFO] Using LLM model: {MODEL_NAME}", file=sys.stderr)

    prompt_content = ""
    if args.prompt_file and os.path.exists(args.prompt_file):
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        print(f"[INFO] Loaded prompt context from {args.prompt_file}", file=sys.stderr)
    else:
        print("[WARNING] No prompt file provided or found. Using basic SoA detection.", file=sys.stderr)

    print("[DEBUG] Starting PDF text extraction...", file=sys.stderr, flush=True)
    page_texts = extract_page_texts(pdf_path)
    print(f"[DEBUG] PDF text extraction complete. Extracted {len(page_texts)} pages.", file=sys.stderr, flush=True)
    # Log page text stats for automation/debugging
    empty_or_short = 0
    for i, text in enumerate(page_texts):
        if len(text.strip()) < 30:
            empty_or_short += 1
    if empty_or_short == len(page_texts):
        print("[WARNING] All pages are empty or too short. Consider OCR fallback for this PDF.", file=sys.stderr)

    print("[DEBUG] Starting keyword filtering...", file=sys.stderr, flush=True)
    candidates = keyword_filter(page_texts)
    print("[DEBUG] Keyword filtering complete.", file=sys.stderr, flush=True)
    print(f"[INFO] Keyword candidate pages: {[p + 1 for p in candidates]}", file=sys.stderr)
    soa_pages = []
    def log_llm(page_idx, answer, mode):
        print(f"[LLM][{mode}] Page {page_idx+1} response: {answer}", file=sys.stderr)

    adjudicated = set()
    # 1. Adjudicate keyword candidate pages
    if candidates:
        print(f"[INFO] Running LLM adjudication on keyword candidate pages...", file=sys.stderr, flush=True)
        for i in candidates:
            if i in adjudicated:
                continue
            answer = llm_is_soa_page(page_texts[i], MODEL_NAME, prompt_content)
            log_llm(i, answer, "text")
            # If text-based check fails, try vision-based as a fallback
            if not answer:
                print(f"[INFO] Text-based check failed for page {i+1}. Trying vision-based analysis...", file=sys.stderr)
                answer = llm_is_soa_page_image(pdf_path, i + 1, MODEL_NAME)
                log_llm(i, answer, "vision")
            adjudicated.add(i)
            if answer:
                # Found the start of an SoA block.
                if i not in soa_pages:
                    soa_pages.append(i)
                
                # Keep checking subsequent pages until a "no" to find the whole block.
                next_idx = i + 1
                while next_idx < len(page_texts):
                    if next_idx in adjudicated:
                        next_idx += 1
                        continue
                    answer_next = llm_is_soa_page(page_texts[next_idx], MODEL_NAME, prompt_content)
                    log_llm(next_idx, answer_next, "text (contiguous)")
                    adjudicated.add(next_idx)
                    if answer_next:
                        if next_idx not in soa_pages:
                            soa_pages.append(next_idx)
                        next_idx += 1
                    else:
                        # Found the end of a contiguous block.
                        break
                
                # A contiguous block has ended. The main loop will continue to check other candidates.
                pass

    # 2. If no SOA found from text, use vision on first N pages
    if not soa_pages:
        print(f"[INFO] No SoA pages found from text. Adjudicating first {args.max_pages} pages using vision model...", file=sys.stderr)
        found_soa_vision = False
        for i in range(min(args.max_pages, len(page_texts))):
            if i in adjudicated:
                continue
            print(f"[INFO] LLM adjudicating page {i+1} (vision)...", file=sys.stderr)
            answer = llm_is_soa_page_image(pdf_path, i, MODEL_NAME)
            log_llm(i, answer, "vision")
            adjudicated.add(i)
            if answer:
                if i not in soa_pages:
                    soa_pages.append(i)
                found_soa_vision = True
            elif found_soa_vision:
                # We found the end of the contiguous SoA block
                print(f"[INFO] First non-SOA page after finding SOA block (vision): page {i+1}. Stopping adjudication.", file=sys.stderr)
                break

    soa_pages = sorted(list(set(soa_pages)))

    if soa_pages:
        print(f"[RESULT] SOA pages: {[p + 1 for p in soa_pages]}", file=sys.stderr)
    else:
        print("[RESULT] No SOA pages found.", file=sys.stderr)
    
    # Final output to stdout for the pipeline
    print(",".join(str(p) for p in soa_pages))

if __name__ == "__main__":
    main()
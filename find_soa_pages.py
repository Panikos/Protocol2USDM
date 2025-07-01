import os
import sys
import base64
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import fitz  # PyMuPDF
import textwrap
from openai import OpenAI
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
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

def llm_is_soa_page(page_text, client, model):
    unique_run_id = f"RunID:{time.time()}"
    system_prompt = (
        "You are a text classification assistant. Your only task is to determine if the text from a clinical trial protocol page contains the 'Schedule of Activities' (SoA).\n"
        "The SoA can be a table, a title, or a header.\n"
        "IMPORTANT: A 'Table of Contents' page is NOT a Schedule of Activities, even if it lists the SoA as a section. If the page is a Table of Contents, respond 'no'.\n"
        "If the text contains 'Schedule of Activities', 'SoA', 'Schedule of Events', or a similar title, OR if it contains a table with visits, timepoints, and medical procedures, you must respond 'yes'.\n"
        "Otherwise, respond 'no'.\n"
        "Your response must be a single word: 'yes' or 'no'."
    )
    user_content = f"Page Text:\n{textwrap.shorten(page_text, width=3500)}\n{unique_run_id}"
    params = dict(model=model, messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ])
    # o3 does not support temperature=0, so we use the API's default.
    # For other models, set temperature to 0 for deterministic output.
    if model != "o3":
        params["temperature"] = 0
    if model in ['o3', 'o3-mini', 'o3-mini-high']:
        params['max_completion_tokens'] = 5
    else:
        params['max_tokens'] = 5
    response = client.chat.completions.create(**params)

    answer = response.choices[0].message.content.strip().lower()
    return answer.startswith('yes')

def llm_is_soa_page_image(pdf_path, page_num, client, model):
    """Send image of a PDF page to OpenAI vision API and ask if it contains the SOA table."""
    import tempfile
    import fitz
    import time
    import uuid
    import shutil
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=200)
    # Ensure unique temp file name and that file is closed before pix.save
    for attempt in range(3):
        tmp_path = os.path.join(tempfile.gettempdir(), f"soa_page_{uuid.uuid4().hex}.png")
        try:
            with open(tmp_path, 'wb') as f:
                pass  # Just create and close the file
            pix.save(tmp_path)
            image_path = tmp_path
            break
        except Exception as e:
            print(f"[WARN] Failed to save pixmap to temp file (attempt {attempt+1}): {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            time.sleep(0.5)
    else:
        raise RuntimeError("[FATAL] Could not create/save temp PNG for LLM vision adjudication after 3 attempts.")
    with open(image_path, 'rb') as imgf:
        img_b64 = base64.b64encode(imgf.read()).decode('utf-8')
    image_url = f"data:image/png;base64,{img_b64}"
    unique_run_id = f"RunID:{time.time()}"
    system_prompt = (
        "You are an image classification assistant. Your only task is to determine if the image of a clinical trial protocol page contains the 'Schedule of Activities' (SoA).\n"
        "The SoA can be a table, a title, or a header.\n"
        "IMPORTANT: A 'Table of Contents' page is NOT a Schedule of Activities, even if it lists the SoA as a section. If the image shows a Table of Contents, respond 'no'.\n"
        "If the image contains the text 'Schedule of Activities', 'SoA', 'Schedule of Events', or a similar title, OR if it shows a table with visits, timepoints, and medical procedures, you must respond 'yes'.\n"
        "Otherwise, respond 'no'.\n"
        "Your response must be a single word: 'yes' or 'no'. "
        f"{unique_run_id}"
    )
    try:
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
        )
        # o3 does not support temperature=0, so we use the API's default.
        # For other models, set temperature to 0 for deterministic output.
        if model != "o3":
            params["temperature"] = 0
        if model in ['o3', 'o3-mini', 'o3-mini-high']:
            params['max_completion_tokens'] = 5
        else:
            params['max_tokens'] = 5
        response = client.chat.completions.create(**params)
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}")
        # Fallback or re-raise
        raise
    answer = response.choices[0].message.content.strip().lower()
    import time
    # Robust temp file cleanup: retry up to 3 times if permission denied
    for attempt in range(3):
        try:
            os.remove(image_path)
            break
        except PermissionError as e:
            print(f"[WARN] Temp file removal failed (attempt {attempt+1}): {e}. Retrying...")
            time.sleep(0.5)
    else:
        print(f"[ERROR] Could not remove temp file {image_path} after 3 attempts. Please check for locked files.")
    return answer.startswith('yes')


def main():
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(description="Find SOA pages in a PDF.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--max-pages", type=int, default=30, help="Max pages to check with LLM if keyword filter fails")
    parser.add_argument("--model", default=os.environ.get('OPENAI_MODEL', 'gpt-4o'), help="OpenAI model to use")
    args = parser.parse_args()

    MODEL_NAME = args.model
    print(f"[INFO] Using OpenAI model: {MODEL_NAME}")

    page_texts = extract_page_texts(args.pdf_path)
    # Log page text stats for automation/debugging
    empty_or_short = 0
    for i, text in enumerate(page_texts):
        snippet = text[:100].replace('\n', ' ')
        print(f"[PAGE {i+1}] Length: {len(text)} | Preview: '{snippet}'")
        if len(text.strip()) < 30:
            empty_or_short += 1
    if empty_or_short == len(page_texts):
        print("[WARNING] All pages are empty or too short. Consider OCR fallback for this PDF.")

    candidates = keyword_filter(page_texts)
    print(f"[INFO] Keyword candidate pages: {[p + 1 for p in candidates]}")
    soa_pages = []
    def log_llm(page_idx, answer, mode):
        print(f"[LLM][{mode}] Page {page_idx+1} response: {answer}")

    adjudicated = set()
    found_soa = False
    # 1. Adjudicate keyword candidate pages
    N_EXTRA = getattr(args, 'extra_pages', 1)  # Default to 1 extra page if not set
    if candidates:
        print(f"[INFO] Running LLM adjudication on keyword candidate pages: {[p + 1 for p in candidates]}")
        for i in candidates:
            if i in adjudicated:
                continue
            model_to_use = args.model
            print(f'[DEBUG] llm_is_soa_page using model: {model_to_use}')
            answer = llm_is_soa_page(page_texts[i], client, model_to_use)
            log_llm(i, answer, "text")
            adjudicated.add(i)
            if answer:
                soa_pages.append(i)
                found_soa = True
                # Keep checking subsequent pages until a "no"
                next_idx = i + 1
                while next_idx < len(page_texts):
                    answer_next = llm_is_soa_page(page_texts[next_idx], client, MODEL_NAME)
                    log_llm(next_idx, answer_next, "text (contiguous)")
                    adjudicated.add(next_idx)
                    if answer_next:
                        soa_pages.append(next_idx)
                        next_idx += 1
                    else:
                        break

    # 2. If no SOA found, continue adjudicating all remaining pages in order with vision
    if not soa_pages:
        print(f"[INFO] No SOA found in keyword candidates. Adjudicating all pages in order (vision)...")
        found_soa_vision = False
        for i in range(len(page_texts)):
            if i in adjudicated:
                continue
            print(f"[INFO] LLM adjudicating page {i+1} (vision)...")
            answer = llm_is_soa_page_image(args.pdf_path, i, client, MODEL_NAME)
            log_llm(i, answer, "vision")
            if answer:
                soa_pages.append(i)
                found_soa_vision = True
            elif found_soa_vision:
                # We found the end of the contiguous SoA block
                print(f"[INFO] First non-SOA page after finding SOA block (vision): page {i+1}. Stopping adjudication.")
                break
    if soa_pages:
        print(f"[RESULT] SOA pages: {soa_pages}")
        print(f"SOA page range: {soa_pages[0]+1} to {soa_pages[-1]+1}")
    else:
        print("[RESULT] No SOA pages found.")
    print(",".join(str(p) for p in soa_pages))

if __name__ == "__main__":
    main()

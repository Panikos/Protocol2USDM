import os
import sys
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

def llm_is_soa_page(page_text, client):
    unique_run_id = f"RunID:{time.time()}"
    prompt = (
        "You are an expert in clinical trial protocol parsing. "
        "Does the following page contain the Schedule of Activities (SoA) table for a clinical trial protocol? "
        "Reply only 'yes' or 'no'.\n\n"
        f"Page Text:\n{textwrap.shorten(page_text, width=3500)}\n{unique_run_id}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt}
        ],
        max_tokens=5
    )
    answer = response.choices[0].message.content.strip().lower()
    return answer.startswith('yes')

def llm_is_soa_page_image(pdf_path, page_num, client):
    """Send image of a PDF page to OpenAI vision API and ask if it contains the SOA table."""
    import tempfile
    import fitz
    import time
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=200)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        pix.save(tmp.name)
        image_path = tmp.name
    unique_run_id = f"RunID:{time.time()}"
    prompt = (
        "You are an expert in clinical trial protocol parsing. "
        "Does this image contain the Schedule of Activities (SoA) table for a clinical trial protocol? "
        "Reply only 'yes' or 'no'. "
        f"{unique_run_id}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"file://{image_path}"}}
            ]}
        ],
        max_tokens=5
    )
    answer = response.choices[0].message.content.strip().lower()
    os.remove(image_path)
    return answer.startswith('yes')

def main():
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(description="Find SOA pages in a PDF.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--max-pages", type=int, default=30, help="Max pages to check with LLM if keyword filter fails")
    args = parser.parse_args()

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
    print(f"[INFO] Keyword candidate pages: {candidates}")
    soa_pages = []
    def log_llm(page_idx, answer, mode):
        print(f"[LLM][{mode}] Page {page_idx+1} response: {answer}")

    adjudicated = set()
    found_soa = False
    # 1. Adjudicate keyword candidate pages
    N_EXTRA = getattr(args, 'extra_pages', 1)  # Default to 1 extra page if not set
    if candidates:
        print(f"[INFO] Running LLM adjudication on keyword candidate pages: {candidates}")
        for i in candidates:
            answer = llm_is_soa_page(page_texts[i], client)
            log_llm(i, answer, "text")
            adjudicated.add(i)
            if answer:
                soa_pages.append(i)
                found_soa = True
                # Check N_EXTRA subsequent pages
                for j in range(1, N_EXTRA+1):
                    if i+j < len(page_texts):
                        answer_next = llm_is_soa_page(page_texts[i+j], client)
                        log_llm(i+j, answer_next, "text (extra)")
                        adjudicated.add(i+j)
                        if answer_next:
                            soa_pages.append(i+j)
                        else:
                            break
    # 2. If no SOA found, continue adjudicating all remaining pages in order
    if not soa_pages:
        print(f"[INFO] No SOA found in keyword candidates. Adjudicating all pages in order...")
        for i in range(len(page_texts)):
            if i in adjudicated:
                continue
            print(f"[INFO] LLM adjudicating page {i+1} (vision)...")
            answer = llm_is_soa_page_image(args.pdf_path, i, client)
            log_llm(i, answer, "vision")
            if answer:
                soa_pages.append(i)
            elif found_soa:
                print(f"[INFO] First non-SOA page after finding SOA: page {i+1}. Stopping adjudication.")
                break
    if soa_pages:
        print(f"[RESULT] SOA pages: {soa_pages}")
        print(f"SOA page range: {soa_pages[0]+1} to {soa_pages[-1]+1}")
    else:
        print("[RESULT] No SOA pages found.")
    print(",".join(str(p) for p in soa_pages))

if __name__ == "__main__":
    main()

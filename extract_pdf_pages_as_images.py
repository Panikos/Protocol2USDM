import os
import sys
import fitz  # PyMuPDF
import argparse

def extract_pages_as_images(pdf_path, page_numbers, output_dir="."):
    """
    Extracts specific 1-indexed pages from a PDF as images.

    Args:
        pdf_path (str): The path to the PDF file.
        page_numbers (list[int]): A list of 1-based page numbers to extract.
        output_dir (str): The directory to save the output images.

    Returns:
        list[str]: A list of paths to the created image files.
    """
    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF file not found at: {pdf_path}", file=sys.stderr)
        return []
        
    image_paths = []
    try:
        doc = fitz.open(pdf_path)
        os.makedirs(output_dir, exist_ok=True)

        for page_num in page_numbers:
            # PyMuPDF uses 0-based indexing, so subtract 1 from the 1-based input
            page_index = page_num - 1
            if 0 <= page_index < len(doc):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(dpi=300)
                image_path = os.path.join(output_dir, f'soa_page_{page_num}.png')
                pix.save(image_path)
                image_paths.append(image_path)
                print(f"Extracted page {page_num} to {image_path}")
            else:
                print(f"[WARN] Page number {page_num} is out of range (1-{len(doc)}).", file=sys.stderr)

    except Exception as e:
        print(f"[ERROR] Failed to extract pages from {pdf_path}: {e}", file=sys.stderr)
        return []
        
    return image_paths

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract specific 1-indexed pages from a PDF as high-resolution PNG images.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    parser.add_argument("--pages", nargs='+', type=int, required=True, help="One or more 1-based page numbers to extract (e.g., --pages 51 52 53).")
    parser.add_argument("--outdir", default="./soa_images", help="Directory to save the output images (default: ./soa_images).")
    
    args = parser.parse_args()

    image_paths = extract_pages_as_images(args.pdf_path, args.pages, args.outdir)
    
    if not image_paths:
        sys.exit(1)

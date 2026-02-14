"""
PDF Utility Functions.

Common PDF operations used across the pipeline.
"""

import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def extract_text_from_pages(
    pdf_path: str,
    pages: List[int],
    max_chars_per_page: int = 10000,
) -> Optional[str]:
    """
    Extract text from specific pages of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        pages: List of 0-indexed page numbers to extract
        max_chars_per_page: Maximum characters per page (to avoid huge texts)
        
    Returns:
        Combined text from all specified pages, or None on failure
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        texts = []
        for page_num in pages:
            if page_num < 0 or page_num >= total_pages:
                logger.warning(f"Page {page_num} out of range (0-{total_pages-1})")
                continue
                
            page = doc[page_num]
            text = page.get_text()
            
            # Truncate if too long
            if len(text) > max_chars_per_page:
                text = text[:max_chars_per_page] + "\n...[truncated]..."
                
            texts.append(f"--- Page {page_num + 1} ---\n{text}")
            
        doc.close()
        
        if texts:
            return "\n\n".join(texts)
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        return None


def get_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception as e:
        logger.error(f"Failed to get page count: {e}")
        return 0


def render_page_to_image(
    pdf_path: str,
    page_num: int,
    output_path: str,
    dpi: int = 150,
) -> Optional[str]:
    """
    Render a PDF page to an image file.
    
    Args:
        pdf_path: Path to the PDF file
        page_num: 0-indexed page number
        output_path: Path for the output image
        dpi: Resolution in dots per inch
        
    Returns:
        Path to the created image, or None on failure
    """
    try:
        import fitz
        
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            logger.error(f"Page {page_num} out of range")
            doc.close()
            return None
            
        page = doc[page_num]
        
        # Calculate zoom factor for DPI
        zoom = dpi / 72  # 72 is default PDF DPI
        matrix = fitz.Matrix(zoom, zoom)
        
        # Render page
        pix = page.get_pixmap(matrix=matrix)
        pix.save(output_path)
        
        doc.close()
        logger.info(f"Rendered page {page_num} to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to render page: {e}")
        return None


def render_page_region_to_image(
    pdf_path: str,
    page_num: int,
    output_path: str,
    clip_rect: tuple,
    dpi: int = 200,
) -> Optional[str]:
    """
    Render a clipped region of a PDF page to an image file.
    
    Args:
        pdf_path: Path to the PDF file
        page_num: 0-indexed page number
        output_path: Path for the output image
        clip_rect: (x0, y0, x1, y1) rectangle in PDF points to clip
        dpi: Resolution in dots per inch
        
    Returns:
        Path to the created image, or None on failure
    """
    try:
        import fitz
        
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            doc.close()
            return None
            
        page = doc[page_num]
        rect = fitz.Rect(clip_rect)
        
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        
        pix = page.get_pixmap(matrix=matrix, clip=rect)
        if pix.width < 10 or pix.height < 10:
            doc.close()
            return None
        pix.save(output_path)
        
        doc.close()
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to render page region: {e}")
        return None


def extract_embedded_image(
    pdf_path: str,
    page_num: int,
    xref: int,
    output_path: str,
) -> Optional[str]:
    """
    Extract an embedded image from a PDF by its xref number.
    
    Args:
        pdf_path: Path to the PDF file
        page_num: Page number (for logging)
        xref: PDF object reference number for the image
        output_path: Path for the output image
        
    Returns:
        Path to the created image, or None on failure
    """
    try:
        import fitz
        
        doc = fitz.open(pdf_path)
        img_data = doc.extract_image(xref)
        doc.close()
        
        if not img_data or not img_data.get("image"):
            return None
        
        # Get extension from image format
        ext = img_data.get("ext", "png")
        raw_bytes = img_data["image"]
        
        # If it's already PNG or JPEG, write directly
        if ext in ("png", "jpeg", "jpg"):
            # Ensure output has right extension
            if not output_path.endswith(f".{ext}"):
                output_path = output_path.rsplit('.', 1)[0] + f".{ext}"
            with open(output_path, "wb") as f:
                f.write(raw_bytes)
            return output_path
        
        # For other formats, convert via pixmap
        pix = fitz.Pixmap(raw_bytes)
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(output_path)
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to extract embedded image (xref={xref}): {e}")
        return None


def render_pages_to_images(
    pdf_path: str,
    pages: List[int],
    output_dir: str,
    dpi: int = 150,
    prefix: str = "page",
) -> List[str]:
    """
    Render multiple PDF pages to images.
    
    Args:
        pdf_path: Path to the PDF file
        pages: List of 0-indexed page numbers
        output_dir: Directory for output images
        dpi: Resolution in dots per inch
        prefix: Filename prefix
        
    Returns:
        List of paths to created images
    """
    from pathlib import Path
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    image_paths = []
    for page_num in pages:
        img_path = str(output_path / f"{prefix}_{page_num:03d}.png")
        result = render_page_to_image(pdf_path, page_num, img_path, dpi)
        if result:
            image_paths.append(result)
            
    return image_paths

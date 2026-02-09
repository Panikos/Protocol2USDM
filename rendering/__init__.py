"""
M11 Protocol Document Rendering Module.

Transforms USDM JSON into publishable M11 protocol documents (DOCX).
"""

from .m11_renderer import render_m11_docx, M11RenderResult

__all__ = [
    "render_m11_docx",
    "M11RenderResult",
]

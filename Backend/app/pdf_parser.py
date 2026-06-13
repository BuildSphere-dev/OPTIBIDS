# backend/app/pdf_parser.py

"""
PDF text extraction using PyMuPDF (fitz).
Install: pip install pymupdf

Falls back gracefully if the file is missing or corrupted.
"""

import fitz  # PyMuPDF
from typing import cast


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF file.

    Args:
        pdf_path: Absolute or relative path to the .pdf file.

    Returns:
        Full text of the PDF as a single string.
        Returns empty string on failure (logs the error).
    """
    try:
        doc = fitz.open(pdf_path)
        pages_text = []

        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)

            page_text = cast(str, page.get_text("text"))

            if page_text.strip():
                pages_text.append(page_text)

        doc.close()
        return "\n\n".join(pages_text)

    except Exception as e:
        print(f" pdf_parser: failed to extract text from '{pdf_path}': {e}")
        return ""

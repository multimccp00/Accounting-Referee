"""
PDF text extraction utilities.

Provides functions to read and extract text from PDF files.
Requires the pypdf library.
"""


def extract_pdf_text(pdf_path: str) -> str:
    """Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Full text from all pages, joined with newlines.

    Raises:
        ImportError: If pypdf library is not installed.
        Exception: If the PDF file cannot be read.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "Missing dependency pypdf. Install with: pip install pypdf"
        ) from exc

    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)

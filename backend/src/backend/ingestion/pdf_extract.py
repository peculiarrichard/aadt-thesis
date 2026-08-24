from pathlib import Path

import pypdf


def extract_lines(pdf_path: Path) -> list[str]:
    """Every non-empty line of extracted text, across all pages, in reading order.

    Returns an empty list for scanned/image-only PDFs with no text layer (OCR is out
    of scope here; see docs/guideline_corpus/README.md for a document rejected for this).
    """
    reader = pypdf.PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines.extend(line.strip() for line in text.split("\n") if line.strip())
    return lines

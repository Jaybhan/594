"""Stage 1 — PDF extraction with PyMuPDF and pytesseract OCR fallback."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .config import OCR_TEXT_MIN_CHARS

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    path: Path
    text: str
    method: str          # "pymupdf" | "ocr" | "failed"
    error: str | None = field(default=None)


def extract_pdf(path: Path, ocr_fallback: bool = True) -> ExtractionResult:
    """Extract text from a PDF. Never raises — returns ExtractionResult with method='failed' on error."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ExtractionResult(path=path, text="", method="failed",
                                error="PyMuPDF not installed")

    try:
        doc = fitz.open(str(path))
        pages_text = [page.get_text() for page in doc]
        doc.close()
        full_text = "\n".join(pages_text).strip()

        if len(full_text) >= OCR_TEXT_MIN_CHARS:
            return ExtractionResult(path=path, text=full_text, method="pymupdf")

        if not ocr_fallback:
            return ExtractionResult(path=path, text=full_text, method="pymupdf")

        # Text layer is too sparse — try OCR
        return _ocr_extract(path)

    except Exception as exc:
        logger.error("PyMuPDF failed for %s: %s", path, exc)
        if ocr_fallback:
            return _ocr_extract(path)
        return ExtractionResult(path=path, text="", method="failed", error=str(exc))


def _ocr_extract(path: Path) -> ExtractionResult:
    """Render each PDF page as an image and run pytesseract OCR."""
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(str(path))
        pages_text: list[str] = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            pages_text.append(pytesseract.image_to_string(img))
        doc.close()
        text = "\n".join(pages_text).strip()
        return ExtractionResult(path=path, text=text, method="ocr")

    except Exception as exc:
        logger.error("OCR failed for %s: %s", path, exc)
        return ExtractionResult(path=path, text="", method="failed", error=str(exc))


def _extract_dir(directory: Path) -> dict[str, ExtractionResult]:
    """Extract all PDFs in a flat directory. Keys are file stems (e.g. 'q1')."""
    results: dict[str, ExtractionResult] = {}
    if not directory.exists():
        logger.warning("Directory not found: %s", directory)
        return results
    for pdf_path in sorted(directory.glob("*.pdf")):
        stem = pdf_path.stem
        logger.info("Extracting %s", pdf_path)
        results[stem] = extract_pdf(pdf_path)
    return results


def extract_exam_texts(exam_dir: Path) -> dict:
    """
    Walk an exam directory and extract all PDFs.

    Returns:
        {
            "questions": {"q1": ExtractionResult, ...},
            "rubrics":   {"q1": ExtractionResult, ...},
            "responses": {
                "student_001": {"q1": ExtractionResult, ...},
                ...
            }
        }
    """
    exam_dir = Path(exam_dir)
    questions = _extract_dir(exam_dir / "questions")
    rubrics = _extract_dir(exam_dir / "rubric")

    responses: dict[str, dict[str, ExtractionResult]] = {}
    responses_root = exam_dir / "sample_responses"
    if responses_root.exists():
        for student_dir in sorted(responses_root.iterdir()):
            if student_dir.is_dir():
                sid = student_dir.name
                logger.info("Extracting responses for student %s", sid)
                responses[sid] = _extract_dir(student_dir)
    else:
        logger.warning("sample_responses directory not found in %s", exam_dir)

    return {"questions": questions, "rubrics": rubrics, "responses": responses}

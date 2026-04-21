# -*- coding: utf-8 -*-
"""
Reorganizes the AP-History exam PDFs into the directory structure expected by
the grader:

  Exams/AP-History/
    questions/{q_id}.pdf
    rubric/{q_id}.pdf
    sample_responses/{student_id}/{q_id}.pdf

Run once before running code.py.
"""

from pathlib import Path
import fitz  # PyMuPDF

EXAM_DIR = Path("Exams/AP-History")
QUESTION_SET = EXAM_DIR / "APUSH Question Set 1.pdf"
ANSWER_KEY   = EXAM_DIR / "APUSH Answer Key 1.pdf"

# Pages to extract from Question Set (0-indexed PyMuPDF page numbers)
# Page 1 = SAQ directions, always included for context.
# Page 5 = Section II directions, included with DBQ/LEQ.
QUESTION_PAGES = {
    "saq1": [1, 2],        # SAQ directions + Q1 (Wilentz/Bouton sources)
    "saq2": [1, 3],        # SAQ directions + Q2 (Webster speech)
    "saq3": [1, 4],        # SAQ directions + Q3 (Colonial period) — Q3 & Q4 share p4
    "saq4": [1, 4],        # SAQ directions + Q4 (Reconstruction)  — same page
    "dbq1": [5, 6, 7, 8, 9],  # Sec II directions + DBQ prompt + all 7 docs
    "leq1": [5, 10],       # Sec II directions + all three LEQ prompts
    "leq2": [5, 10],
    "leq3": [5, 10],
}

# Pages to extract from Answer Key (0-indexed)
RUBRIC_PAGES = {
    "saq1": list(range(1, 3)),    # pp 2-3  (SAQ Q1 rubric, 3 pts)
    "saq2": list(range(3, 5)),    # pp 4-5  (SAQ Q2 rubric, 3 pts)
    "saq3": list(range(5, 7)),    # pp 6-7  (SAQ Q3 rubric, 3 pts)
    "saq4": list(range(7, 9)),    # pp 8-9  (SAQ Q4 rubric, 3 pts)
    "dbq1": list(range(9, 18)),   # pp 10-18 (DBQ rubric, 7 pts)
    "leq1": list(range(18, 25)),  # pp 19-25 (LEQ Q2 rubric, 6 pts)
    "leq2": list(range(25, 32)),  # pp 26-32 (LEQ Q3 rubric, 6 pts)
    "leq3": list(range(32, 38)),  # pp 33-38 (LEQ Q4 rubric, 6 pts)
}

# Each source PDF contains responses from 3 students separated by "Student N" header pages.
RESPONSE_SOURCES = {
    "saq1": EXAM_DIR / "APUSH SAQ 1-1.pdf",
    "saq2": EXAM_DIR / "APUSH SAQ 1-2.pdf",
    "saq3": EXAM_DIR / "APUSH SAQ 1-3.pdf",
    "saq4": EXAM_DIR / "APUSH SAQ 1-4.pdf",
    "dbq1": EXAM_DIR / "APUSH DBQ 1-1.pdf",
    "leq1": EXAM_DIR / "APUSH LEQ 1-1_.pdf",
    "leq2": EXAM_DIR / "APUSH LEQ 1-2.pdf",
    "leq3": EXAM_DIR / "APUSH LEQ 1-3.pdf",
}


def extract_pages(src, page_indices, dest):
    if dest.exists():
        print(f"  skip (exists): {dest.relative_to(EXAM_DIR)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_doc = fitz.open(str(src))
    out_doc = fitz.open()
    for idx in page_indices:
        out_doc.insert_pdf(src_doc, from_page=idx, to_page=idx)
    out_doc.save(str(dest))
    out_doc.close()
    src_doc.close()
    print(f"  wrote: {dest.relative_to(EXAM_DIR)}")


def _is_student_header(page):
    """True if this page is a 'Student N' separator page, not essay content."""
    text = page.get_text().strip()
    parts = text.split()
    return len(parts) == 2 and parts[0] == "Student" and parts[1].isdigit()


def split_student_responses(src):
    """
    Open src PDF and split it into per-student page groups by detecting
    'Student N' header pages.  Returns [(student_num, [page_indices]), ...].
    """
    doc = fitz.open(str(src))
    sections = []
    current_student = None
    current_pages = []

    for i, page in enumerate(doc):
        if _is_student_header(page):
            if current_student is not None:
                sections.append((current_student, current_pages))
            current_student = int(page.get_text().strip().split()[1])
            current_pages = []
        elif current_student is not None:
            current_pages.append(i)

    if current_student is not None and current_pages:
        sections.append((current_student, current_pages))

    return doc, sections


def extract_student_response(src_doc, page_indices, dest):
    if dest.exists():
        print(f"  skip (exists): {dest.relative_to(EXAM_DIR)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    out_doc = fitz.open()
    for idx in page_indices:
        out_doc.insert_pdf(src_doc, from_page=idx, to_page=idx)
    out_doc.save(str(dest))
    out_doc.close()
    print(f"  wrote: {dest.relative_to(EXAM_DIR)}")


def main():
    print("=== Extracting question PDFs ===")
    for qid, pages in QUESTION_PAGES.items():
        extract_pages(QUESTION_SET, pages, EXAM_DIR / "questions" / f"{qid}.pdf")

    print("\n=== Extracting rubric PDFs ===")
    for qid, pages in RUBRIC_PAGES.items():
        extract_pages(ANSWER_KEY, pages, EXAM_DIR / "rubric" / f"{qid}.pdf")

    print("\n=== Extracting student responses ===")
    for qid, src in RESPONSE_SOURCES.items():
        if not src.exists():
            print(f"  MISSING source: {src.name}")
            continue
        src_doc, sections = split_student_responses(src)
        for student_num, pages in sections:
            dest = EXAM_DIR / "sample_responses" / f"student_{student_num:03d}" / f"{qid}.pdf"
            extract_student_response(src_doc, pages, dest)
        src_doc.close()

    print("\nDone. Directory structure ready for grader.")


if __name__ == "__main__":
    main()

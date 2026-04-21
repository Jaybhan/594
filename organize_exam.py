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

import shutil
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

# Student response source files, keyed by (student_id, question_id)
RESPONSES = {
    "student_001": {
        "saq1": EXAM_DIR / "APUSH SAQ 1-1.pdf",
        "saq2": EXAM_DIR / "APUSH SAQ 1-2.pdf",
        "saq3": EXAM_DIR / "APUSH SAQ 1-3.pdf",
        "saq4": EXAM_DIR / "APUSH SAQ 1-4.pdf",
        "dbq1": EXAM_DIR / "APUSH DBQ 1-1.pdf",
        "leq1": EXAM_DIR / "APUSH LEQ 1-1_.pdf",
        "leq2": EXAM_DIR / "APUSH LEQ 1-2.pdf",
        "leq3": EXAM_DIR / "APUSH LEQ 1-3.pdf",
    },
    "student_002": {
        "saq1": EXAM_DIR / "Copy of APUSH SAQ 1-1.pdf",
        "saq2": EXAM_DIR / "Copy of APUSH SAQ 1-2.pdf",
        "saq3": EXAM_DIR / "Copy of APUSH SAQ 1-3.pdf",
        "saq4": EXAM_DIR / "Copy of APUSH SAQ 1-4.pdf",
        "dbq1": EXAM_DIR / "Copy of APUSH DBQ 1-1.pdf",
        "leq1": EXAM_DIR / "Copy of APUSH LEQ 1-1.pdf",
        "leq2": EXAM_DIR / "Copy of APUSH LEQ 1-2.pdf",
        "leq3": EXAM_DIR / "Copy of APUSH LEQ 1-3.pdf",
    },
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


def copy_response(src, dest):
    if dest.exists():
        print(f"  skip (exists): {dest.relative_to(EXAM_DIR)}")
        return
    if not src.exists():
        print(f"  MISSING source: {src.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  copied: {src.name} → {dest.relative_to(EXAM_DIR)}")


def main():
    print("=== Extracting question PDFs ===")
    for qid, pages in QUESTION_PAGES.items():
        extract_pages(QUESTION_SET, pages, EXAM_DIR / "questions" / f"{qid}.pdf")

    print("\n=== Extracting rubric PDFs ===")
    for qid, pages in RUBRIC_PAGES.items():
        extract_pages(ANSWER_KEY, pages, EXAM_DIR / "rubric" / f"{qid}.pdf")

    print("\n=== Copying student responses ===")
    for student_id, files in RESPONSES.items():
        for qid, src in files.items():
            copy_response(src, EXAM_DIR / "sample_responses" / student_id / f"{qid}.pdf")

    print("\nDone. Directory structure ready for grader.")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Reorganizes the AP-Chem exam PDFs into the directory structure expected by
the grader:

  Exams/AP-Chem/
    questions/{frq_id}.pdf
    rubric/{frq_id}.pdf
    sample_responses/{student_id}/{frq_id}.pdf

Student files are already split: student_{letter}_q{num}.pdf
  e.g. student_A_q1.pdf = Student A's response to FRQ 1

Run with --inspect first to verify page mappings from the official PDFs,
then run without flags to build the full directory structure.
"""

from pathlib import Path
import argparse
import fitz  # PyMuPDF

EXAM_DIR = Path("Exams/AP-Chem")
FRQ_DOC  = EXAM_DIR / "ap25-frq-chemistry.pdf"
SG_DOC   = EXAM_DIR / "ap25-sg-chemistry.pdf"

STUDENT_MAP = {"A": "student_001", "B": "student_002", "C": "student_003"}

# Pages to extract from the FRQ document (0-indexed).
# p0=cover, p1=general directions, p2-4=Q1, p5-6=Q2, p7-9=Q3,
# p10=Q4, p11=Q5, p12-13=Q6, p14=Q7
QUESTION_PAGES = {
    "frq1": [1, 2, 3, 4],    # directions + Q1 (3 pages)
    "frq2": [1, 5, 6],       # directions + Q2 (2 pages)
    "frq3": [1, 7, 8, 9],    # directions + Q3 (3 pages)
    "frq4": [1, 10],         # directions + Q4
    "frq5": [1, 11],         # directions + Q5
    "frq6": [1, 12, 13],     # directions + Q6 (2 pages)
    "frq7": [1, 14],         # directions + Q7
}

# Pages to extract from the scoring guide (0-indexed).
# p0=cover, p1-2=Q1, p3-4=Q2, p5-6=Q3, p7=Q4, p8=Q5, p9=Q6, p10=Q7
RUBRIC_PAGES = {
    "frq1": [1, 2],
    "frq2": [3, 4],
    "frq3": [5, 6],
    "frq4": [7],
    "frq5": [8],
    "frq6": [9],
    "frq7": [10],
}


def inspect_pdf(path):
    """Print page count and first non-blank line of each page."""
    doc = fitz.open(str(path))
    print(f"\n=== {path.name}  ({len(doc)} pages) ===")
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "(no text)")
        print(f"  p{i:>3}  {first_line[:100]}")
    doc.close()


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
    """Copy a single-student PDF into the target directory structure."""
    if dest.exists():
        print(f"  skip (exists): {dest.relative_to(EXAM_DIR)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_doc = fitz.open(str(src))
    out_doc = fitz.open()
    out_doc.insert_pdf(src_doc)
    out_doc.save(str(dest))
    out_doc.close()
    src_doc.close()
    print(f"  wrote: {dest.relative_to(EXAM_DIR)}")


def reorganize_responses():
    for q in range(1, 8):
        for letter, sid in STUDENT_MAP.items():
            src = EXAM_DIR / f"student_{letter}_q{q}.pdf"
            if not src.exists():
                print(f"  MISSING: {src.name}")
                continue
            dest = EXAM_DIR / "sample_responses" / sid / f"frq{q}.pdf"
            copy_response(src, dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true",
                        help="Print page structure of official PDFs and exit")
    args = parser.parse_args()

    if args.inspect:
        inspect_pdf(FRQ_DOC)
        inspect_pdf(SG_DOC)
        return

    print("=== Extracting question PDFs ===")
    for qid, pages in QUESTION_PAGES.items():
        extract_pages(FRQ_DOC, pages, EXAM_DIR / "questions" / f"{qid}.pdf")

    print("\n=== Extracting rubric PDFs ===")
    for qid, pages in RUBRIC_PAGES.items():
        extract_pages(SG_DOC, pages, EXAM_DIR / "rubric" / f"{qid}.pdf")

    print("\n=== Reorganizing student responses ===")
    reorganize_responses()

    print("\nDone. Directory structure ready for grader.")


if __name__ == "__main__":
    main()

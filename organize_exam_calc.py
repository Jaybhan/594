# -*- coding: utf-8 -*-
"""
Reorganizes the AP-Calc exam PDFs into the directory structure expected by
the grader:

  Exams/AP-Calc/
    questions/{frq_id}.pdf
    rubric/{frq_id}.pdf
    sample_responses/{student_id}/{frq_id}.pdf

Student files are already split: Student_{question}{letter}.pdf
  e.g. Student_1A.pdf = Student A's response to FRQ 1

Run with --inspect first to determine page mappings from the official PDFs,
then run without flags to build the full directory structure.
"""

from pathlib import Path
import argparse
import fitz  # PyMuPDF

EXAM_DIR = Path("Exams/AP-Calc")
FRQ_DOC  = EXAM_DIR / "ap25-frq-calculus-bc.pdf"
SG_DOC   = EXAM_DIR / "ap25-sg-calculus-bc.pdf"

STUDENT_MAP = {"A": "student_001", "B": "student_002", "C": "student_003"}

# Pages to extract from the FRQ document (0-indexed).
# p0=cover, p1=Part A directions, p2=Q1, p3=Q2,
# p4=Part B directions, p5=Q3, p6=Q4, p7=Q5, p8=Q6
QUESTION_PAGES = {
    "frq1": [1, 2],        # Part A directions + Q1
    "frq2": [1, 3],        # Part A directions + Q2
    "frq3": [4, 5],        # Part B directions + Q3
    "frq4": [4, 6],        # Part B directions + Q4
    "frq5": [4, 7],        # Part B directions + Q5
    "frq6": [4, 8],        # Part B directions + Q6
}

# Pages to extract from the scoring guide (0-indexed).
# p0=cover, p1-4=Q1, p5-9=Q2, p10-13=Q3, p14-18=Q4, p19-22=Q5, p23-26=Q6
RUBRIC_PAGES = {
    "frq1": list(range(1, 5)),    # pp 1-4
    "frq2": list(range(5, 10)),   # pp 5-9
    "frq3": list(range(10, 14)),  # pp 10-13
    "frq4": list(range(14, 19)),  # pp 14-18
    "frq5": list(range(19, 23)),  # pp 19-22
    "frq6": list(range(23, 27)),  # pp 23-26
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
    """Copy a single-student image PDF into the target directory structure."""
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
    for q in range(1, 7):
        for letter, sid in STUDENT_MAP.items():
            src = EXAM_DIR / f"Student_{q}{letter}.pdf"
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

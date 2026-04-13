"""
Automated Exam Grading Pipeline
================================
Usage:
    python code.py <exam_dir> [--db grading.db] [--threshold 0.20] [--out-dir .]

Requires ANTHROPIC_API_KEY environment variable.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import anthropic

from grader.config import DB_PATH, DISCREPANCY_THRESHOLD
from grader.extractor import extract_exam_texts
from grader.assessor import GraderAssessor, grade_exam
from grader.database import load_teacher_scores, build_dataframe, save_to_sqlite, export_csv, export_json
from grader.analyzer import compute_discrepancies, print_report, export_report


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("grading.log"),
        ],
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="Automated exam grading pipeline powered by Claude."
    )
    parser.add_argument(
        "exam_dir",
        type=Path,
        help="Path to the exam directory (e.g. Exams/AP-Calc)",
    )
    parser.add_argument(
        "--db",
        default=DB_PATH,
        help=f"SQLite database path (default: {DB_PATH})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DISCREPANCY_THRESHOLD,
        help=f"Discrepancy rate threshold for flagging (default: {DISCREPANCY_THRESHOLD})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("."),
        help="Directory for CSV, JSON, and report outputs (default: current dir)",
    )
    args = parser.parse_args()

    exam_dir: Path = args.exam_dir
    if not exam_dir.exists():
        logger.error("Exam directory not found: %s", exam_dir)
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    exam_name = exam_dir.name

    # ── Stage 1: PDF Extraction ──────────────────────────────────────────────
    logger.info("=== Stage 1: PDF Extraction ===")
    extraction = extract_exam_texts(exam_dir)
    q_count = len(extraction["questions"])
    s_count = len(extraction["responses"])
    logger.info("Extracted %d question(s), rubrics for %d question(s), %d student(s)",
                q_count, len(extraction["rubrics"]), s_count)

    # ── Stage 2: AI Assessment ───────────────────────────────────────────────
    logger.info("=== Stage 2: AI Assessment ===")
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
    assessor = GraderAssessor(client)
    results = grade_exam(exam_dir, extraction, assessor)
    logger.info("Completed %d assessment(s)", len(results))

    # ── Stage 3: Score Database ──────────────────────────────────────────────
    logger.info("=== Stage 3: Score Database ===")
    teacher_df = load_teacher_scores(exam_dir)
    df = build_dataframe(results, exam_name, teacher_df)
    save_to_sqlite(df, args.db)
    export_csv(df, args.out_dir / f"{exam_name}_grades.csv")
    export_json(df, args.out_dir / f"{exam_name}_grades.json")
    logger.info("Database contains %d row(s)", len(df))

    # ── Stage 4: Discrepancy Analysis ────────────────────────────────────────
    logger.info("=== Stage 4: Discrepancy Analysis ===")
    reports = compute_discrepancies(df, threshold=args.threshold)
    print_report(reports)
    export_report(reports, args.out_dir / f"{exam_name}_report.json")

    logger.info("Pipeline complete. Outputs written to: %s", args.out_dir)


if __name__ == "__main__":
    main()

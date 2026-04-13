"""Stage 3 — Score database: DataFrame construction, SQLite, CSV/JSON export."""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import pandas as pd

from .assessor import AssessmentResult
from .config import DB_PATH, TEACHER_CSV_COLS, TEACHER_SCORES_FILENAME

logger = logging.getLogger(__name__)

GRADES_SCHEMA_COLS = [
    "student_id",
    "exam",
    "question",
    "rubric_item",
    "ai_score",
    "teacher_score",
    "rationale",
]


def load_teacher_scores(exam_dir: Path) -> pd.DataFrame:
    """
    Read teacher_scores.csv from the exam directory.
    Returns an empty DataFrame (with correct columns) if the file is missing or malformed.
    """
    csv_path = Path(exam_dir) / TEACHER_SCORES_FILENAME
    if not csv_path.exists():
        logger.warning("teacher_scores.csv not found in %s — teacher scores will be NaN", exam_dir)
        return pd.DataFrame(columns=TEACHER_CSV_COLS)
    try:
        df = pd.read_csv(csv_path)
        # Validate required columns
        missing = [c for c in TEACHER_CSV_COLS if c not in df.columns]
        if missing:
            logger.error("teacher_scores.csv missing columns: %s", missing)
            return pd.DataFrame(columns=TEACHER_CSV_COLS)
        df["teacher_score"] = pd.to_numeric(df["teacher_score"], errors="coerce")
        # Normalise key columns to strings to ensure clean joins
        for col in ("student_id", "question", "rubric_item"):
            df[col] = df[col].astype(str).str.strip()
        return df[TEACHER_CSV_COLS]
    except Exception as exc:
        logger.error("Failed to load teacher_scores.csv: %s", exc)
        return pd.DataFrame(columns=TEACHER_CSV_COLS)


def build_dataframe(
    results: list[AssessmentResult],
    exam_name: str,
    teacher_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Flatten AssessmentResult objects into one row per rubric item, then
    left-join teacher scores on (student_id, question, rubric_item).
    """
    rows = []
    for result in results:
        if result.parse_error and not result.rubric_scores:
            # Record a single error row so failures are visible in the DB
            rows.append(
                {
                    "student_id": result.student_id,
                    "exam": exam_name,
                    "question": result.question_id,
                    "rubric_item": "__parse_error__",
                    "ai_score": None,
                    "teacher_score": None,
                    "rationale": None,
                }
            )
            continue
        for score in result.rubric_scores:
            rows.append(
                {
                    "student_id": result.student_id,
                    "exam": exam_name,
                    "question": result.question_id,
                    "rubric_item": score.rubric_item,
                    "ai_score": score.ai_score,
                    "teacher_score": None,  # filled by join below
                    "rationale": score.rationale,
                }
            )

    if not rows:
        logger.warning("No grading rows produced — returning empty DataFrame")
        return pd.DataFrame(columns=GRADES_SCHEMA_COLS)

    ai_df = pd.DataFrame(rows)
    # Normalise join keys
    for col in ("student_id", "question", "rubric_item"):
        ai_df[col] = ai_df[col].astype(str).str.strip()

    if teacher_df.empty:
        ai_df["teacher_score"] = None
        return ai_df[GRADES_SCHEMA_COLS]

    # Drop the placeholder teacher_score column, then left-join.
    # Normalize rubric_item keys: strip " (0-N points)" suffix the AI appends
    # so they match the bare labels used in teacher_scores.csv.
    ai_df = ai_df.drop(columns=["teacher_score"])
    ai_df["_rubric_key"] = ai_df["rubric_item"].str.replace(
        r"\s*\(\d+[-–]\d+\s+points?\)\s*$", "", regex=True
    ).str.strip()
    teacher_df = teacher_df.copy()
    teacher_df["_rubric_key"] = teacher_df["rubric_item"].str.strip()

    merged = ai_df.merge(
        teacher_df[["student_id", "question", "_rubric_key", "teacher_score"]],
        on=["student_id", "question", "_rubric_key"],
        how="left",
    )
    merged = merged.drop(columns=["_rubric_key"])
    return merged[GRADES_SCHEMA_COLS]


def save_to_sqlite(df: pd.DataFrame, db_path: str = DB_PATH) -> None:
    """Write/replace the 'grades' table in SQLite."""
    try:
        conn = sqlite3.connect(db_path)
        df.to_sql("grades", conn, if_exists="replace", index=False)
        conn.close()
        logger.info("Saved %d rows to SQLite: %s", len(df), db_path)
    except Exception as exc:
        logger.error("Failed to save to SQLite: %s", exc)


def export_csv(df: pd.DataFrame, out_path: Path) -> None:
    try:
        df.to_csv(out_path, index=False)
        logger.info("Exported CSV: %s", out_path)
    except Exception as exc:
        logger.error("CSV export failed: %s", exc)


def export_json(df: pd.DataFrame, out_path: Path) -> None:
    try:
        df.to_json(out_path, orient="records", indent=2)
        logger.info("Exported JSON: %s", out_path)
    except Exception as exc:
        logger.error("JSON export failed: %s", exc)

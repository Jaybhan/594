"""Stage 4 — Discrepancy analysis between AI scores and teacher scores."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .config import DISCREPANCY_MIN_DELTA, DISCREPANCY_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class DiscrepancyReport:
    rubric_item: str
    question: str
    total_graded: int
    count_discrepancies: int
    mae: float
    discrepancy_rate: float
    flagged: bool


def compute_discrepancies(
    df: pd.DataFrame,
    threshold: float = DISCREPANCY_THRESHOLD,
    discrepancy_min_delta: float = DISCREPANCY_MIN_DELTA,
) -> list[DiscrepancyReport]:
    """
    Compute per-(question, rubric_item) discrepancy statistics.
    Only rows where both ai_score and teacher_score are non-null are used.
    """
    scoreable = df.dropna(subset=["ai_score", "teacher_score"]).copy()
    if scoreable.empty:
        logger.warning("No rows with both ai_score and teacher_score — skipping discrepancy analysis")
        return []

    reports: list[DiscrepancyReport] = []
    for (question, rubric_item), group in scoreable.groupby(["question", "rubric_item"]):
        delta = (group["ai_score"] - group["teacher_score"]).abs()
        n = len(group)
        n_disc = int((delta > discrepancy_min_delta).sum())
        mae = float(delta.mean())
        rate = n_disc / n if n > 0 else 0.0
        flagged = rate > threshold

        reports.append(
            DiscrepancyReport(
                rubric_item=str(rubric_item),
                question=str(question),
                total_graded=n,
                count_discrepancies=n_disc,
                mae=round(mae, 4),
                discrepancy_rate=round(rate, 4),
                flagged=flagged,
            )
        )

    # Sort: flagged first, then by discrepancy_rate descending
    reports.sort(key=lambda r: (-int(r.flagged), -r.discrepancy_rate))
    return reports


def print_report(reports: list[DiscrepancyReport]) -> None:
    if not reports:
        print("No discrepancy data available (no rows with both AI and teacher scores).")
        return

    col_widths = {
        "question": max(8, max(len(r.question) for r in reports)),
        "rubric_item": max(11, max(len(r.rubric_item) for r in reports)),
    }
    header = (
        f"{'Question':<{col_widths['question']}}  "
        f"{'Rubric Item':<{col_widths['rubric_item']}}  "
        f"{'N':>5}  {'Discrepancies':>13}  {'MAE':>6}  {'Rate':>6}  {'Flag'}"
    )
    separator = "-" * len(header)
    print("\n=== Discrepancy Report ===")
    print(separator)
    print(header)
    print(separator)
    for r in reports:
        flag = "*** FLAGGED ***" if r.flagged else ""
        print(
            f"{r.question:<{col_widths['question']}}  "
            f"{r.rubric_item:<{col_widths['rubric_item']}}  "
            f"{r.total_graded:>5}  {r.count_discrepancies:>13}  "
            f"{r.mae:>6.3f}  {r.discrepancy_rate:>5.1%}  {flag}"
        )
    print(separator)

    flagged = [r for r in reports if r.flagged]
    if flagged:
        print(f"\n{len(flagged)} rubric item(s) flagged (discrepancy rate > threshold).")
    else:
        print("\nNo rubric items exceeded the discrepancy threshold.")


def export_report(reports: list[DiscrepancyReport], out_path: Path) -> None:
    try:
        data = [asdict(r) for r in reports]
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Exported discrepancy report: %s", out_path)
    except Exception as exc:
        logger.error("Failed to export discrepancy report: %s", exc)

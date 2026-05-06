"""
3x3 grading sweep: 3 prompts x 3 models across all exam directories.
Outputs to output_3x3/{prompt_name}/{model_name}/ for each combination.

PDF extraction runs once per exam and is reused across all 9 combos.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import anthropic

from grader.assessor import GraderAssessor, grade_exam
from grader.analyzer import compute_discrepancies, export_report
from grader.config import DISCREPANCY_THRESHOLD
from grader.database import build_dataframe, export_csv, export_json, load_teacher_scores
from grader.extractor import extract_exam_texts

# ── Prompts ──────────────────────────────────────────────────────────────────

PROMPT_A = """\
You are an expert exam grader. You will be given an exam question, a rubric, \
and a student response. Your job is to score the student's response against \
each rubric item independently.

IMPORTANT RULES:
- Score only based on the rubric provided. Do not invent criteria.
- Return ONLY valid JSON matching the schema provided. No additional prose.
- Never include, reference, or infer any teacher-assigned scores.
- If a rubric item cannot be assessed (e.g. illegible handwriting), set ai_score to null.
- Interpret garbled or partial mathematical notation charitably given the context."""

PROMPT_B = """\
You are an expert exam grader. After years of teaching, you have developed a finetuned \
ability to translate high detailed rubrics into student grades. You pay VERY close attention \
to the details of the rubrics, and want to provide grades and feedback that align as closely \
as possible to the rubric and solution given. Even if you feel the response could be more \
nuanced or detailed, you always give the base amount of points recommended in the rubric.

You will be given an exam question, a rubric, and a student response. Your job is to score \
the student's response against each rubric item independently. Your reasoning should be \
justified solely in the context of the rubric.

IMPORTANT RULES:
- Score only based on the rubric provided. Do not invent criteria.
- Return ONLY valid JSON matching the schema provided. No additional prose.
- Never include, reference, or infer any teacher-assigned scores.
- If a rubric item cannot be assessed (e.g. illegible handwriting), set ai_score to null.
- Interpret garbled or partial mathematical notation charitably given the context."""

PROMPT_C = """\
You are a calibrated AP exam grader trained to apply official scoring guidelines with high \
consistency and minimal subjectivity. Your goal is to replicate how experienced human graders \
award points: strictly rubric-aligned, conservative in interpretation, and consistent across responses.

You will be given:
  1. An exam question
  2. A rubric with discrete scoring items
  3. A student response

Your task is to evaluate each rubric item independently and assign a score based only on \
whether the student meets the exact criteria described.

Grading Principles:
- Treat each rubric item as a binary or discrete checkpoint, not a holistic judgment.
- Award points when the student clearly satisfies the rubric requirement, even if reasoning \
  is incomplete or imperfect, unless the rubric explicitly requires justification.
- Do not deduct points for minor arithmetic, notation, or wording errors unless the rubric \
  explicitly penalizes them.
- If a response contains correct work alongside incorrect reasoning, follow the rubric \
  strictly—award points if the rubric criteria are met.
- Avoid over-interpreting intent. Only award points supported by explicit evidence in the response.
- When multiple interpretations are possible, choose the most reasonable rubric-aligned \
  interpretation, but do not stretch beyond what is written.
- Match AP grading norms: partial credit is awarded only when explicitly allowed by the rubric.

Evaluation Principles — for each rubric item:
  1. Identify the exact requirement being tested.
  2. Locate relevant evidence in the student response.
  3. Determine whether the requirement is satisfied as written.
  4. Assign the score accordingly.

IMPORTANT RULES:
- Score only based on the rubric provided. Do not invent criteria.
- Return ONLY valid JSON matching the schema provided. No additional prose.
- Never include, reference, or infer any teacher-assigned scores.
- If a rubric item cannot be assessed (e.g. illegible handwriting), set ai_score to null.
- Interpret garbled or partial mathematical notation charitably given the context."""

PROMPTS: dict[str, str] = {
    "prompt_A": PROMPT_A,
    "prompt_B": PROMPT_B,
    "prompt_C": PROMPT_C,
}

MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}


def run_combo(
    exam_dir: Path,
    extraction: dict,
    assessor: GraderAssessor,
    out_dir: Path,
    threshold: float = DISCREPANCY_THRESHOLD,
) -> None:
    exam_name = exam_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    results = grade_exam(exam_dir, extraction, assessor)

    teacher_df = load_teacher_scores(exam_dir)
    df = build_dataframe(results, exam_name, teacher_df)

    export_csv(df, out_dir / f"{exam_name}_grades.csv")
    export_json(df, out_dir / f"{exam_name}_grades.json")

    reports = compute_discrepancies(df, threshold=threshold)
    export_report(reports, out_dir / f"{exam_name}_report.json")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("grading_3x3.log"),
        ],
    )
    logger = logging.getLogger(__name__)

    exams_root = Path("Exams")
    if not exams_root.exists():
        logger.error("Exams/ directory not found. Run from the project root.")
        sys.exit(1)

    exam_dirs = sorted(exams_root.iterdir())
    if not exam_dirs:
        logger.error("No exam directories found under Exams/")
        sys.exit(1)

    logger.info("Found %d exam(s): %s", len(exam_dirs), [d.name for d in exam_dirs])

    # Extract PDFs once per exam — reused across all 9 prompt/model combos
    logger.info("=== Pre-extracting all exam PDFs ===")
    extractions: dict[Path, dict] = {}
    for exam_dir in exam_dirs:
        logger.info("Extracting %s ...", exam_dir.name)
        extractions[exam_dir] = extract_exam_texts(exam_dir)

    client = anthropic.Anthropic()
    base_out = Path("output_3x3")
    total = len(PROMPTS) * len(MODELS) * len(exam_dirs)
    done = 0

    # Combos already completed — skip to avoid re-running
    skip = {("prompt_A", "haiku")}

    for prompt_name, prompt_text in PROMPTS.items():
        for model_name, model_id in MODELS.items():
            if (prompt_name, model_name) in skip:
                logger.info("Skipping %s / %s (already done)", prompt_name, model_name)
                done += len(exam_dirs)
                continue
            assessor = GraderAssessor(client, system_prompt=prompt_text, model_id=model_id)
            combo_dir = base_out / prompt_name / model_name

            for exam_dir in exam_dirs:
                done += 1
                logger.info(
                    "=== [%d/%d] %s / %s / %s ===",
                    done, total, prompt_name, model_name, exam_dir.name,
                )
                run_combo(exam_dir, extractions[exam_dir], assessor, combo_dir)

    logger.info("Done. All outputs written to %s/", base_out)


if __name__ == "__main__":
    main()

"""Stage 2 — AI-based assessment via Anthropic API with prompt caching."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic

from .config import MODEL_ID
from .extractor import ExtractionResult, extract_exam_texts

logger = logging.getLogger(__name__)

_JSON_SCHEMA_INSTRUCTION = """\
Return a JSON object with this exact schema (no prose before or after):
{
  "scores": [
    {
      "rubric_item": "<exact rubric item label>",
      "ai_score": <number or null if response is illegible for this item>,
      "max_score": <number>,
      "rationale": "<one sentence explaining the score>"
    }
  ]
}"""

_SYSTEM_PROMPT = """\
You are an expert exam grader. You will be given an exam question, a rubric, \
and a student response. Your job is to score the student's response against \
each rubric item independently.

IMPORTANT RULES:
- Score only based on the rubric provided. Do not invent criteria.
- Return ONLY valid JSON matching the schema provided. No additional prose.
- Never include, reference, or infer any teacher-assigned scores.
- If a rubric item cannot be assessed (e.g. illegible handwriting), set ai_score to null.
- Interpret garbled or partial mathematical notation charitably given the context."""


@dataclass
class RubricItemScore:
    rubric_item: str
    ai_score: float | None
    max_score: float
    rationale: str


@dataclass
class AssessmentResult:
    student_id: str
    question_id: str
    rubric_scores: list[RubricItemScore]
    raw_response: str
    parse_error: str | None = field(default=None)


class GraderAssessor:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def build_cached_prompt_blocks(
        self, question_text: str, rubric_text: str
    ) -> list[dict[str, Any]]:
        """Build the stable (question + rubric) content block with cache_control."""
        combined = (
            f"=== EXAM QUESTION ===\n{question_text}\n\n"
            f"=== RUBRIC ===\n{rubric_text}\n\n"
            "Score each rubric item independently using the schema provided."
        )
        return [
            {
                "type": "text",
                "text": combined,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def build_response_blocks(
        self, student_response_text: str, response_images: list[str]
    ) -> list[dict[str, Any]]:
        """Build content blocks for the student response (text or images)."""
        if response_images:
            # Handwritten work — send page images directly to Claude vision
            blocks: list[dict[str, Any]] = [
                {"type": "text", "text": "=== STUDENT RESPONSE (handwritten, see images) ==="}
            ]
            for b64 in response_images:
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": b64},
                })
            return blocks
        return [{"type": "text", "text": f"=== STUDENT RESPONSE ===\n{student_response_text}"}]

    def assess_response(
        self,
        question_text: str,
        rubric_text: str,
        student_response_text: str,
        student_id: str,
        question_id: str,
        cached_blocks: list[dict[str, Any]] | None = None,
        response_images: list[str] | None = None,
    ) -> AssessmentResult:
        """Score one student response against a question and rubric."""
        if cached_blocks is None:
            cached_blocks = self.build_cached_prompt_blocks(question_text, rubric_text)

        content_blocks: list[dict[str, Any]] = [
            *cached_blocks,
            *self.build_response_blocks(student_response_text, response_images or []),
            {
                "type": "text",
                "text": _JSON_SCHEMA_INSTRUCTION,
            },
        ]

        try:
            response = self.client.messages.create(
                model=MODEL_ID,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content_blocks}],
            )
            raw = response.content[0].text
        except Exception as exc:
            logger.error(
                "API call failed for student=%s question=%s: %s",
                student_id, question_id, exc,
            )
            return AssessmentResult(
                student_id=student_id,
                question_id=question_id,
                rubric_scores=[],
                raw_response="",
                parse_error=str(exc),
            )

        try:
            scores = self.parse_scores(raw)
        except Exception as exc:
            logger.error(
                "Score parsing failed for student=%s question=%s: %s",
                student_id, question_id, exc,
            )
            return AssessmentResult(
                student_id=student_id,
                question_id=question_id,
                rubric_scores=[],
                raw_response=raw,
                parse_error=str(exc),
            )

        return AssessmentResult(
            student_id=student_id,
            question_id=question_id,
            rubric_scores=scores,
            raw_response=raw,
        )

    def parse_scores(self, raw: str) -> list[RubricItemScore]:
        """Extract and parse JSON from model output robustly."""
        # Strip markdown fences if present
        fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        candidate = fence_match.group(1) if fence_match else raw.strip()

        # Find the outermost JSON object
        start = candidate.find("{")
        end = candidate.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"No JSON object found in model response: {raw[:300]}")
        candidate = candidate[start:end]

        data = json.loads(candidate)

        scores: list[RubricItemScore] = []
        for item in data.get("scores", []):
            scores.append(
                RubricItemScore(
                    rubric_item=item["rubric_item"],
                    ai_score=item.get("ai_score"),
                    max_score=float(item.get("max_score", 0)),
                    rationale=item.get("rationale", ""),
                )
            )
        return scores


def grade_exam(
    exam_dir: Path,
    extraction: dict,
    assessor: GraderAssessor,
) -> list[AssessmentResult]:
    """
    Stage 2 orchestrator: iterate over all (student, question) pairs and assess each.
    Skips pairs where question, rubric, or student response failed to extract.
    """
    questions = extraction.get("questions", {})
    rubrics = extraction.get("rubrics", {})
    responses = extraction.get("responses", {})

    results: list[AssessmentResult] = []

    for question_id in sorted(questions):
        q_result = questions[question_id]
        r_result = rubrics.get(question_id)

        if q_result.method == "failed":
            logger.warning("Skipping question %s — extraction failed", question_id)
            continue
        if r_result is None or r_result.method == "failed":
            logger.warning("Skipping question %s — rubric extraction failed", question_id)
            continue

        # Build cached blocks once per question (reused across all students)
        cached_blocks = assessor.build_cached_prompt_blocks(q_result.text, r_result.text)

        for student_id, student_responses in responses.items():
            s_result = student_responses.get(question_id)
            if s_result is None:
                logger.warning(
                    "Student %s has no response for question %s — skipping",
                    student_id, question_id,
                )
                continue
            if s_result.method == "failed":
                logger.warning(
                    "Student %s question %s response extraction failed — skipping",
                    student_id, question_id,
                )
                continue
            if s_result.method == "images" and not s_result.images:
                logger.warning(
                    "Student %s question %s yielded no images — skipping",
                    student_id, question_id,
                )
                continue

            logger.info("Grading student=%s question=%s (method=%s)",
                        student_id, question_id, s_result.method)
            result = assessor.assess_response(
                question_text=q_result.text,
                rubric_text=r_result.text,
                student_response_text=s_result.text,
                student_id=student_id,
                question_id=question_id,
                cached_blocks=cached_blocks,
                response_images=s_result.images if s_result.method == "images" else None,
            )
            results.append(result)

    return results

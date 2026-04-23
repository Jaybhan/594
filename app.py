"""
Streamlit web UI for the Automated Exam Grading Pipeline.

Run with:
    streamlit run app.py

Requires ANTHROPIC_API_KEY environment variable.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import tempfile
from pathlib import Path

import anthropic
import pandas as pd
import streamlit as st

from grader.assessor import GraderAssessor, grade_exam
from grader.analyzer import compute_discrepancies
from grader.config import DISCREPANCY_THRESHOLD
from grader.database import build_dataframe, load_teacher_scores
from grader.extractor import extract_exam_texts

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Exam Grader",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        color: white;
    }
    .main-header h1 { margin: 0; font-size: 2.2rem; }
    .main-header p  { margin: 0.4rem 0 0; opacity: 0.85; font-size: 1rem; }

    .step-card {
        background: #f8f9fb;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }
    .step-label {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #667eea;
        margin-bottom: 0.2rem;
    }
    .metric-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .flagged-row { background-color: #fff0f0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div class="main-header">
        <h1>📝 Exam Grader</h1>
        <p>Upload your question, rubric, and student responses — Claude will grade them for you.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def slugify(name: str) -> str:
    stem = Path(name).stem
    slug = re.sub(r"[^\w\-]", "_", stem).strip("_")
    return slug or "item"


def save_uploaded_pdf(uploaded_file, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(uploaded_file.read())
    uploaded_file.seek(0)


@st.cache_data(show_spinner=False)
def check_rubric_quality(rubric_bytes: bytes) -> tuple[bool, str]:
    """Return (is_adequate, feedback). Cached by rubric content."""
    if not api_key:
        return True, ""
    client = anthropic.Anthropic(api_key=api_key)
    rubric_b64 = base64.standard_b64encode(rubric_bytes).decode()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": rubric_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "You are reviewing a document uploaded as a grading rubric for an exam question. "
                        "First check: is this actually a rubric? A rubric specifies grading criteria, point values, or scoring guidelines. "
                        "If it is NOT a rubric (e.g. it is a student response, blank page, question sheet, or unrelated document), set adequate=false. "
                        "If it IS a rubric, evaluate whether it is specific and objective enough for consistent automated grading. "
                        "A good rubric clearly defines point values, specifies what constitutes correct and incorrect responses, "
                        "and leaves little room for subjective interpretation. "
                        "Set adequate=false if the document is not a rubric, or if the rubric is too vague or ambiguous for objective grading. "
                        'Respond with valid JSON only, no other text: {"adequate": true_or_false, "feedback": "one or two sentences explaining your assessment"}.'
                    ),
                },
            ],
        }],
    )
    raw = response.content[0].text.strip()
    try:
        data = json.loads(raw)
        return bool(data["adequate"]), str(data.get("feedback", ""))
    except Exception:
        return False, f"Could not parse rubric quality response: {raw[:200]}"


def build_exam_dir(
    tmp_dir: Path,
    exam_name: str,
    questions: dict,
    rubrics: dict,
    responses: dict,
    teacher_csv,
) -> Path:
    exam_dir = tmp_dir / exam_name
    for qid, f in questions.items():
        save_uploaded_pdf(f, exam_dir / "questions" / f"{qid}.pdf")
    for qid, f in rubrics.items():
        save_uploaded_pdf(f, exam_dir / "rubric" / f"{qid}.pdf")
    for sid, q_map in responses.items():
        for qid, f in q_map.items():
            save_uploaded_pdf(f, exam_dir / "sample_responses" / sid / f"{qid}.pdf")
    if teacher_csv is not None:
        (exam_dir / "teacher_scores.csv").write_bytes(teacher_csv.read())
    return exam_dir


def run_pipeline(exam_dir: Path, exam_name: str, threshold: float, api_key: str):
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(fmt)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        client = anthropic.Anthropic(api_key=api_key)
        assessor = GraderAssessor(client)
        extraction = extract_exam_texts(exam_dir)
        results = grade_exam(exam_dir, extraction, assessor)
        teacher_df = load_teacher_scores(exam_dir)
        df = build_dataframe(results, exam_name, teacher_df)
        reports = compute_discrepancies(df, threshold=threshold)
    finally:
        root_logger.removeHandler(handler)
    return df, reports, log_stream.getvalue()


# ── API Key ───────────────────────────────────────────────────────────────────

api_key = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Step 1: Exam Setup ────────────────────────────────────────────────────────

st.markdown('<div class="step-label">Step 1</div>', unsafe_allow_html=True)
with st.expander("Exam Setup", expanded=True):
    col_name, col_thresh = st.columns([2, 1])
    with col_name:
        exam_name = st.text_input(
            "Exam name",
            value="my-exam",
            help="Used for output filenames. Letters, numbers, and hyphens only.",
        )
    with col_thresh:
        threshold = st.slider(
            "Discrepancy threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(DISCREPANCY_THRESHOLD),
            step=0.05,

            help="Rubric items with AI/teacher disagreement above this rate are flagged.",
        )

# ── Step 2: Questions & Rubrics ───────────────────────────────────────────────

st.markdown('<div class="step-label">Step 2</div>', unsafe_allow_html=True)
with st.expander("Questions & Rubrics", expanded=True):
    st.caption("Upload one PDF per question alongside its rubric. Filenames don't need to match.")
    num_questions = st.number_input(
        "Number of questions", min_value=1, max_value=20, value=1, step=1, key="num_q"
    )

    question_files: dict = {}
    rubric_files: dict = {}

    for i in range(int(num_questions)):
        col_q, col_r = st.columns(2)
        with col_q:
            qf = st.file_uploader(
                f"Question {i + 1} PDF",
                type="pdf",
                key=f"q_{i}",
            )
        with col_r:
            rf = st.file_uploader(
                f"Rubric {i + 1} PDF",
                type="pdf",
                key=f"r_{i}",
            )
            if rf is not None:
                rubric_bytes = rf.read()
                rf.seek(0)
                with st.spinner("Checking rubric quality…"):
                    adequate, feedback = check_rubric_quality(rubric_bytes)
                if not adequate:
                    st.warning(f"**Rubric may be too vague for consistent grading.** {feedback}")
        if qf is not None:
            qid = slugify(qf.name)
            question_files[qid] = qf
            if rf is not None:
                rubric_files[qid] = rf  # key rubric by question's ID, not rubric filename
        elif rf is not None:
            rubric_files[slugify(rf.name)] = rf

# ── Step 3: Student Responses ─────────────────────────────────────────────────

st.markdown('<div class="step-label">Step 3</div>', unsafe_allow_html=True)
with st.expander("Student Responses", expanded=True):
    st.caption(
        "For each student, give them an ID and upload one PDF **per question**."
    )
    num_students = st.number_input(
        "Number of students", min_value=1, max_value=200, value=1, step=1, key="num_s"
    )

    response_files: dict = {}
    q_ids = sorted(question_files.keys())

    for s in range(int(num_students)):
        with st.container():
            sid_input = st.text_input(
                f"Student {s + 1} ID",
                value=f"student_{s + 1:03d}",
                key=f"sid_{s}",
            )
            sid = slugify(sid_input) if sid_input.strip() else f"student_{s + 1:03d}"

            if q_ids:
                n_cols = min(len(q_ids), 4)
                cols = st.columns(n_cols)
                student_responses: dict = {}
                for j, qid in enumerate(q_ids):
                    with cols[j % n_cols]:
                        rf = st.file_uploader(
                            qid,
                            type="pdf",
                            key=f"resp_{s}_{qid}",
                            help=f"Response for question {qid}",
                            label_visibility="visible",
                        )
                        if rf is not None:
                            student_responses[qid] = rf
                if student_responses:
                    response_files[sid] = student_responses
            else:
                st.info("Upload questions in Step 2 first to see response slots here.")

            if s < int(num_students) - 1:
                st.divider()

# ── Step 4: Teacher Scores (optional) ────────────────────────────────────────

st.markdown('<div class="step-label">Step 4 — Optional</div>', unsafe_allow_html=True)
with st.expander("Teacher Scores (for discrepancy analysis)", expanded=False):
    st.caption(
        "Upload a CSV with columns: `student_id, question, rubric_item, teacher_score`. "
        "If omitted, the Discrepancy Analysis tab will be empty."
    )
    teacher_csv = st.file_uploader("teacher_scores.csv", type="csv", key="teacher_csv")
    if teacher_csv is not None:
        preview = pd.read_csv(teacher_csv)
        teacher_csv.seek(0)
        st.dataframe(preview.head(10), use_container_width=True)

# ── Run button ────────────────────────────────────────────────────────────────

st.markdown("---")
run_clicked = st.button("▶ Run Grading Pipeline", type="primary", use_container_width=True)

if run_clicked:
    errors = []
    if not api_key:
        errors.append("ANTHROPIC_API_KEY environment variable is not set.")
    if not exam_name or not re.match(r"^[\w\-]+$", exam_name):
        errors.append("Exam name must contain only letters, numbers, and hyphens.")
    if not question_files:
        errors.append("Upload at least one question PDF in Step 2.")
    missing_rubrics = set(question_files) - set(rubric_files)
    if missing_rubrics:
        errors.append(f"Missing rubric PDF(s) for: {', '.join(sorted(missing_rubrics))}")
    if not response_files:
        errors.append("Upload at least one student response in Step 3.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            exam_dir = build_exam_dir(
                tmp_path,
                slugify(exam_name),
                question_files,
                rubric_files,
                response_files,
                teacher_csv,
            )
            with st.spinner("Grading in progress — this may take a minute…"):
                try:
                    df, reports, log_lines = run_pipeline(
                        exam_dir, slugify(exam_name), threshold, api_key
                    )
                    st.session_state["results"] = (df, reports, log_lines, exam_name)
                    st.success(
                        f"Done! Graded **{len(df)}** rubric-item rows across "
                        f"**{df['student_id'].nunique()}** student(s) and "
                        f"**{df['question'].nunique()}** question(s)."
                    )
                except Exception as exc:
                    st.error(f"Pipeline failed: {exc}")
                    st.exception(exc)

# ── Results ───────────────────────────────────────────────────────────────────


def render_results(df: pd.DataFrame, reports: list, log_lines: str, name: str) -> None:
    st.markdown("---")
    st.subheader("Results")

    # Top-level metrics
    n_students = df["student_id"].nunique()
    n_questions = df["question"].nunique()
    n_flagged = sum(1 for r in reports if r.flagged)
    avg_score = df["ai_score"].mean() if not df.empty else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Students graded", n_students)
    m2.metric("Questions", n_questions)
    m3.metric("Avg AI score", f"{avg_score:.2f}")
    m4.metric("Flagged rubric items", n_flagged, delta=None)

    tab_grades, tab_summary, tab_disc, tab_logs = st.tabs(
        ["📋 Raw Grades", "📊 Score Summary", "⚠️ Discrepancy Analysis", "🪵 Pipeline Logs"]
    )

    # ── Raw Grades ────────────────────────────────────────────────────────────
    with tab_grades:
        st.markdown("Per-rubric-item grades for every student.")
        display_df = df[["student_id", "question", "rubric_item", "ai_score", "teacher_score", "rationale"]]
        try:
            styled = display_df.style.background_gradient(subset=["ai_score"], cmap="RdYlGn")
            st.dataframe(styled, use_container_width=True)
        except Exception:
            st.dataframe(display_df, use_container_width=True)

        st.download_button(
            "⬇ Download grades CSV",
            data=df.to_csv(index=False).encode(),
            file_name=f"{name}_grades.csv",
            mime="text/csv",
        )

    # ── Score Summary ─────────────────────────────────────────────────────────
    with tab_summary:
        if df.empty or "ai_score" not in df.columns:
            st.info("No grade data to summarize.")
        else:
            st.markdown("**Total AI score per student per question**")
            pivot = (
                df.groupby(["student_id", "question"])["ai_score"]
                .sum()
                .reset_index()
                .pivot(index="student_id", columns="question", values="ai_score")
            )
            pivot.columns.name = None
            try:
                st.dataframe(
                    pivot.style.background_gradient(cmap="Blues"),
                    use_container_width=True,
                )
            except Exception:
                st.dataframe(pivot, use_container_width=True)

            st.markdown("**Total score per student (all questions combined)**")
            totals = df.groupby("student_id")["ai_score"].sum().reset_index()
            totals.columns = ["Student", "Total Score"]
            st.bar_chart(totals.set_index("Student"))

    # ── Discrepancy Analysis ──────────────────────────────────────────────────
    with tab_disc:
        if not reports:
            st.info(
                "No discrepancy data available. "
                "Upload a `teacher_scores.csv` in Step 4 to enable this tab."
            )
        else:
            disc_rows = [
                {
                    "Question": r.question,
                    "Rubric Item": r.rubric_item,
                    "N Graded": r.total_graded,
                    "Discrepancies": r.count_discrepancies,
                    "MAE": round(r.mae, 3),
                    "Rate": r.discrepancy_rate,
                    "Flagged": r.flagged,
                }
                for r in reports
            ]
            disc_df = pd.DataFrame(disc_rows)

            def highlight_flagged(row):
                if row["Flagged"]:
                    return ["background-color: #ffdddd"] * len(row)
                return [""] * len(row)

            display_cols = ["Question", "Rubric Item", "N Graded", "Discrepancies", "MAE", "Rate", "Flagged"]
            try:
                styled_disc = (
                    disc_df[display_cols]
                    .style.apply(highlight_flagged, axis=1)
                    .format({"Rate": "{:.1%}"})
                )
                st.dataframe(styled_disc, use_container_width=True)
            except Exception:
                st.dataframe(disc_df[display_cols], use_container_width=True)

            if n_flagged:
                st.warning(
                    f"{n_flagged} rubric item(s) flagged "
                    f"(discrepancy rate > {threshold:.0%})"
                )
            else:
                st.success("No rubric items exceeded the discrepancy threshold.")

            st.markdown("**Mean Absolute Error per rubric item**")
            mae_df = pd.DataFrame({
                "label": [f"{r.question} / {r.rubric_item[:25]}" for r in reports],
                "MAE": [r.mae for r in reports],
            }).set_index("label")
            st.bar_chart(mae_df)

            st.download_button(
                "⬇ Download discrepancy report CSV",
                data=disc_df.to_csv(index=False).encode(),
                file_name=f"{name}_discrepancy.csv",
                mime="text/csv",
            )

    # ── Pipeline Logs ─────────────────────────────────────────────────────────
    with tab_logs:
        st.markdown("Raw log output from the grading pipeline.")
        st.code(log_lines or "(no log output)", language="text")


if "results" in st.session_state:
    df_r, reports_r, logs_r, name_r = st.session_state["results"]
    render_results(df_r, reports_r, logs_r, name_r)

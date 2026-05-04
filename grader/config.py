MODEL_ID = "claude-sonnet-4-6"
AVAILABLE_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
]
DISCREPANCY_THRESHOLD: float = 0.20
DISCREPANCY_MIN_DELTA: float = 0.5
DB_PATH = "grading.db"
TEACHER_SCORES_FILENAME = "teacher_scores.csv"
TEACHER_CSV_COLS = ["student_id", "question", "rubric_item", "teacher_score"]
OCR_TEXT_MIN_CHARS = 1000

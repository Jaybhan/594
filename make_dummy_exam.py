"""
Creates a dummy Exams/AP-History/ folder with:
  - 2 questions (q1.pdf, q2.pdf)
  - 2 rubrics  (q1.pdf, q2.pdf)
  - 2 students (student_001, student_002), each with q1.pdf and q2.pdf
  - teacher_scores.csv with rubric-item-level scores
"""
import csv
from pathlib import Path
import fitz  # PyMuPDF


def make_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(50, 50, 550, 780),
        text,
        fontsize=12,
        fontname="helv",
        color=(0, 0, 0),
    )
    doc.save(str(path))
    doc.close()
    print(f"  Created: {path}")


# ── Content ──────────────────────────────────────────────────────────────────

Q1_TEXT = """\
Question 1 (10 points)

Explain the causes of World War I. Your answer should discuss at least THREE
distinct factors that contributed to the outbreak of the war in 1914.
Include specific examples where relevant.
"""

Q1_RUBRIC = """\
Question 1 Rubric

Rubric Item: Thesis Statement (0-2 points)
  2 = Clear, defensible thesis that addresses multiple causes.
  1 = Vague or partially correct thesis.
  0 = No thesis or off-topic.

Rubric Item: Cause 1 – Alliance System (0-2 points)
  2 = Correctly explains how entangling alliances escalated a local conflict.
  1 = Mentions alliances but lacks explanation.
  0 = Not addressed.

Rubric Item: Cause 2 – Nationalism (0-2 points)
  2 = Describes nationalist tensions in Austria-Hungary or the Balkans.
  1 = Mentions nationalism vaguely.
  0 = Not addressed.

Rubric Item: Cause 3 – Militarism (0-2 points)
  2 = Explains the arms race and its role in war readiness.
  1 = Mentions militarism without explanation.
  0 = Not addressed.

Rubric Item: Evidence & Specificity (0-2 points)
  2 = Uses at least two specific historical examples (dates, events, figures).
  1 = One specific example.
  0 = No specific examples.
"""

Q2_TEXT = """\
Question 2 (8 points)

Compare and contrast the economic policies of the New Deal (1933) with
those of Reaganomics (1981). What were the core assumptions of each
approach, and how effective were they in addressing economic crises?
"""

Q2_RUBRIC = """\
Question 2 Rubric

Rubric Item: New Deal Summary (0-2 points)
  2 = Accurately describes key programs (e.g., CCC, WPA, Social Security).
  1 = Partially correct or incomplete.
  0 = Incorrect or missing.

Rubric Item: Reaganomics Summary (0-2 points)
  2 = Accurately describes supply-side economics, tax cuts, deregulation.
  1 = Partially correct or incomplete.
  0 = Incorrect or missing.

Rubric Item: Comparison / Contrast (0-2 points)
  2 = Explicitly identifies at least two meaningful differences or similarities.
  1 = Implicit or superficial comparison.
  0 = No comparison attempted.

Rubric Item: Effectiveness Evaluation (0-2 points)
  2 = Provides evidence-backed judgment on outcomes for both policies.
  1 = Evaluates only one policy or lacks evidence.
  0 = No evaluation.
"""

# ── Student responses ─────────────────────────────────────────────────────────

S1_Q1 = """\
Student 001 – Response to Question 1

World War I broke out due to a combination of political, military, and
social forces that had been building for decades.

The alliance system was perhaps the most direct cause. Europe had divided
itself into two armed camps: the Triple Alliance (Germany, Austria-Hungary,
Italy) and the Triple Entente (France, Russia, Britain). When Archduke Franz
Ferdinand was assassinated in Sarajevo on June 28, 1914, Austria-Hungary
declared war on Serbia, which triggered a chain reaction that pulled every
major power into the conflict within weeks.

Nationalism also played a pivotal role. Pan-Slavic movements in the Balkans
threatened the Austro-Hungarian Empire, which feared the breakup of its
multi-ethnic state. Serbia's ambition to unite South Slavic peoples was seen
as an existential threat by Vienna.

Finally, militarism had created a culture of war readiness. Germany's naval
build-up directly challenged British supremacy at sea. The Schlieffen Plan
demonstrated how military planning had taken on a life of its own, leaving
diplomats little room to maneuver once mobilization began.

In summary, alliances, nationalism, and militarism combined with the spark
of the assassination to produce a catastrophic war.
"""

S1_Q2 = """\
Student 001 – Response to Question 2

The New Deal and Reaganomics represent opposite poles of American economic
thinking.

Roosevelt's New Deal (1933) responded to the Great Depression through
massive federal intervention. Programs like the Civilian Conservation Corps
(CCC) and Works Progress Administration (WPA) put millions of unemployed
Americans to work on public projects. The Social Security Act (1935)
established a safety net. The core assumption was that the government must
step in when markets fail.

Reagan's supply-side economics took the opposite view. The Economic Recovery
Tax Act of 1981 cut the top marginal income tax rate from 70% to 50% (later
to 28%), arguing that tax relief for producers would "trickle down" to
workers. Deregulation and cuts to domestic spending were also hallmarks.

Comparing the two: the New Deal expanded government, while Reaganomics
contracted it. Both were responses to economic downturns, but they disagreed
fundamentally about the role of the state.

In terms of effectiveness, the New Deal stabilized the banking system and
reduced unemployment from 25% to about 14% by 1937, though full recovery
came only with WWII spending. Reagan's policies contributed to strong GDP
growth in 1983-1984 but also tripled the national debt and widened income
inequality.
"""

S2_Q1 = """\
Student 002 – Response to Question 1

There were several reasons why World War I started. The main one was the
assassination of Franz Ferdinand in 1914. After that, countries started
fighting because of their alliances.

Nationalism was also a cause. People in different countries wanted
independence and this created conflicts especially in places like the Balkans.

The arms race between European powers made things worse. Germany was building
up its military and navy, and other countries did the same.

These three things together caused the war to happen in 1914.
"""

S2_Q2 = """\
Student 002 – Response to Question 2

The New Deal was made by Franklin Roosevelt to help the US economy during
the Great Depression. He created programs to give people jobs.

Reaganomics was Ronald Reagan's idea that if you cut taxes for rich people
and businesses, the money would trickle down to everyone else.

The New Deal used government spending, while Reaganomics cut government
spending. They are opposites in that way.

The New Deal helped lower unemployment. Reagan's policies caused the economy
to grow in some years but the debt also went up.
"""

# ── Teacher scores ────────────────────────────────────────────────────────────

TEACHER_SCORES = [
    # student_001, q1
    ("student_001", "q1", "Thesis Statement",        2),
    ("student_001", "q1", "Cause 1 – Alliance System", 2),
    ("student_001", "q1", "Cause 2 – Nationalism",   2),
    ("student_001", "q1", "Cause 3 – Militarism",    2),
    ("student_001", "q1", "Evidence & Specificity",  2),
    # student_001, q2
    ("student_001", "q2", "New Deal Summary",         2),
    ("student_001", "q2", "Reaganomics Summary",      2),
    ("student_001", "q2", "Comparison / Contrast",   2),
    ("student_001", "q2", "Effectiveness Evaluation", 2),
    # student_002, q1
    ("student_002", "q1", "Thesis Statement",         0),
    ("student_002", "q1", "Cause 1 – Alliance System", 1),
    ("student_002", "q1", "Cause 2 – Nationalism",   1),
    ("student_002", "q1", "Cause 3 – Militarism",    1),
    ("student_002", "q1", "Evidence & Specificity",  0),
    # student_002, q2
    ("student_002", "q2", "New Deal Summary",         1),
    ("student_002", "q2", "Reaganomics Summary",      1),
    ("student_002", "q2", "Comparison / Contrast",   1),
    ("student_002", "q2", "Effectiveness Evaluation", 1),
]

# ── Build the folder structure ────────────────────────────────────────────────

base = Path("Exams/AP-History")

print("Creating dummy exam: Exams/AP-History/")

make_pdf(base / "questions" / "q1.pdf", Q1_TEXT)
make_pdf(base / "questions" / "q2.pdf", Q2_TEXT)
make_pdf(base / "rubric"    / "q1.pdf", Q1_RUBRIC)
make_pdf(base / "rubric"    / "q2.pdf", Q2_RUBRIC)
make_pdf(base / "sample_responses" / "student_001" / "q1.pdf", S1_Q1)
make_pdf(base / "sample_responses" / "student_001" / "q2.pdf", S1_Q2)
make_pdf(base / "sample_responses" / "student_002" / "q1.pdf", S2_Q1)
make_pdf(base / "sample_responses" / "student_002" / "q2.pdf", S2_Q2)

csv_path = base / "teacher_scores.csv"
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["student_id", "question", "rubric_item", "teacher_score"])
    writer.writerows(TEACHER_SCORES)
print(f"  Created: {csv_path}")

print("\nDone! Run the pipeline with:")
print("  python3 code.py Exams/AP-History --out-dir output/")

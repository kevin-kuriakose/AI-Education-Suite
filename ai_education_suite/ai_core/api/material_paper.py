# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Generates an AI Question Paper Draft from teacher-uploaded material (PDF or
DOCX chapter/notes) rather than purely from Topic Tags. Two generation modes:
  - "class_performance" (default): weights questions toward the weakest
    topics from the most recent Class Performance Snapshot for this
    course/student group, same signal the existing weakness-based generator
    uses.
  - "easy" / "medium" / "hard": every question is generated at that single
    difficulty level, ignoring class performance.

Image-based material (photographed textbook pages) is intentionally out of
scope for this first version — PDF and DOCX only. Extend extract_text() to
add image OCR (via the same Groq vision model used for grading) later.
"""

import os

import frappe
from frappe.utils import nowdate
from frappe.utils.file_manager import get_file_path

from ai_education_suite.ai_core.utils.claude_client import ClaudeClientError, call_claude_json

MAX_MATERIAL_CHARS = 15000  # keep prompts a reasonable size / cost


def extract_text(file_url):
	path = get_file_path(file_url)
	ext = os.path.splitext(path)[1].lower()

	if ext == ".pdf":
		try:
			from pypdf import PdfReader
		except ImportError:
			frappe.throw(
				"pypdf is not installed on this bench. Run: "
				"./env/bin/pip install pypdf --break-system-packages"
			)
		reader = PdfReader(path)
		text = "\n".join(page.extract_text() or "" for page in reader.pages)

	elif ext == ".docx":
		try:
			import docx
		except ImportError:
			frappe.throw(
				"python-docx is not installed on this bench. Run: "
				"./env/bin/pip install python-docx --break-system-packages"
			)
		document = docx.Document(path)
		text = "\n".join(p.text for p in document.paragraphs)

	else:
		frappe.throw(f"Unsupported file type '{ext}'. Upload a PDF or DOCX file.")

	text = text.strip()
	if not text:
		frappe.throw("Couldn't extract any text from that file \u2014 it may be a scanned/image-only PDF.")
	return text[:MAX_MATERIAL_CHARS]


def _get_weak_topics(course, student_group):
	filters = {"course": course}
	if student_group:
		filters["student_group"] = student_group
	snapshot_name = frappe.db.get_value(
		"Class Performance Snapshot", filters, "name", order_by="creation desc"
	)
	if not snapshot_name:
		return None, []
	snapshot = frappe.get_doc("Class Performance Snapshot", snapshot_name)
	weak = [
		row.topic
		for row in snapshot.weakness_table
		if (row.weakness_level or "").lower() in ("high", "medium")
	]
	return snapshot_name, weak


@frappe.whitelist()
def generate_question_paper_from_material(
	file_url, course, student_group=None, num_questions=10, mode="class_performance", total_marks=None
):
	num_questions = int(num_questions)
	material_text = extract_text(file_url)

	snapshot_name = None
	instruction = ""
	if mode == "class_performance":
		snapshot_name, weak_topics = _get_weak_topics(course, student_group)
		if weak_topics:
			instruction = (
				f"Weight the questions toward these topics, which the class is currently weak in: "
				f"{', '.join(weak_topics)}. Roughly 60% of questions should come from these topics, "
				"the rest can cover other material below."
			)
		else:
			instruction = (
				"No class performance data is available yet, so cover the material below evenly."
			)
	elif mode in ("easy", "medium", "hard"):
		instruction = f"Every question must be at '{mode}' difficulty level."
	else:
		frappe.throw(f"Unknown mode '{mode}'. Use class_performance, easy, medium, or hard.")

	prompt = f"""You are creating an exam question paper from the teaching material below.

TEACHING MATERIAL:
---
{material_text}
---

Generate exactly {num_questions} questions based on this material. {instruction}

Respond with a JSON object of the shape:
{{"questions": [
  {{"question_text": "...", "topic": "short topic name", "marks": 5,
    "difficulty": "Easy|Medium|Hard", "question_type": "Short Answer|Long Answer|Numerical|MCQ"}}
]}}
Marks per question should be reasonable for the difficulty (Easy: 2-4, Medium: 5-8, Hard: 8-12).
No preamble, no markdown code fences, just the JSON object."""

	try:
		parsed = call_claude_json(prompt, max_tokens=4000)
	except ClaudeClientError as e:
		frappe.throw(str(e))

	questions = parsed.get("questions") if isinstance(parsed, dict) else parsed
	if not isinstance(questions, list) or not questions:
		frappe.throw("The AI model did not return a recognizable list of questions. Try again.")

	draft = frappe.new_doc("AI Question Paper Draft")
	mode_label = {"class_performance": "Class Performance", "easy": "Easy", "medium": "Medium", "hard": "Hard"}[mode]
	draft.title = f"{course} - {mode_label} Paper - {nowdate()}"
	draft.course = course
	if student_group:
		draft.student_group = student_group
	if snapshot_name:
		draft.class_performance_snapshot = snapshot_name
	draft.status = "Draft"
	draft.generated_on = frappe.utils.now_datetime()

	computed_total = 0
	for q in questions:
		marks = q.get("marks") or 0
		computed_total += marks
		draft.append("questions", {
			"question_text": q.get("question_text", ""),
			"topic": q.get("topic", ""),
			"marks": marks,
			"difficulty": q.get("difficulty", mode_label if mode != "class_performance" else "Medium"),
			"question_type": q.get("question_type", "Short Answer"),
		})
	draft.total_marks = float(total_marks) if total_marks else computed_total

	draft.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": draft.name}

# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Image-based grading: teacher uploads a photo of the question paper and a
photo of the student's answer sheet. A vision-capable Groq model reads both,
matches answers to question numbers, and grades each one. Results are saved
as AI Grading Suggestion records (never auto-finalized — same human-in-the-loop
pattern as the rest of this app).
"""

import base64
import mimetypes
import os

import frappe
from frappe.utils.file_manager import get_file_path

from ai_education_suite.ai_core.utils.claude_client import ClaudeClientError, call_claude_vision

GRADING_PROMPT = """You will be shown two images:
1. A question paper (with numbered questions and, where visible, marks per question)
2. A student's handwritten or typed answer sheet, answering those same numbered questions

Read both images carefully. For each question number that appears in the question paper AND
has a corresponding answer on the answer sheet, produce one entry with:
- question_number (integer)
- question_text (the question, transcribed from the question paper image)
- max_score (the marks for that question if visible on the question paper, otherwise your best
  reasonable estimate as a number)
- student_answer (the student's answer, transcribed from the answer sheet image as accurately
  as you can read it)
- suggested_score (a number between 0 and max_score, reflecting how well the answer addresses
  the question)
- rationale (1-2 sentences explaining the score \u2014 what was right, what was missing or wrong)

If a question has no corresponding answer on the answer sheet, still include it with
student_answer set to "(no answer found)" and suggested_score 0.

Respond ONLY with a JSON object of the shape:
{"results": [ {"question_number": 1, "question_text": "...", "max_score": 8,
"student_answer": "...", "suggested_score": 6, "rationale": "..."}, ... ]}
No preamble, no markdown code fences, just the JSON object.
"""


def _file_to_data_url(file_url):
	"""Reads a Frappe-attached file (public or private) from disk and returns
	a base64 data: URL suitable for Groq's image_url content blocks."""
	path = get_file_path(file_url)
	mime_type, _ = mimetypes.guess_type(path)
	mime_type = mime_type or "image/jpeg"
	with open(path, "rb") as f:
		encoded = base64.b64encode(f.read()).decode("utf-8")
	return f"data:{mime_type};base64,{encoded}"


@frappe.whitelist()
def grade_from_images(answer_sheet_image, student, question_paper_image=None, question_paper_upload=None, course=None):
	"""
	Exactly one of question_paper_image (a freshly uploaded file URL) or
	question_paper_upload (the name of an existing AI Question Paper Upload
	record, reused across students) must be given.
	answer_sheet_image: file URL from an already-uploaded Frappe file.
	student: Student docname to attribute the grading suggestions to.
	course: optional Course docname.
	Returns {"created": [<AI Grading Suggestion names>], "results": [...]}
	"""
	if not frappe.db.exists("Student", student):
		frappe.throw(f"Student {student} not found.")

	if question_paper_upload:
		image_url = frappe.db.get_value(
			"AI Question Paper Upload", question_paper_upload, "question_paper_image"
		)
		if not image_url:
			frappe.throw(f"AI Question Paper Upload {question_paper_upload} not found.")
	elif question_paper_image:
		image_url = question_paper_image
	else:
		frappe.throw("Either question_paper_image or question_paper_upload is required.")

	question_paper_data_url = _file_to_data_url(image_url)
	answer_sheet_data_url = _file_to_data_url(answer_sheet_image)

	try:
		parsed = call_claude_vision(
			GRADING_PROMPT,
			[question_paper_data_url, answer_sheet_data_url],
			json_mode=True,
			max_tokens=3000,
		)
	except ClaudeClientError as e:
		frappe.throw(str(e))

	results = parsed.get("results") if isinstance(parsed, dict) else parsed
	if not isinstance(results, list):
		frappe.throw("The AI model did not return a recognizable list of graded questions. Try again.")

	student_doc = frappe.get_cached_doc("Student", student)
	created = []
	for item in results:
		grading = frappe.new_doc("AI Grading Suggestion")
		grading.student = student
		grading.student_name = student_doc.student_name
		if course:
			grading.course = course
		grading.question_reference = (
			f"Q{item.get('question_number', '?')}. {item.get('question_text', '')}"
		)
		grading.student_answer = item.get("student_answer", "")
		grading.max_score = item.get("max_score") or 0
		grading.suggested_score = item.get("suggested_score") or 0
		grading.ai_rationale = item.get("rationale", "")
		grading.status = "Pending Review"
		grading.insert(ignore_permissions=True, ignore_mandatory=True)
		created.append(grading.name)

	frappe.db.commit()
	return {"created": created, "results": results}

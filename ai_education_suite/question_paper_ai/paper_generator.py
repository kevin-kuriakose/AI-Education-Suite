# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Generates a draft question paper weighted toward weak topics identified in a
Class Performance Snapshot. Pulls syllabus text from linked Course Content
where available. Always lands as a Draft for teacher review/edit — never
auto-published or auto-sent to students.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime
from ai_education_suite.ai_core.utils import claude_client


@frappe.whitelist()
def generate_question_paper(class_performance_snapshot, total_marks=50, remedial_ratio=60, num_questions=10):
	if not claude_client.is_module_enabled("enable_question_paper_ai"):
		frappe.throw(_("Question Paper AI is disabled in AI Settings."))

	snapshot = frappe.get_doc("Class Performance Snapshot", class_performance_snapshot)
	total_marks = float(total_marks)
	remedial_ratio = float(remedial_ratio)
	num_questions = int(num_questions)

	weak_topics = [
		{"topic": r.topic, "average_score": r.average_score}
		for r in snapshot.weakness_table if r.weakness_level in ("High", "Medium")
	]
	all_topics = [r.topic for r in snapshot.weakness_table] or ["General"]

	syllabus_context = _get_syllabus_context(snapshot.course)

	system = (
		"You are an experienced teacher setting a class question paper. You weight questions toward "
		"topics where the class is weak, without making the paper unfairly hard, and you keep marks "
		"distribution sensible. You only use topics that were given to you."
	)
	prompt = (
		f"Course: {snapshot.course}\n"
		f"Class overall average: {snapshot.overall_average}%\n"
		f"All topics covered: {', '.join(all_topics)}\n"
		f"Weak topics (need more coverage): {weak_topics}\n"
		f"Syllabus context (may be partial):\n{syllabus_context}\n\n"
		f"Generate a question paper with exactly {num_questions} questions totalling {total_marks} marks. "
		f"Approximately {remedial_ratio}% of total marks should come from weak topics, the rest from "
		"general/standard coverage of the other topics. Vary difficulty and question type. "
		"Return a JSON array, each item exactly: "
		'{"question_text": "...", "topic": "...", "marks": <number>, '
		'"difficulty": "Easy|Medium|Hard", "question_type": "MCQ|Short Answer|Long Answer|Numerical", '
		'"expected_answer_notes": "..."}'
	)
	questions = claude_client.call_claude_json(prompt, system=system, max_tokens=2000)

	draft = frappe.new_doc("AI Question Paper Draft")
	draft.title = f"{snapshot.course} - Draft Paper - {frappe.utils.nowdate()}"
	draft.course = snapshot.course
	draft.student_group = snapshot.student_group
	draft.academic_term = snapshot.academic_term
	draft.class_performance_snapshot = snapshot.name
	draft.total_marks = total_marks
	draft.remedial_ratio = remedial_ratio
	draft.status = "Draft"
	draft.generated_on = now_datetime()
	for q in questions:
		draft.append("questions", {
			"question_text": q.get("question_text"),
			"topic": q.get("topic"),
			"marks": q.get("marks"),
			"difficulty": q.get("difficulty"),
			"question_type": q.get("question_type"),
			"expected_answer_notes": q.get("expected_answer_notes"),
		})
	draft.insert(ignore_permissions=True)
	return draft.name


def _get_syllabus_context(course):
	if not frappe.db.exists("DocType", "Course Content"):
		return ""
	rows = frappe.get_all(
		"Course Content", filters={"course": course}, fields=["name"], limit_page_length=5
	)
	if not rows:
		return ""
	chunks = []
	for r in rows:
		try:
			content_doc = frappe.get_doc("Course Content", r.name)
			text = getattr(content_doc, "content", "") or getattr(content_doc, "description", "") or ""
			if text:
				chunks.append(text[:1000])
		except Exception:
			continue
	return "\n---\n".join(chunks)[:4000]

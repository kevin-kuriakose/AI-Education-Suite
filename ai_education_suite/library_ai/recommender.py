# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import now_datetime
from ai_education_suite.ai_core.utils import claude_client


@frappe.whitelist()
def generate_recommendations_for_student(student, num_books=5):
	if not claude_client.is_module_enabled("enable_library_ai"):
		frappe.throw(_("Library AI is disabled in AI Settings."))

	student_doc = frappe.get_doc("Student", student)
	program = getattr(student_doc, "program", None)

	courses = frappe.get_all(
		"Course Enrollment", filters={"student": student}, fields=["course"]
	)
	course_names = [c.course for c in courses]

	context_summary = f"Program: {program or 'N/A'}; Courses: {', '.join(course_names) or 'N/A'}"

	system = (
		"You are a school librarian assistant. You recommend real, well-known books appropriate for "
		"the student's program/courses and likely reading level. Prefer widely available titles."
	)
	prompt = (
		f"Student program: {program or 'Unknown'}\n"
		f"Enrolled courses: {', '.join(course_names) or 'Unknown'}\n\n"
		f"Suggest {num_books} books (fiction or non-fiction) relevant to this student's curriculum "
		"or that would broaden their understanding of their subjects. Return a JSON array, each item: "
		'{"book_title": "...", "author": "...", "relevance_score": 0.0-1.0, "reason": "1 sentence"}'
	)
	results = claude_client.call_claude_json(prompt, system=system, max_tokens=700)

	log = frappe.new_doc("Book Recommendation Log")
	log.student = student
	log.generated_on = now_datetime()
	log.status = "Suggested"
	log.context_summary = context_summary
	log.reasoning = f"Generated from {len(course_names)} enrolled course(s) under program '{program}'."
	for item in results:
		log.append("recommendations", {
			"book_title": item.get("book_title"),
			"author": item.get("author"),
			"relevance_score": item.get("relevance_score"),
			"reason": item.get("reason"),
		})
	log.insert(ignore_permissions=True)
	return log.name


def weekly_demand_forecast():
	"""
	Aggregates the last 7 days of recommendations to surface which titles/topics
	are trending across the school, so the librarian can pre-order copies.
	Writes a summary to the Frappe log (extend this to its own doctype if you
	want it queryable in the desk UI).
	"""
	if not claude_client.is_module_enabled("enable_library_ai"):
		return

	from frappe.utils import add_days
	recent = frappe.get_all(
		"Book Recommendation Log",
		filters={"generated_on": [">=", add_days(now_datetime(), -7)]},
		fields=["name"],
	)
	titles = {}
	for r in recent:
		items = frappe.get_all("Book Recommendation Item", filters={"parent": r.name}, fields=["book_title"])
		for i in items:
			titles[i.book_title] = titles.get(i.book_title, 0) + 1

	top = sorted(titles.items(), key=lambda x: x[1], reverse=True)[:10]
	frappe.logger("ai_education_suite").info(f"Library demand forecast (7d): {json.dumps(top)}")
	return top

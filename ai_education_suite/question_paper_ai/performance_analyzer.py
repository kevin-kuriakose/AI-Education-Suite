# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Builds a Class Performance Snapshot for a Student Group + Course + Term by
bucketing Assessment Result scores per Topic Tag (which links an Assessment
Criteria to a human-readable topic name). This is the data that
paper_generator.py uses to weight new question papers toward weak areas.
"""

import json
import frappe
from frappe import _
from frappe.utils import now_datetime
from ai_education_suite.ai_core.utils import claude_client


def on_assessment_result_submit(doc, method=None):
	"""Doc event hook: Assessment Result -> on_submit. Rebuilds snapshots async."""
	if not claude_client.is_module_enabled("enable_question_paper_ai"):
		return
	groups = frappe.get_all(
		"Student Group Student", filters={"student": doc.student}, fields=["parent"]
	)
	for g in groups:
		student_group = g.parent
		course = frappe.db.get_value("Student Group", student_group, "course") or getattr(doc, "course", None)
		if not course:
			continue
		frappe.enqueue(
			"ai_education_suite.question_paper_ai.performance_analyzer.build_snapshot",
			queue="short",
			student_group=student_group,
			course=course,
			academic_term=getattr(doc, "academic_term", None),
		)


@frappe.whitelist()
def build_snapshot(student_group, course, academic_term=None):
	settings = frappe.get_single("AI Settings")
	weak_threshold = settings.weak_topic_score_threshold or 50

	students = [s.student for s in frappe.get_all(
		"Student Group Student", filters={"parent": student_group}, fields=["student"]
	)]
	if not students:
		return None

	topic_tags = frappe.get_all(
		"Topic Tag", filters={"course": course}, fields=["topic_name", "assessment_criteria"]
	)

	weakness_rows = []
	all_scores = []

	if topic_tags:
		for tag in topic_tags:
			rows = frappe.get_all(
				"Assessment Result",
				filters={
					"student": ["in", students],
					"docstatus": 1,
					"assessment_criteria": tag.assessment_criteria,
				} if tag.assessment_criteria else {"student": ["in", students], "docstatus": 1},
				fields=["total_score", "maximum_score"],
			)
			if not rows:
				continue
			pct_scores = [
				(r.total_score / r.maximum_score) * 100
				for r in rows if r.maximum_score
			]
			if not pct_scores:
				continue
			avg = round(sum(pct_scores) / len(pct_scores), 1)
			weak_count = len([p for p in pct_scores if p < weak_threshold])
			level = "High" if avg < weak_threshold else ("Medium" if avg < weak_threshold + 20 else "Low")
			weakness_rows.append({
				"topic": tag.topic_name,
				"average_score": avg,
				"total_students": len(pct_scores),
				"weak_student_count": weak_count,
				"weakness_level": level,
			})
			all_scores.extend(pct_scores)
	else:
		# no topic tags configured yet — fall back to an overall-only snapshot
		rows = frappe.get_all(
			"Assessment Result",
			filters={"student": ["in", students], "docstatus": 1},
			fields=["total_score", "maximum_score"],
		)
		all_scores = [(r.total_score / r.maximum_score) * 100 for r in rows if r.maximum_score]

	overall_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

	existing = frappe.db.exists(
		"Class Performance Snapshot",
		{"student_group": student_group, "course": course, "academic_term": academic_term},
	)
	doc = frappe.get_doc("Class Performance Snapshot", existing) if existing else frappe.new_doc("Class Performance Snapshot")
	doc.student_group = student_group
	doc.course = course
	doc.academic_term = academic_term
	doc.overall_average = overall_avg
	doc.generated_on = now_datetime()
	doc.set("weakness_table", [])
	for row in weakness_rows:
		doc.append("weakness_table", row)

	weak_topics = [r["topic"] for r in weakness_rows if r["weakness_level"] == "High"]
	if weak_topics and claude_client.is_module_enabled("enable_question_paper_ai"):
		try:
			prompt = (
				f"Class overall average: {overall_avg}%.\n"
				f"Weak topics (class average below {weak_threshold}%): {', '.join(weak_topics)}.\n\n"
				"Write 2 sentences summarizing the class's performance for the teacher, naming the "
				"weakest areas and one suggestion for what to reinforce before the next assessment."
			)
			doc.ai_notes = claude_client.call_claude(prompt, max_tokens=200)
		except Exception:
			frappe.log_error(title="Performance Snapshot AI Notes Failed", message=frappe.get_traceback())

	doc.save(ignore_permissions=True)
	return doc.name

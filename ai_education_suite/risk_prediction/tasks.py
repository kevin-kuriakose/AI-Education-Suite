# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Daily scheduled job: computes a rule-based risk score for every active student
from attendance, assessment performance and fee history, then (optionally)
asks Claude for a one-paragraph plain-English summary for the reviewing staff
member. The scoring itself is deterministic and auditable on purpose — the
LLM is only used to explain it, never to produce the number.
"""

import json
import frappe
from frappe.utils import flt, now_datetime, add_days

from ai_education_suite.ai_core.utils import claude_client
from ai_education_suite.risk_prediction.doctype.student_risk_score.student_risk_score import classify_risk


def run_daily_risk_scoring():
	if not claude_client.is_module_enabled("enable_risk_prediction"):
		return

	students = frappe.get_all("Student", filters={"enabled": 1}, fields=["name", "student_name"])
	for student in students:
		try:
			compute_risk_for_student(student.name)
		except Exception:
			frappe.log_error(title="Risk Prediction Failed", message=frappe.get_traceback())


def compute_risk_for_student(student):
	attendance_pct = _get_attendance_percentage(student)
	avg_score = _get_average_assessment_score(student)
	fee_overdue_count = _get_fee_overdue_count(student)
	weak_topic_count = _get_weak_topic_count(student)

	# --- deterministic weighted score (0-100, higher = more at risk) ---
	attendance_risk = max(0, 100 - attendance_pct) if attendance_pct is not None else 30
	academic_risk = max(0, 100 - avg_score) if avg_score is not None else 30
	fee_risk = min(100, fee_overdue_count * 25)
	topic_risk = min(100, weak_topic_count * 20)

	risk_score = round(
		(attendance_risk * 0.35) + (academic_risk * 0.35) + (fee_risk * 0.15) + (topic_risk * 0.15), 1
	)
	risk_level = classify_risk(risk_score)

	factors = {
		"attendance_percentage": attendance_pct,
		"average_assessment_score": avg_score,
		"fee_overdue_count": fee_overdue_count,
		"weak_topic_count": weak_topic_count,
	}

	ai_summary = ""
	if risk_level in ("High", "Critical"):
		ai_summary = _generate_ai_summary(student, factors, risk_score, risk_level)

	existing = frappe.db.exists("Student Risk Score", {
		"student": student, "status": ["!=", "Actioned"],
		"generated_on": [">=", add_days(now_datetime(), -1)]
	})
	doc = frappe.get_doc("Student Risk Score", existing) if existing else frappe.new_doc("Student Risk Score")
	doc.student = student
	doc.risk_score = risk_score
	doc.risk_level = risk_level
	doc.attendance_percentage = attendance_pct
	doc.average_assessment_score = avg_score
	doc.fee_overdue_count = fee_overdue_count
	doc.weak_topic_count = weak_topic_count
	doc.contributing_factors = json.dumps(factors, indent=2)
	if ai_summary:
		doc.ai_summary = ai_summary
	doc.generated_on = now_datetime()
	if not existing:
		doc.status = "Open"
	doc.save(ignore_permissions=True)
	return doc.name


def _get_attendance_percentage(student):
	total = frappe.db.count("Student Attendance", {"student": student})
	if not total:
		return None
	present = frappe.db.count("Student Attendance", {"student": student, "status": "Present"})
	return round((present / total) * 100, 1)


def _get_average_assessment_score(student):
	rows = frappe.get_all(
		"Assessment Result",
		filters={"student": student, "docstatus": 1},
		fields=["total_score", "maximum_score"],
	)
	if not rows:
		return None
	total = sum(flt(r.total_score) for r in rows)
	maximum = sum(flt(r.maximum_score) for r in rows)
	if not maximum:
		return None
	return round((total / maximum) * 100, 1)


def _get_fee_overdue_count(student):
	if not frappe.db.exists("DocType", "Student Fee Payment"):
		return 0
	return frappe.db.count("Student Fee Payment", {"student": student, "status": "Overdue"})


def _get_weak_topic_count(student):
	groups = frappe.get_all("Student Group Student", filters={"student": student}, fields=["parent"])
	if not groups:
		return 0
	group_names = [g.parent for g in groups]
	snapshots = frappe.get_all(
		"Class Performance Snapshot", filters={"student_group": ["in", group_names]}, fields=["name"]
	)
	weak_count = 0
	for s in snapshots:
		details = frappe.get_all(
			"Topic Weakness Detail", filters={"parent": s.name, "weakness_level": "High"}
		)
		weak_count += len(details)
	return weak_count


def _generate_ai_summary(student, factors, risk_score, risk_level):
	try:
		student_name = frappe.db.get_value("Student", student, "student_name")
		prompt = (
			f"Student: {student_name}\n"
			f"Risk score: {risk_score}/100 ({risk_level})\n"
			f"Attendance: {factors.get('attendance_percentage')}%\n"
			f"Average assessment score: {factors.get('average_assessment_score')}%\n"
			f"Overdue fee payments: {factors.get('fee_overdue_count')}\n"
			f"Weak topics flagged: {factors.get('weak_topic_count')}\n\n"
			"Write a 2-3 sentence plain-English summary for a teacher/counsellor explaining "
			"why this student has been flagged, and one concrete, supportive next step. "
			"Do not diagnose any mental health condition. Be factual and neutral."
		)
		return claude_client.call_claude(prompt, max_tokens=250)
	except Exception:
		frappe.log_error(title="Risk Summary Generation Failed", message=frappe.get_traceback())
		return ""

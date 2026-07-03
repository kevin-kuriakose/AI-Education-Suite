# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Screens a Student Applicant and produces a score + strengths/concerns for a
human admissions officer to review. This NEVER writes a decision back to the
Student Applicant record itself, and final_decision always defaults to
Pending — the AI recommendation is advisory only.
"""

import frappe
from ai_education_suite.ai_core.utils import claude_client


def on_applicant_created(doc, method=None):
	if not claude_client.is_module_enabled("enable_admissions_ai"):
		return
	frappe.enqueue(
		"ai_education_suite.admissions_ai.screening.generate_screening",
		queue="short",
		student_applicant=doc.name,
	)


@frappe.whitelist()
def generate_screening(student_applicant):
	applicant = frappe.get_doc("Student Applicant", student_applicant)

	details = []
	for field in ("previous_school", "qualification", "program", "student_email_id", "student_mobile_number"):
		value = getattr(applicant, field, None)
		if value:
			details.append(f"{field}: {value}")

	system = (
		"You are assisting a school admissions officer. You provide a preliminary, advisory screening "
		"only. You do not make a final decision. You are fair, avoid bias related to name, gender, or "
		"background, and base your assessment only on the academic/program information given."
	)
	prompt = (
		"Applicant details:\n" + "\n".join(details) + "\n\n"
		"Provide a preliminary screening as JSON exactly: "
		'{"score": <0-100>, "recommendation": "Strongly Recommend|Recommend|Consider|Not Recommended", '
		'"strengths": "...", "concerns": "..."}'
	)
	result = claude_client.call_claude_json(prompt, system=system, max_tokens=400)

	screening = frappe.new_doc("Applicant Screening Result")
	screening.student_applicant = student_applicant
	screening.program = getattr(applicant, "program", None)
	screening.ai_score = result.get("score")
	screening.recommendation = result.get("recommendation")
	screening.strengths = result.get("strengths")
	screening.concerns = result.get("concerns")
	screening.generated_on = frappe.utils.now_datetime()
	screening.final_decision = "Pending"
	screening.insert(ignore_permissions=True)
	return screening.name

# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Grading Assist is invoked explicitly (e.g. from a button on the Assessment
Result form, or a bulk tool) rather than automatically, because core ERPNext
Education does not store free-text subjective answers by default — a teacher
or an integration supplies the answer text when requesting a suggestion.

Whitelisted entry point: create_grading_suggestion(...)
"""

import frappe
from frappe import _
from ai_education_suite.ai_core.utils import claude_client


@frappe.whitelist()
def create_grading_suggestion(assessment_result, question_reference, student_answer, max_score,
                               assessment_criteria=None, rubric=None):
	if not claude_client.is_module_enabled("enable_grading_assist"):
		frappe.throw(_("Grading Assist is disabled in AI Settings."))

	ar = frappe.get_doc("Assessment Result", assessment_result)

	system = (
		"You are an assistant grading student answers for a teacher. You suggest a score and a short "
		"rationale. You are careful, consistent, and always defer final judgement to the teacher. "
		"You never fabricate rubric criteria that were not given to you."
	)
	prompt = (
		f"Question / rubric reference:\n{question_reference}\n\n"
		+ (f"Rubric:\n{rubric}\n\n" if rubric else "")
		+ f"Maximum score: {max_score}\n\n"
		f"Student answer:\n{student_answer}\n\n"
		"Return a JSON object with exactly these keys: "
		'{"score": <number, 0 to max_score>, "rationale": "<2-4 sentence explanation>"}'
	)
	result = claude_client.call_claude_json(prompt, system=system, max_tokens=400)

	suggestion = frappe.new_doc("AI Grading Suggestion")
	suggestion.assessment_result = assessment_result
	suggestion.student = ar.student
	suggestion.course = getattr(ar, "course", None)
	suggestion.assessment_criteria = assessment_criteria
	suggestion.question_reference = question_reference
	suggestion.student_answer = student_answer
	suggestion.max_score = max_score
	suggestion.suggested_score = result.get("score")
	suggestion.ai_rationale = result.get("rationale")
	suggestion.status = "Pending Review"
	suggestion.insert(ignore_permissions=True)
	return suggestion.name


@frappe.whitelist()
def bulk_create_grading_suggestions(assessment_result, answers):
	"""
	answers: list of dicts: [{"question_reference": ..., "student_answer": ..., "max_score": ...,
	                           "assessment_criteria": ...(optional), "rubric": ...(optional)}, ...]
	Returns list of created AI Grading Suggestion names.
	"""
	import json as _json
	if isinstance(answers, str):
		answers = _json.loads(answers)
	created = []
	for a in answers:
		name = create_grading_suggestion(
			assessment_result=assessment_result,
			question_reference=a.get("question_reference"),
			student_answer=a.get("student_answer"),
			max_score=a.get("max_score"),
			assessment_criteria=a.get("assessment_criteria"),
			rubric=a.get("rubric"),
		)
		created.append(name)
	return created

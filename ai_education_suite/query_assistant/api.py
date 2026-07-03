# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Natural-language query assistant over a SAFELISTED set of Education doctypes.

Safety design:
  - Only doctypes in ALLOWED_DOCTYPES can ever be queried.
  - Only fields that actually exist on that doctype (per frappe.get_meta) are
    accepted, both for `fields` and inside `filters`.
  - Claude only ever produces a filter SPEC (doctype/fields/filters), never
    raw SQL or code. The spec is validated before frappe.get_list runs.
  - Every query + result count is logged to Query Assistant Log for audit.
"""

import json
import frappe
from frappe import _
from frappe.utils import now_datetime
from ai_education_suite.ai_core.utils import claude_client

ALLOWED_DOCTYPES = [
    "Student",
    "Student Attendance",
    "Assessment Result",
    "Course Enrollment",
    "Student Group",
    "Student Fee Payment",
]


@frappe.whitelist()
def ask(query_text):
	if not claude_client.is_module_enabled("enable_query_assistant"):
		frappe.throw(_("Query Assistant is disabled in AI Settings."))

	system = (
		"You translate a staff member's plain-English question into a structured query over a school "
		f"management system. You may ONLY use one of these doctypes: {', '.join(ALLOWED_DOCTYPES)}. "
		"You do not invent field names — use common, obvious field names (student, status, percentage, "
		"course, student_group, total_score, maximum_score, posting_date, etc)."
	)
	prompt = (
		f'Question: "{query_text}"\n\n'
		"Return JSON exactly: "
		'{"doctype": "<one of the allowed doctypes>", '
		'"fields": ["field1", "field2", ...], '
		'"filters": [["field", "operator", "value"], ...], '
		'"explanation": "1 sentence describing what you are fetching and why"}'
	)
	spec = claude_client.call_claude_json(prompt, system=system, max_tokens=500)

	doctype = spec.get("doctype")
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Query Assistant can only query: {0}").format(", ".join(ALLOWED_DOCTYPES)))

	meta = frappe.get_meta(doctype)
	valid_fieldnames = {"name"} | {df.fieldname for df in meta.fields}

	fields = [fld for fld in (spec.get("fields") or ["name"]) if fld in valid_fieldnames] or ["name"]

	filters = []
	for cond in spec.get("filters") or []:
		if not isinstance(cond, (list, tuple)) or len(cond) != 3:
			continue
		fieldname, operator, value = cond
		if fieldname not in valid_fieldnames:
			continue
		if operator not in ("=", "!=", ">", "<", ">=", "<=", "like", "in", "not in"):
			continue
		filters.append([fieldname, operator, value])

	results = frappe.get_list(doctype, fields=fields, filters=filters, limit_page_length=100)

	log = frappe.new_doc("Query Assistant Log")
	log.user = frappe.session.user
	log.query_text = query_text
	log.doctype_targeted = doctype
	log.filters_used = json.dumps(filters, indent=2)
	log.result_count = len(results)
	log.ai_explanation = spec.get("explanation")
	log.executed_on = now_datetime()
	log.insert(ignore_permissions=True)

	return {
		"explanation": spec.get("explanation"),
		"doctype": doctype,
		"count": len(results),
		"results": results,
	}

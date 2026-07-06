# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Natural-language query assistant over a SAFELISTED set of Education +
AI Education Suite doctypes.

Safety design:
  - Only doctypes in ALLOWED_DOCTYPES can ever be queried.
  - Only fields that actually exist on that doctype (per frappe.get_meta) are
    accepted, both for `fields` and inside `filters`.
  - The model only ever produces a filter SPEC (doctype/fields/filters),
    never raw SQL or code. The spec is validated before frappe.get_list runs.
  - Every query + result count is logged to Query Assistant Log for audit.

Accuracy design:
  - The system prompt includes the REAL field list (and Select field valid
    values) for every allowed doctype, built dynamically from frappe.get_meta
    each call. This stops the model from guessing plausible-sounding but
    wrong field names (e.g. a generic "status" field that doesn't exist on
    the target doctype), which previously caused filters to be silently
    dropped and every record to come back unfiltered.
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
	"Fees",
	"Student Applicant",
	"Student Risk Score",
	"AI Grading Suggestion",
	"AI Question Paper Draft",
	"Book Recommendation Log",
	"House Allocation Suggestion",
	"Team Balance Suggestion",
	"Applicant Screening Result",
]


def _get_valid_allowed_doctypes():
	"""Filters ALLOWED_DOCTYPES down to ones that actually exist as installed
	DocTypes right now. Protects against a typo'd/renamed/uninstalled
	doctype in the static list causing a hard crash instead of just being
	quietly excluded from what the assistant can query."""
	return [dt for dt in ALLOWED_DOCTYPES if frappe.db.exists("DocType", dt)]


def _build_schema_context(valid_doctypes):
	"""Compact per-doctype field summary (name + type, with Select fields'
	valid values shown in parentheses) so the model picks real field names
	and real Select values instead of guessing generic ones."""
	lines = []
	for doctype in valid_doctypes:
		try:
			meta = frappe.get_meta(doctype)
		except Exception:
			continue
		field_bits = []
		for df in meta.fields:
			if df.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table"):
				continue
			bit = df.fieldname
			if df.fieldtype == "Select" and df.options:
				bit += f" (one of: {df.options.replace(chr(10), '/')})"
			field_bits.append(bit)
		lines.append(f"- {doctype}: {', '.join(field_bits)}")
	return "\n".join(lines)


@frappe.whitelist()
def ask(query_text, context=None):
	if not claude_client.is_module_enabled("enable_query_assistant"):
		frappe.throw(_("Query Assistant is disabled in AI Settings."))

	valid_doctypes = _get_valid_allowed_doctypes()
	schema_context = _build_schema_context(valid_doctypes)

	context_block = ""
	if context:
		try:
			context_data = json.loads(context) if isinstance(context, str) else context
			prev_doctype = context_data.get("doctype")
			prev_results = context_data.get("results") or []
			if prev_doctype and prev_results:
				items = "; ".join(
					f"{r.get('label')} (name={r.get('name')})" for r in prev_results[:10]
				)
				context_block = (
					f"\n\nCONTEXT: the previous question in this conversation queried '{prev_doctype}' "
					f"and found: {items}. If THIS question refers back to one of these (e.g. 'this "
					"applicant', 'that student', 'his/her record'), add a filter on that doctype's "
					"'name' field equal to the matching record's name shown above -- do not guess a "
					"placeholder value."
				)
		except Exception:
			pass

	system = (
		"You translate a staff member's plain-English question into a structured query over a "
		"school management system. You may ONLY use one of the doctypes below, and ONLY the field "
		"names listed for each one (Select fields show their valid values in parentheses) \u2014 never "
		"invent a field name that isn't listed there.\n\n"
		f"{schema_context}\n\n"
		"Pick the single doctype that best matches the question's actual subject. In particular: "
		"'Student' is already-ENROLLED students; a question about 'applicants', 'admissions', or "
		"'screening' means 'Student Applicant' or 'Applicant Screening Result' instead, NOT 'Student'."
		f"{context_block}"
	)
	prompt = (
		f'Question: "{query_text}"\n\n'
		"Return JSON exactly: "
		'{"doctype": "<one of the allowed doctypes>", '
		'"fields": ["field1", "field2", ...], '
		'"filters": [["field", "operator", "value"], ...], '
		'"explanation": "1 sentence describing what you are fetching and why"}'
	)
	spec = claude_client.call_claude_json(prompt, system=system, max_tokens=600)

	doctype = spec.get("doctype")
	if doctype not in valid_doctypes:
		frappe.throw(_("Query Assistant can only query: {0}").format(", ".join(valid_doctypes)))

	meta = frappe.get_meta(doctype)
	valid_fieldnames = {"name"} | {df.fieldname for df in meta.fields}

	fields = [fld for fld in (spec.get("fields") or []) if fld in valid_fieldnames]
	# Always include a usable label field and the docname itself, regardless
	# of what the model asked for -- otherwise a query that only requests a
	# filter field (e.g. just "application_status") comes back with nothing
	# the UI can display or link to.
	if meta.title_field and meta.title_field in valid_fieldnames and meta.title_field not in fields:
		fields.append(meta.title_field)
	if "name" not in fields:
		fields.append("name")

	filters = []
	dropped_any = False
	for cond in spec.get("filters") or []:
		if not isinstance(cond, (list, tuple)) or len(cond) != 3:
			continue
		fieldname, operator, value = cond
		if fieldname not in valid_fieldnames or operator not in (
			"=", "!=", ">", "<", ">=", "<=", "like", "in", "not in",
		):
			dropped_any = True
			continue
		filters.append([fieldname, operator, value])

	results = frappe.get_list(doctype, fields=fields, filters=filters, limit_page_length=100)

	explanation = spec.get("explanation") or ""
	if dropped_any and not filters:
		explanation += " (Couldn't map this question to a specific filter, so this shows all records of this type \u2014 try rephrasing with more specific wording.)"

	log = frappe.new_doc("Query Assistant Log")
	log.user = frappe.session.user
	log.query_text = query_text
	log.doctype_targeted = doctype
	log.filters_used = json.dumps(filters, indent=2)
	log.result_count = len(results)
	log.ai_explanation = explanation
	log.executed_on = now_datetime()
	log.insert(ignore_permissions=True)

	return {
		"explanation": explanation,
		"doctype": doctype,
		"count": len(results),
		"results": results,
	}

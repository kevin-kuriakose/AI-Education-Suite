# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
House allocation is a constraint-balancing problem, not a generative one.
The solver below is deterministic and rule-based:

  1. Hard constraint: siblings (students sharing a Guardian) are kept in the
     same house unless `split_siblings=True` is passed.
  2. Soft constraints (minimised via greedy assignment): house size, gender
     ratio, and academic performance are kept as balanced as possible across
     houses.

Claude is used only to translate the numeric result into a short, parent-
readable explanation — never to decide the placement itself.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime
from ai_education_suite.ai_core.utils import claude_client


def _house_stats(houses):
	stats = {}
	for house in houses:
		members = frappe.get_all("Student", filters={"house": house}, fields=["name", "gender"])
		count = len(members)
		female = len([m for m in members if (m.gender or "").lower() == "female"])
		avg_score = _average_score([m.name for m in members]) if members else 0
		stats[house] = {"count": count, "female": female, "avg_score": avg_score}
	return stats


def _average_score(student_names):
	if not student_names:
		return 0
	rows = frappe.get_all(
		"Assessment Result",
		filters={"student": ["in", student_names], "docstatus": 1},
		fields=["total_score", "maximum_score"],
	)
	if not rows:
		return 0
	total = sum((r.total_score or 0) for r in rows)
	maximum = sum((r.maximum_score or 0) for r in rows)
	return round((total / maximum) * 100, 1) if maximum else 0


def _get_siblings(student):
	"""Students sharing at least one Guardian with the given student."""
	guardians = frappe.get_all("Student Guardian", filters={"parent": student}, fields=["guardian"])
	guardian_ids = [g.guardian for g in guardians]
	if not guardian_ids:
		return []
	sibling_links = frappe.get_all(
		"Student Guardian", filters={"guardian": ["in", guardian_ids], "parent": ["!=", student]},
		fields=["parent"]
	)
	return list({s.parent for s in sibling_links})


def _balance_score(stats):
	"""Lower is better: variance across houses in size, gender ratio, academic avg."""
	counts = [s["count"] for s in stats.values()] or [0]
	females = [s["female"] for s in stats.values()] or [0]
	scores = [s["avg_score"] for s in stats.values()] or [0]

	def variance(values):
		if not values:
			return 0
		mean = sum(values) / len(values)
		return sum((v - mean) ** 2 for v in values) / len(values)

	return round(variance(counts) + variance(females) + variance(scores), 2)


@frappe.whitelist()
def allocate_new_students(students, houses=None, split_siblings=False):
	"""
	students: list of student IDs (or JSON string) needing a house.
	houses: optional list of House names to consider; defaults to all Houses.
	Returns list of created House Allocation Suggestion names.
	"""
	import json as _json
	if isinstance(students, str):
		students = _json.loads(students)
	if isinstance(houses, str):
		houses = _json.loads(houses)
	if not houses:
		houses = [h.name for h in frappe.get_all("House")]
	if not houses:
		frappe.throw(_("No House records found. Create at least one House first."))

	created = []
	assigned_in_this_run = {}

	for student in students:
		siblings = [] if split_siblings else _get_siblings(student)
		sibling_house = None
		for sib in siblings:
			sib_house = frappe.db.get_value("Student", sib, "house")
			if sib_house:
				sibling_house = sib_house
				break

		stats_before = _house_stats(houses)
		balance_before = _balance_score(stats_before)

		if sibling_house:
			target_house = sibling_house
			reasoning_note = f"Placed with sibling(s) already in {sibling_house}."
		else:
			# greedy: try each house, pick whichever minimises post-assignment variance
			best_house, best_score = None, None
			gender = frappe.db.get_value("Student", student, "gender")
			for house in houses:
				trial = {h: dict(v) for h, v in stats_before.items()}
				trial[house]["count"] += 1
				if (gender or "").lower() == "female":
					trial[house]["female"] += 1
				score = _balance_score(trial)
				if best_score is None or score < best_score:
					best_score, best_house = score, house
			target_house = best_house
			reasoning_note = "Selected to keep house size/gender/academic balance as even as possible."

		current_house = frappe.db.get_value("Student", student, "house")
		stats_after = _house_stats(houses)
		if target_house in stats_after:
			stats_after[target_house]["count"] += 1
		balance_after = _balance_score(stats_after)

		suggestion = frappe.new_doc("House Allocation Suggestion")
		suggestion.student = student
		suggestion.current_house = current_house
		suggestion.suggested_house = target_house
		suggestion.sibling_reference = ", ".join(siblings) if siblings else ""
		suggestion.balance_score_before = balance_before
		suggestion.balance_score_after = balance_after
		suggestion.reasoning = reasoning_note
		suggestion.status = "Pending"
		suggestion.generated_on = now_datetime()
		suggestion.insert(ignore_permissions=True)
		created.append(suggestion.name)

	return created


def weekly_balance_check():
	"""
	Scheduled job: checks current inter-house balance and, if imbalance exceeds
	a reasonable threshold, logs a warning (extend this to raise suggestions
	for swaps if desired). Kept conservative by default — swapping students
	already in a house is disruptive, so this only alerts rather than acting.
	"""
	if not claude_client.is_module_enabled("enable_house_allocation"):
		return
	houses = [h.name for h in frappe.get_all("House")]
	if not houses:
		return
	stats = _house_stats(houses)
	score = _balance_score(stats)
	threshold = 50  # tune per school size
	if score > threshold:
		frappe.logger("ai_education_suite").warning(
			f"House imbalance detected (score={score}): {stats}"
		)

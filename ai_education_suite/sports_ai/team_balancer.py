# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Team balancing is rule-based (snake draft by skill score) so results are
reproducible and fair by construction. Claude is used only to write a short
plain-English explanation of the split for coaches/parents.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime
from ai_education_suite.ai_core.utils import claude_client


@frappe.whitelist()
def suggest_balanced_teams(title, sport, students, num_teams=2, student_group=None):
	"""
	students: list of dicts [{"student": "STU-0001", "skill_score": 7.5}, ...]
	          or a JSON string of the same.
	"""
	import json as _json
	if isinstance(students, str):
		students = _json.loads(students)

	num_teams = int(num_teams)
	ranked = sorted(students, key=lambda s: float(s.get("skill_score") or 0), reverse=True)

	teams = [[] for _ in range(num_teams)]
	direction = 1
	idx = 0
	for student in ranked:
		teams[idx].append(student)
		idx += direction
		if idx == num_teams:
			idx = num_teams - 1
			direction = -1
		elif idx < 0:
			idx = 0
			direction = 1

	doc = frappe.new_doc("Team Balance Suggestion")
	doc.title = title
	doc.sport = sport
	doc.student_group = student_group
	doc.num_teams = num_teams
	doc.generated_on = now_datetime()

	team_summaries = []
	for i, team in enumerate(teams, start=1):
		scores = [float(s.get("skill_score") or 0) for s in team]
		avg = round(sum(scores) / len(scores), 2) if scores else 0
		row = doc.append("teams", {"team_name": f"Team {i}", "average_skill_score": avg})
		for s in team:
			row.append("students", {
				"student": s.get("student"),
				"skill_score": s.get("skill_score"),
			})
		team_summaries.append(f"Team {i}: avg skill {avg}, {len(team)} players")

	if claude_client.is_module_enabled("enable_sports_ai"):
		try:
			prompt = (
				f"Sport: {sport}\nTeams generated via snake-draft skill balancing:\n"
				+ "\n".join(team_summaries)
				+ "\n\nWrite 2-3 sentences summarizing how balanced this split is and any note "
				"a coach should know (e.g. if one team is slightly stronger)."
			)
			doc.balance_notes = claude_client.call_claude(prompt, max_tokens=200)
		except Exception:
			frappe.log_error(title="Sports AI Notes Failed", message=frappe.get_traceback())

	doc.insert(ignore_permissions=True)
	return doc.name

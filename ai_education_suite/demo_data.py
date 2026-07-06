# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Creates a small, consistent demo dataset covering every AI Education Suite
doctype, plus the underlying Education-module Assessment chain (Grading
Scale, Assessment Group, Assessment Criteria, Assessment Plan, Assessment
Result) so the whole system has real, linked data to look at rather than
isolated AI-only records.

Run:
    bench --site yoursite.local execute ai_education_suite.demo_data.generate_demo_data

Safe to re-run: uses get_or_create() and checks frappe.db.exists() throughout.
"""

import json
import frappe
from frappe.utils import now_datetime, add_days, nowdate


def get_or_create(doctype, filters, values=None):
	name = frappe.db.exists(doctype, filters)
	if name:
		return frappe.get_doc(doctype, name)
	doc = frappe.new_doc(doctype)
	doc.update(filters)
	if values:
		doc.update(values)
	try:
		doc.insert(ignore_permissions=True, ignore_mandatory=True)
	except frappe.DuplicateEntryError:
		# A record with this autoname already exists but didn't match every
		# field in `filters` (e.g. a previous partial run left a slightly
		# different value in a non-naming field) — fetch it instead of crashing.
		frappe.db.rollback()
		return frappe.get_doc(doctype, doc.name)
	return doc


def generate_demo_data():
	frappe.flags.in_demo_data = True

	print("Creating AI Settings...")
	settings = frappe.get_single("AI Settings")
	settings.enable_ai_features = 1
	settings.model = "llama-3.3-70b-versatile"
	settings.max_tokens = 1024
	settings.temperature = 0.3
	for toggle in [
		"enable_risk_prediction", "enable_grading_assist", "enable_question_paper_ai",
		"enable_library_ai", "enable_sports_ai", "enable_house_allocation",
		"enable_admissions_ai", "enable_query_assistant",
	]:
		settings.set(toggle, 1)
	settings.risk_high_threshold = 70
	settings.risk_medium_threshold = 40
	settings.grading_autoflag_delta = 15
	settings.weak_topic_score_threshold = 50
	settings.save(ignore_permissions=True)

	print("Creating base academic structure...")
	academic_year = get_or_create("Academic Year", {"academic_year_name": "2024-25"})
	program = get_or_create("Program", {"program_name": "Grade 9 - Science", "program_code": "G9SCI"})
	course = get_or_create("Course", {"course_name": "Physics", "course_code": "PHY9"})

	student_group = get_or_create(
		"Student Group",
		{"student_group_name": "Grade 9 - Section A"},
		{"group_based_on": "Batch", "program": program.name if hasattr(program, "name") else None},
	)

	print("Creating demo students...")
	students = []
	demo_students = [
		("Aarav Sharma", "Male"), ("Diya Patel", "Female"), ("Kabir Singh", "Male"),
		("Ishita Rao", "Female"), ("Vivaan Mehta", "Male"),
	]
	for full_name, gender in demo_students:
		first_name, last_name = full_name.split(" ", 1)
		email = full_name.lower().replace(" ", ".") + "@demo.ai-education.local"
		s = get_or_create(
			"Student",
			{"student_name": full_name},
			{
				"first_name": first_name, "last_name": last_name,
				"gender": gender, "enabled": 1,
				"student_email_id": email, "student_mobile_number": "9999999999",
			},
		)
		students.append(s)
		if not frappe.db.exists("Student Group Student", {"parent": student_group.name, "student": s.name}):
			try:
				student_group.append("students", {"student": s.name, "student_name": s.student_name})
			except Exception:
				pass
	try:
		student_group.save(ignore_permissions=True)
	except Exception:
		pass

	print("Creating Houses...")
	house_defs = [("Red House", "#e53935"), ("Blue House", "#1e88e5"),
	              ("Green House", "#43a047"), ("Yellow House", "#fdd835")]
	houses = []
	for name, color in house_defs:
		h = get_or_create("House", {"house_name": name}, {"color_code": color, "capacity": 100})
		houses.append(h)

	print("Creating Topic Tags for Physics...")
	topics = ["Mechanics", "Thermodynamics", "Optics", "Electricity"]
	for t in topics:
		get_or_create("Topic Tag", {"course": course.name, "topic_name": t})

	# ------------------------------------------------------------------
	# Assessment chain: Grading Scale -> Assessment Group -> Assessment
	# Criteria -> Assessment Plan -> Assessment Result. This is real
	# Education-module data (not an AI Education Suite doctype), but the
	# AI Grading Suggestion demo record links to a real Assessment Result
	# below, so it needs to exist first.
	# ------------------------------------------------------------------

	print("Creating a Grading Scale...")
	grading_scale_name = "Standard Percentage Scale"
	if frappe.db.exists("Grading Scale", grading_scale_name):
		grading_scale = frappe.get_doc("Grading Scale", grading_scale_name)
	else:
		grading_scale = frappe.new_doc("Grading Scale")
		grading_scale.grading_scale_name = grading_scale_name
		for grade_code, threshold, desc in [
			("A", 90, "Outstanding"), ("B", 75, "Very Good"),
			("C", 60, "Good"), ("D", 40, "Needs Improvement"), ("F", 0, "Fail"),
		]:
			grading_scale.append("intervals", {
				"grade_code": grade_code, "threshold": threshold, "grade_description": desc,
			})
		grading_scale.insert(ignore_permissions=True)
		try:
			grading_scale.submit()
		except Exception:
			pass

	print("Setting up Assessment Group hierarchy...")
	assessment_group_root = frappe.db.get_value(
		"Assessment Group", {"parent_assessment_group": ["in", ["", None]]}, "name"
	)
	if not assessment_group_root:
		any_group = frappe.db.get_value("Assessment Group", {}, "name")
		if any_group:
			assessment_group_root = any_group
		else:
			root_doc = frappe.new_doc("Assessment Group")
			root_doc.assessment_group_name = "All Assessment Groups"
			root_doc.is_group = 1
			root_doc.parent_assessment_group = ""
			root_doc.insert(ignore_permissions=True, ignore_mandatory=True)
			assessment_group_root = root_doc.name

	assessment_group = get_or_create(
		"Assessment Group",
		{"assessment_group_name": "Term 1 Exams", "parent_assessment_group": assessment_group_root},
		{"is_group": 0},
	)

	print("Creating Assessment Criteria...")
	criteria_docs = {}
	for crit_name in ["Theory", "Practical"]:
		criteria_docs[crit_name] = get_or_create("Assessment Criteria", {"assessment_criteria": crit_name})

	print("Creating an Assessment Plan for Physics...")
	assessment_plan_filter = {
		"student_group": student_group.name, "course": course.name, "assessment_group": assessment_group.name,
	}
	existing_plan_name = frappe.db.get_value("Assessment Plan", assessment_plan_filter, "name")
	if existing_plan_name:
		assessment_plan = frappe.get_doc("Assessment Plan", existing_plan_name)
	else:
		assessment_plan = frappe.new_doc("Assessment Plan")
		assessment_plan.student_group = student_group.name
		assessment_plan.assessment_name = "Physics - Term 1 Assessment"
		assessment_plan.assessment_group = assessment_group.name
		assessment_plan.grading_scale = grading_scale.name
		assessment_plan.program = program.name if hasattr(program, "name") else None
		assessment_plan.course = course.name
		assessment_plan.academic_year = academic_year.name if hasattr(academic_year, "name") else None
		assessment_plan.schedule_date = nowdate()
		assessment_plan.from_time = "09:00:00"
		assessment_plan.to_time = "11:00:00"
		assessment_plan.maximum_assessment_score = 50
		assessment_plan.append("assessment_criteria", {
			"assessment_criteria": criteria_docs["Theory"].name, "maximum_score": 40,
		})
		assessment_plan.append("assessment_criteria", {
			"assessment_criteria": criteria_docs["Practical"].name, "maximum_score": 10,
		})
		assessment_plan.insert(ignore_permissions=True)
		try:
			assessment_plan.submit()
		except Exception:
			pass

	print("Creating sample Assessment Results...")
	assessment_results = {}
	# (student, theory_score /40, practical_score /10, grade)
	demo_scores = [
		(students[0], 20, 5, "D"),   # matches the at-risk student — low score
		(students[1], 30, 8, "B"),   # matches the AI Grading Suggestion student
		(students[2], 36, 9, "A"),
		(students[3], 25, 7, "C"),
	]
	for s, theory_score, practical_score, grade in demo_scores:
		existing_result_name = frappe.db.get_value(
			"Assessment Result", {"assessment_plan": assessment_plan.name, "student": s.name}, "name"
		)
		if existing_result_name:
			assessment_results[s.name] = frappe.get_doc("Assessment Result", existing_result_name)
			continue
		ar = frappe.new_doc("Assessment Result")
		ar.assessment_plan = assessment_plan.name
		ar.student = s.name
		ar.student_group = student_group.name
		ar.program = program.name if hasattr(program, "name") else None
		ar.course = course.name
		ar.academic_year = academic_year.name if hasattr(academic_year, "name") else None
		ar.assessment_group = assessment_group.name
		ar.grading_scale = grading_scale.name
		ar.maximum_score = 50
		ar.total_score = theory_score + practical_score
		ar.grade = grade
		ar.append("details", {
			"assessment_criteria": criteria_docs["Theory"].name, "maximum_score": 40, "score": theory_score,
		})
		ar.append("details", {
			"assessment_criteria": criteria_docs["Practical"].name, "maximum_score": 10, "score": practical_score,
		})
		ar.insert(ignore_permissions=True)
		try:
			ar.submit()
		except Exception:
			pass
		assessment_results[s.name] = ar

	print("Creating a Class Performance Snapshot (pre-generated, no API call)...")
	if not frappe.db.exists("Class Performance Snapshot",
	                         {"student_group": student_group.name, "course": course.name}):
		snapshot = frappe.new_doc("Class Performance Snapshot")
		snapshot.student_group = student_group.name
		snapshot.course = course.name
		snapshot.overall_average = 61.5
		snapshot.generated_on = now_datetime()
		snapshot.ai_notes = (
			"The class is performing well in Mechanics and Electricity, but Thermodynamics "
			"is significantly weaker (38% average). Recommend a revision session on heat "
			"transfer and the laws of thermodynamics before the next assessment."
		)
		for topic, avg, weak, total, level in [
			("Mechanics", 78, 1, 5, "Low"),
			("Thermodynamics", 38, 4, 5, "High"),
			("Optics", 65, 2, 5, "Medium"),
			("Electricity", 71, 1, 5, "Low"),
		]:
			snapshot.append("weakness_table", {
				"topic": topic, "average_score": avg, "weak_student_count": weak,
				"total_students": total, "weakness_level": level,
			})
		snapshot.insert(ignore_permissions=True)
	else:
		snapshot = frappe.get_doc("Class Performance Snapshot",
		                           {"student_group": student_group.name, "course": course.name})

	print("Creating a sample AI Question Paper Draft (pre-generated)...")
	if not frappe.db.exists("AI Question Paper Draft", {"class_performance_snapshot": snapshot.name}):
		draft = frappe.new_doc("AI Question Paper Draft")
		draft.title = f"Physics - Draft Paper - {nowdate()}"
		draft.course = course.name
		draft.student_group = student_group.name
		draft.class_performance_snapshot = snapshot.name
		draft.total_marks = 50
		draft.remedial_ratio = 60
		draft.status = "Draft"
		draft.generated_on = now_datetime()
		demo_questions = [
			("Explain the zeroth law of thermodynamics with an example.", "Thermodynamics", 8, "Medium", "Long Answer"),
			("A gas expands isothermally. Calculate the work done given P and V values.", "Thermodynamics", 10, "Hard", "Numerical"),
			("Define specific heat capacity and state its SI unit.", "Thermodynamics", 4, "Easy", "Short Answer"),
			("State Newton's second law of motion.", "Mechanics", 4, "Easy", "Short Answer"),
			("A block slides down a frictionless incline. Find its acceleration.", "Mechanics", 8, "Medium", "Numerical"),
			("Describe total internal reflection with a real-world example.", "Optics", 6, "Medium", "Short Answer"),
			("Which of these is a vector quantity?", "Mechanics", 2, "Easy", "MCQ"),
			("Explain Ohm's Law and derive V=IR.", "Electricity", 6, "Medium", "Long Answer"),
			("Calculate equivalent resistance for two resistors in parallel.", "Electricity", 6, "Medium", "Numerical"),
		]
		for text, topic, marks, diff, qtype in demo_questions:
			draft.append("questions", {
				"question_text": text, "topic": topic, "marks": marks,
				"difficulty": diff, "question_type": qtype,
			})
		draft.insert(ignore_permissions=True)

	print("Creating sample Student Risk Scores...")
	if students:
		at_risk_student = students[0]
		if not frappe.db.exists("Student Risk Score", {"student": at_risk_student.name}):
			risk = frappe.new_doc("Student Risk Score")
			risk.student = at_risk_student.name
			risk.risk_score = 74.5
			risk.risk_level = "High"
			risk.attendance_percentage = 62
			risk.average_assessment_score = 48
			risk.fee_overdue_count = 1
			risk.weak_topic_count = 2
			risk.contributing_factors = json.dumps({
				"attendance_percentage": 62, "average_assessment_score": 48,
				"fee_overdue_count": 1, "weak_topic_count": 2,
			}, indent=2)
			risk.ai_summary = (
				f"{at_risk_student.student_name} has been flagged due to declining attendance (62%) "
				"and below-average scores in Thermodynamics and Optics, alongside one overdue fee "
				"payment. Recommend a check-in conversation and a revision plan for the weak topics."
			)
			risk.status = "Open"
			risk.generated_on = now_datetime()
			risk.insert(ignore_permissions=True)

	print("Creating a sample AI Grading Suggestion...")
	if students and not frappe.db.exists("AI Grading Suggestion", {"student": students[1].name}):
		grading = frappe.new_doc("AI Grading Suggestion")
		grading.student = students[1].name
		grading.course = course.name
		linked_result = assessment_results.get(students[1].name)
		if linked_result:
			grading.assessment_result = linked_result.name
		grading.question_reference = "Explain the zeroth law of thermodynamics with an example."
		grading.student_answer = (
			"If object A is in thermal equilibrium with object B, and B is in thermal "
			"equilibrium with C, then A and C are also in equilibrium. Example: a thermometer."
		)
		grading.max_score = 8
		grading.suggested_score = 6.5
		grading.ai_rationale = (
			"The core definition is correct and the thermometer example is valid, but the answer "
			"does not explain *why* this allows temperature to be measured, which the rubric asks for."
		)
		grading.status = "Pending Review"
		# ignore_mandatory left on as a safety net in case assessment_result
		# couldn't be resolved above for any reason (e.g. partial re-run state).
		grading.insert(ignore_permissions=True, ignore_mandatory=True)

	print("Creating a sample Book Recommendation Log...")
	if students and not frappe.db.exists("Book Recommendation Log", {"student": students[2].name}):
		log = frappe.new_doc("Book Recommendation Log")
		log.student = students[2].name
		log.generated_on = now_datetime()
		log.status = "Suggested"
		log.context_summary = f"Program: {program.program_name}; Courses: Physics"
		log.reasoning = "Generated from enrollment in Physics under Grade 9 - Science."
		for title, author, score, reason in [
			("Six Easy Pieces", "Richard Feynman", 0.95, "Accessible introduction to core physics concepts."),
			("The Elegant Universe", "Brian Greene", 0.8, "Broadens understanding of physics beyond the syllabus."),
			("Thinking Physics", "Lewis Epstein", 0.85, "Builds conceptual intuition through puzzles."),
		]:
			log.append("recommendations", {
				"book_title": title, "author": author, "relevance_score": score, "reason": reason,
			})
		log.insert(ignore_permissions=True)

	print("Creating a sample Team Balance Suggestion...")
	if len(students) >= 4 and not frappe.db.exists("Team Balance Suggestion", {"title": "Inter-House Football Demo"}):
		team_doc = frappe.new_doc("Team Balance Suggestion")
		team_doc.title = "Inter-House Football Demo"
		team_doc.sport = "Football"
		team_doc.num_teams = 2
		team_doc.generated_on = now_datetime()
		row1 = team_doc.append("teams", {"team_name": "Team 1", "average_skill_score": 7.75})
		row1.append("students", {"student": students[3].name, "skill_score": 9.0})
		row1.append("students", {"student": students[0].name, "skill_score": 8.5})
		row2 = team_doc.append("teams", {"team_name": "Team 2", "average_skill_score": 6.5})
		row2.append("students", {"student": students[1].name, "skill_score": 7.0})
		row2.append("students", {"student": students[2].name, "skill_score": 6.5})
		team_doc.balance_notes = (
			"Teams are closely matched (average skill 7.75 vs 6.5). Team 1 has a slight edge; "
			"consider rotating a stronger substitute into Team 2 if available."
		)
		team_doc.insert(ignore_permissions=True)

	print("Creating sample House Allocation Suggestions...")
	if students and houses:
		for i, s in enumerate(students[:2]):
			if not frappe.db.exists("House Allocation Suggestion", {"student": s.name}):
				suggestion = frappe.new_doc("House Allocation Suggestion")
				suggestion.student = s.name
				suggestion.suggested_house = houses[i % len(houses)].name
				suggestion.balance_score_before = 42.0
				suggestion.balance_score_after = 30.5
				suggestion.reasoning = "Selected to keep house size and gender balance as even as possible."
				suggestion.status = "Pending"
				suggestion.generated_on = now_datetime()
				suggestion.insert(ignore_permissions=True)

	print("Creating a sample Applicant Screening Result...")
	applicant = get_or_create(
		"Student Applicant",
		{"first_name": "Rhea", "last_name": "Kapoor"},
		{"program": program.name if hasattr(program, "name") else None},
	)
	if not frappe.db.exists("Applicant Screening Result", {"student_applicant": applicant.name}):
		screening = frappe.new_doc("Applicant Screening Result")
		screening.student_applicant = applicant.name
		screening.applicant_name = "Rhea Kapoor"
		screening.program = program.name if hasattr(program, "name") else None
		screening.ai_score = 82.0
		screening.recommendation = "Recommend"
		screening.strengths = (
			"Strong academic transcript (91% average in prior grade), consistent extracurricular "
			"involvement in science olympiads, and a well-articulated statement of purpose."
		)
		screening.concerns = (
			"No prior formal exposure to the specific Grade 9 Science curriculum structure; "
			"may need a brief onboarding assessment to confirm placement level."
		)
		screening.generated_on = now_datetime()
		screening.final_decision = "Pending"
		screening.insert(ignore_permissions=True, ignore_mandatory=True)

	print("Creating a sample Query Assistant Log...")
	if not frappe.db.exists("Query Assistant Log", {"query_text": "How many students scored below 60% in Physics?"}):
		qlog = frappe.new_doc("Query Assistant Log")
		qlog.user = frappe.session.user
		qlog.query_text = "How many students scored below 60% in Physics?"
		qlog.doctype_targeted = "Assessment Result"
		qlog.filters_used = json.dumps({
			"course": course.name, "score_percent": ["<", 60],
		}, indent=2)
		qlog.result_count = 2
		qlog.ai_explanation = (
			"Found 2 Assessment Result records for Physics where the scored percentage is below 60%, "
			"filtered to the current academic year."
		)
		qlog.executed_on = now_datetime()
		qlog.insert(ignore_permissions=True, ignore_mandatory=True)

	frappe.db.commit()
	print("\nDemo data created successfully.")
	print("Visit: AI Settings, Student Risk Score, Class Performance Snapshot,")
	print("AI Question Paper Draft, AI Grading Suggestion, Book Recommendation Log,")
	print("Team Balance Suggestion, House, House Allocation Suggestion,")
	print("Applicant Screening Result, Query Assistant Log.")
	print("Also: Grading Scale, Assessment Group, Assessment Criteria,")
	print("Assessment Plan, Assessment Result.")


def introspect_assessment_doctypes():
	"""Temporary helper: dumps schema for the Assessment doctype chain so demo
	data can be written against the real field names/mandatory flags instead
	of guessing. Safe to leave in the app; does not modify any data."""
	doctypes = [
		"Grading Scale", "Grading Scale Interval",
		"Assessment Group", "Assessment Criteria",
		"Assessment Plan", "Assessment Plan Criteria",
		"Assessment Result", "Assessment Result Detail",
	]
	for dt in doctypes:
		try:
			meta = frappe.get_meta(dt)
		except Exception as e:
			print(f"=== {dt} === COULD NOT LOAD: {e}")
			continue
		print(f"=== {dt} === (istable={meta.istable}, is_submittable={meta.is_submittable})")
		for f in meta.fields:
			if f.fieldtype in ("Section Break", "Column Break", "Tab Break"):
				continue
			flags = []
			if f.reqd:
				flags.append("REQD")
			if f.fieldtype == "Table":
				flags.append(f"TABLE->{f.options}")
			print(f"  {f.fieldname:30s} {f.fieldtype:15s} {(f.options or '')[:25]:25s} {' '.join(flags)}")
		print()


def create_ai_education_workspace():
	"""Creates (or replaces) a minimal, professional 'AI Education Suite'
	workspace: one row of high-use shortcuts, then one card per module
	linking to that module's top-level doctypes. Safe to re-run — deletes
	and rebuilds the workspace each time rather than trying to diff it."""

	if frappe.db.exists("Workspace", "AI Education Suite"):
		frappe.delete_doc("Workspace", "AI Education Suite", ignore_permissions=True, force=True)

	def block_id():
		return frappe.generate_hash(length=10)

	shortcuts = [
		("Open AI Dashboard", "ai-education-dashboard", "Page"),
		("AI Settings", "AI Settings", "DocType"),
		("Student Risk Score", "Student Risk Score", "DocType"),
		("AI Grading Suggestion", "AI Grading Suggestion", "DocType"),
		("AI Question Paper Draft", "AI Question Paper Draft", "DocType"),
	]

	# (card title, [(label, doctype), ...])
	cards = [
		("Risk Prediction", [("Student Risk Score", "Student Risk Score")]),
		("Grading Assist", [("AI Grading Suggestion", "AI Grading Suggestion")]),
		("Question Paper AI", [
			("Class Performance Snapshot", "Class Performance Snapshot"),
			("AI Question Paper Draft", "AI Question Paper Draft"),
			("Topic Tag", "Topic Tag"),
		]),
		("Library AI", [("Book Recommendation Log", "Book Recommendation Log")]),
		("Sports AI", [("Team Balance Suggestion", "Team Balance Suggestion")]),
		("House Allocation", [
			("House", "House"),
			("House Allocation Suggestion", "House Allocation Suggestion"),
		]),
		("Admissions AI", [("Applicant Screening Result", "Applicant Screening Result")]),
		("Query Assistant", [("Query Assistant Log", "Query Assistant Log")]),
		("Settings", [("AI Settings", "AI Settings")]),
	]

	content = []
	content.append({"id": block_id(), "type": "spacer", "data": {"col": 12}})
	content.append({
		"id": block_id(), "type": "header",
		"data": {"text": "<span class=\"h4\"><b>AI Education Suite</b></span>", "col": 12},
	})
	content.append({
		"id": block_id(), "type": "paragraph",
		"data": {
			"text": "AI-powered add-ons for risk prediction, grading, question papers, "
			        "library and sports recommendations, house allocation, admissions "
			        "screening and natural-language queries.",
			"col": 12,
		},
	})
	for label, _dt, _type in shortcuts:
		content.append({"id": block_id(), "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})
	content.append({"id": block_id(), "type": "spacer", "data": {"col": 12}})
	content.append({
		"id": block_id(), "type": "header",
		"data": {"text": "<span class=\"h4\"><b>Modules</b></span>", "col": 12},
	})
	for card_title, _items in cards:
		content.append({"id": block_id(), "type": "card", "data": {"card_name": card_title, "col": 4}})

	ws = frappe.new_doc("Workspace")
	ws.name = "AI Education Suite"
	ws.label = "AI Education Suite"
	ws.title = "AI Education Suite"
	ws.module = "AI Core"
	ws.icon = "list"
	ws.public = 1
	ws.is_hidden = 0
	ws.hide_custom = 0
	ws.for_user = ""
	ws.parent_page = ""
	ws.sequence_id = 10
	ws.content = json.dumps(content)

	for label, dt, link_type in shortcuts:
		ws.append("shortcuts", {"type": link_type, "link_to": dt, "label": label})

	idx = 0
	for card_title, items in cards:
		idx += 1
		ws.append("links", {
			"idx": idx, "type": "Card Break", "label": card_title, "link_count": len(items),
		})
		for label, dt in items:
			idx += 1
			ws.append("links", {
				"idx": idx, "type": "Link", "label": label, "link_type": "DocType", "link_to": dt,
			})

	ws.insert(ignore_permissions=True)
	frappe.db.commit()
	print("Created workspace: AI Education Suite")


def dump_education_workspace():
	"""Temporary helper: dumps the installed 'Education' workspace's exact
	structure (content blocks, shortcuts, links/cards) so a new AI Education
	Suite workspace can be built matching the same schema version. Read-only."""
	doc = frappe.get_doc("Workspace", "Education")
	out = doc.as_dict()
	for k in ["owner", "modified_by", "creation", "modified", "docstatus", "idx"]:
		out.pop(k, None)
	print(json.dumps(out, indent=2, default=str))


def introspect_grading_workflow_doctypes():
	"""Temporary helper: dumps schema for the doctypes the new grading-workflow
	redesign depends on (Course Enrollment, Student Group + its child table),
	so the new backend can be written against real field names. Read-only."""
	doctypes = ["Course Enrollment", "Student Group", "Student Group Student"]
	for dt in doctypes:
		try:
			meta = frappe.get_meta(dt)
		except Exception as e:
			print(f"=== {dt} === COULD NOT LOAD: {e}")
			continue
		print(f"=== {dt} === (istable={meta.istable}, is_submittable={meta.is_submittable})")
		for f in meta.fields:
			if f.fieldtype in ("Section Break", "Column Break", "Tab Break"):
				continue
			flags = []
			if f.reqd:
				flags.append("REQD")
			if f.fieldtype == "Table":
				flags.append(f"TABLE->{f.options}")
			print(f"  {f.fieldname:30s} {f.fieldtype:15s} {(f.options or '')[:25]:25s} {' '.join(flags)}")
		print()

	# Also check whether the "Course Content" doctype genuinely doesn't exist
	# anywhere, and if so, which installed doctype(s) reference it.
	print("=== Checking for 'Course Content' doctype ===")
	print("Exists:", frappe.db.exists("DocType", "Course Content"))
	offenders = frappe.get_all(
		"DocField", filters={"options": "Course Content"}, fields=["parent", "fieldname"]
	)
	print("Fields referencing it:", offenders)

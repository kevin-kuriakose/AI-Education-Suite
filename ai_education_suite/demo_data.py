# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Creates a small, consistent demo dataset covering every AI Education Suite
doctype, so you can see the whole system working end to end without waiting
on scheduled jobs or making live Groq API calls (the demo inserts
plausible pre-generated AI output directly, rather than calling the API).

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
	doc.insert(ignore_permissions=True, ignore_mandatory=True)
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
		s = get_or_create(
			"Student",
			{"student_name": full_name},
			{"gender": gender, "enabled": 1},
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
		grading.insert(ignore_permissions=True)

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
		skills = [8.5, 7.0, 6.5, 9.0, 5.5]
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

	frappe.db.commit()
	print("\nDemo data created successfully.")
	print("Visit: AI Settings, Student Risk Score, Class Performance Snapshot,")
	print("AI Question Paper Draft, AI Grading Suggestion, Book Recommendation Log,")
	print("Team Balance Suggestion, House, House Allocation Suggestion.")

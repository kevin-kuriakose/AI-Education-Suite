# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Backend for the redesigned grading workflow:
  1. Teacher picks a Subject (Course) and a Class/Section (Student Group).
  2. We show only students in that group who are actually enrolled in that
     course (via Course Enrollment) -- correctly handling optional subjects
     like Hindi/French where not every student in a section takes it.
     If NO Course Enrollment tracking exists yet for that course at all, we
     fall back to showing every student in the group (so the feature isn't
     just empty for schools that haven't set up enrollment records).
  3. The question paper photo is uploaded ONCE per (course, student_group)
     and reused for every student -- only the answer sheet photo is needed
     per student after that.
"""

import frappe
from frappe.utils import now_datetime, nowdate


@frappe.whitelist()
def get_students_for_course_and_group(course, student_group):
	group_doc = frappe.get_doc("Student Group", student_group)
	members = [
		{"student": row.student, "student_name": row.student_name}
		for row in group_doc.students
		if row.active
	]
	if not members:
		return {"enrollment_tracked": False, "students": []}

	member_names = [m["student"] for m in members]
	enrollment_tracked = bool(frappe.db.exists("Course Enrollment", {"course": course}))

	if not enrollment_tracked:
		# No enrollment tracking set up for this course anywhere yet --
		# treat it as open to everyone in the group rather than showing
		# an empty list.
		for m in members:
			m["enrolled"] = True
		return {"enrollment_tracked": False, "students": members}

	enrolled_set = set(
		frappe.get_all(
			"Course Enrollment",
			filters={"student": ["in", member_names], "course": course},
			pluck="student",
		)
	)
	for m in members:
		m["enrolled"] = m["student"] in enrolled_set

	return {"enrollment_tracked": True, "students": members}


@frappe.whitelist()
def enroll_student_in_course(student, course):
	"""Creates a Course Enrollment record for a student who's in the class
	but wasn't yet enrolled in this particular (optional) subject."""
	if frappe.db.exists("Course Enrollment", {"student": student, "course": course}):
		return {"already_enrolled": True}

	program_enrollment = frappe.db.get_value(
		"Program Enrollment", {"student": student}, "name", order_by="creation desc"
	)
	if not program_enrollment:
		frappe.throw(
			f"{student} has no Program Enrollment on file yet. A student needs a Program "
			"Enrollment (confirming admission for the year) before they can be enrolled in "
			"individual courses. Add that first under Student Applicant / Program Enrollment."
		)

	enrollment = frappe.new_doc("Course Enrollment")
	enrollment.program_enrollment = program_enrollment
	enrollment.course = course
	enrollment.student = student
	enrollment.enrollment_date = nowdate()
	enrollment.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"already_enrolled": False, "name": enrollment.name}


@frappe.whitelist()
def get_question_paper_upload(course, student_group):
	name = frappe.db.get_value(
		"AI Question Paper Upload",
		{"course": course, "student_group": student_group},
		"name",
		order_by="creation desc",
	)
	if not name:
		return None
	doc = frappe.get_doc("AI Question Paper Upload", name)
	return {
		"name": doc.name,
		"question_paper_image": doc.question_paper_image,
		"uploaded_on": doc.uploaded_on,
	}


@frappe.whitelist()
def save_question_paper_upload(course, student_group, file_url):
	doc = frappe.new_doc("AI Question Paper Upload")
	doc.course = course
	doc.student_group = student_group
	doc.question_paper_image = file_url
	doc.uploaded_by = frappe.session.user
	doc.uploaded_on = now_datetime()
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name}

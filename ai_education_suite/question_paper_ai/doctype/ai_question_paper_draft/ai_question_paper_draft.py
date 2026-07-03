# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AIQuestionPaperDraft(Document):
	def validate(self):
		if self.status == "Approved" and not self.approved_on:
			self.approved_on = frappe.utils.now_datetime()
			if not self.approved_by:
				self.approved_by = frappe.session.user

		assigned = sum([q.marks or 0 for q in self.questions])
		if self.questions and self.total_marks and abs(assigned - self.total_marks) > 0.01:
			frappe.msgprint(
				f"Question marks add up to {assigned}, which does not match Total Marks ({self.total_marks}).",
				alert=True, indicator="orange"
			)


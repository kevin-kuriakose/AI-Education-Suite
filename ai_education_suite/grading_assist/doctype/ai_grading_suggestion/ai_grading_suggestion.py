# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AIGradingSuggestion(Document):
	def validate(self):
		if self.teacher_final_score is not None and self.suggested_score is not None:
			self.override_delta = round(self.teacher_final_score - self.suggested_score, 2)
			if self.override_delta == 0:
				self.status = "Accepted"
			else:
				self.status = "Overridden"
			if not self.reviewed_on:
				self.reviewed_on = frappe.utils.now_datetime()
			if not self.reviewed_by:
				self.reviewed_by = frappe.session.user

			settings = frappe.get_single("AI Settings")
			flag_delta = settings.grading_autoflag_delta or 15
			if abs(self.override_delta) >= flag_delta:
				frappe.msgprint(
					"Large override detected ({0} points). Consider reviewing the rubric or prompt "
					"used for this question.".format(self.override_delta),
					alert=True, indicator="orange"
				)


# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StudentRiskScore(Document):
	def validate(self):
		if self.risk_score is not None and not self.risk_level:
			self.risk_level = classify_risk(self.risk_score)


def classify_risk(score):
	settings = frappe.get_single("AI Settings")
	high = settings.risk_high_threshold or 70
	medium = settings.risk_medium_threshold or 40
	if score >= high:
		return "Critical" if score >= high + 15 else "High"
	if score >= medium:
		return "Medium"
	return "Low"


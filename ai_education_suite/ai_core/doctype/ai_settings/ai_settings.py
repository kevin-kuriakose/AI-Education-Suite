# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AISettings(Document):
	def validate(self):
		if self.max_tokens and self.max_tokens < 64:
			frappe.throw("Max Tokens should be at least 64.")
		if self.temperature is not None and (self.temperature < 0 or self.temperature > 1):
			frappe.throw("Temperature must be between 0 and 1.")


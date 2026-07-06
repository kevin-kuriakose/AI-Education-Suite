app_name = "ai_education_suite"
app_title = "AI Education Suite"
app_publisher = "AI Education Suite"
app_description = "AI-powered add-ons for the Frappe/ERPNext Education module: risk prediction, grading assist, question paper generation, house allocation, library & sports AI, admissions screening and a natural-language query assistant."
app_email = "admin@example.com"
app_license = "MIT"
app_version = "0.1.0"

# This app extends the Education module and expects it to already be installed.
required_apps = ["education"]

# Loaded on every Desk page. Redirects the "AI Education Suite" workspace
# straight to our custom dashboard page (see public/js/workspace_redirect.js).
app_include_js = ["/assets/ai_education_suite/js/workspace_redirect.js"]

# Doc Events
# ----------
# Hook into core Education doctypes without modifying them.
doc_events = {
	"Assessment Result": {
		"on_submit": "ai_education_suite.question_paper_ai.performance_analyzer.on_assessment_result_submit"
	},
	"Student Applicant": {
		"after_insert": "ai_education_suite.admissions_ai.screening.on_applicant_created"
	},
}

# Scheduled Tasks
# ---------------
scheduler_events = {
	"daily": [
		"ai_education_suite.risk_prediction.tasks.run_daily_risk_scoring",
	],
	"weekly": [
		"ai_education_suite.library_ai.recommender.weekly_demand_forecast",
		"ai_education_suite.house_allocation.solver.weekly_balance_check",
	],
}

# Fixtures (optional - export AI Settings defaults / roles across sites if needed)
# fixtures = []

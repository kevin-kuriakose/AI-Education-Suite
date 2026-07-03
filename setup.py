from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

setup(
	name="ai_education_suite",
	version="0.1.0",
	description="AI-powered add-ons for the ERPNext/Frappe Education module: risk prediction, grading assist, question paper generation, house allocation, library & sports AI, admissions screening and a natural-language query assistant.",
	author="AI Education Suite",
	author_email="admin@example.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)

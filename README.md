# AI Education Suite

AI-powered add-ons for the **Frappe Education module** (ERPNext v15+). Ships as a
standalone, installable Frappe app that layers AI features on top of the existing
Education / Library / Hostel / Sports doctypes **without modifying core code**.

## Modules

| Module | What it does |
|---|---|
| `ai_core` | Central `AI Settings` singleton + shared Groq API client used by every module |
| `risk_prediction` | Computes a dropout/at-risk score per student from attendance, assessment results and fee history |
| `grading_assist` | AI-suggested scores + rationale for subjective answers, with teacher override tracking |
| `question_paper_ai` | Analyses class performance by topic, then generates weighted draft question papers |
| `library_ai` | Curriculum-aware book recommendations + demand forecasting |
| `sports_ai` | Skill-balanced team suggestions for inter-house/inter-class matches |
| `house_allocation` | Constraint-based house allocation & rebalancing (siblings, gender, academic/sports balance) |
| `admissions_ai` | Screens & scores `Student Applicant` records for human review (never auto-decides) |
| `query_assistant` | Natural-language question answering over a safelisted set of Education doctypes |

## Design principles

1. **Human-in-the-loop everywhere.** Every AI output lands in a doctype with a
   `status`/review field (Pending Review, Draft, Suggested, etc.). Nothing is
   auto-applied to a student's record without a human accepting it.
2. **One shared API client.** All LLM calls go through
   `ai_core/utils/claude_client.py` (module talks to Groq's free-tier,
   OpenAI-compatible API — Llama, Qwen, GPT-OSS models), driven by the single
   `AI Settings` doctype (API key, model, per-feature toggles, token/temperature limits).
3. **No core modification.** Everything is additive — new doctypes, doc events,
   and scheduled jobs. Uninstalling the app removes the AI layer cleanly.
4. **Every AI-generated suggestion is logged and auditable** (who reviewed it,
   what was overridden, by how much) so you can measure real-world accuracy
   for your own institution instead of relying on published benchmarks.

## Installation

```bash
# from your bench directory
bench get-app ai_education_suite /path/to/ai_education_suite   # or a git URL
bench --site yoursite.local install-app ai_education_suite
bench --site yoursite.local migrate
```

> Requires the `frappe/education` app to already be installed on the site
> (for Student, Course, Student Group, Assessment Result, etc). Declared as a
> `required_apps` dependency in `hooks.py`.

### Configure

1. Go to **AI Settings** (single doctype, search in the awesome bar).
2. Paste your Groq API key (free, no credit card — get one at
   console.groq.com), choose a model, set max tokens/temperature.
3. Toggle on the modules you want active. Everything is OFF by default for
   the risk/grading/admissions modules until you explicitly enable them.

### Load demo data

```bash
bench --site yoursite.local execute ai_education_suite.demo_data.generate_demo_data
```

This creates a small consistent dataset (students, courses, a student group,
assessment results, and one populated example of every AI doctype) so you can
see the whole loop working end to end without waiting for a scheduled job or
a live Groq call.

## The feedback loop (question_paper_ai)

```
Assessment Result submitted
        │  (doc event)
        ▼
Class Performance Snapshot rebuilt  ──► Topic Weakness Detail (per topic)
        │
        ▼
AI Question Paper Draft generated, weighted toward weak topics
        │
        ▼
Teacher reviews/edits/approves  ──► Exam happens ──► new Assessment Results
        │
        └──────────────── loop repeats, term over term ─────────────────┘
```

## Safety notes

- `query_assistant` only allows a safelisted set of doctypes/fields for its
  generated filters — the model's output is validated against `frappe.get_meta`
  before any query executes.
- `grading_assist` and `admissions_ai` never write back to the source record
  (`Assessment Result`, `Student Applicant`) — they only create a linked
  suggestion doctype for a human to accept or override.
- `house_allocation` treats sibling/guardian grouping as a hard constraint by
  default (configurable), and the solver's balancing logic is rule-based, not
  LLM-based — the model is only used to write the plain-English explanation.

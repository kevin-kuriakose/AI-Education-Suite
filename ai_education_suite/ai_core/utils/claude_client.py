# Copyright (c) 2024, AI Education Suite and contributors
# For license information, please see license.txt

"""
Single shared wrapper around an LLM chat-completions API.

NOTE: this module is still named `claude_client.py` (to avoid touching every
module that imports it), but it now talks to Groq's free-tier, OpenAI-compatible
API instead of Anthropic's. Every AI module in this app calls through here so that:
  - the API key / model / token limits live in one place (AI Settings)
  - errors are logged consistently
  - feature toggles are respected before any network call is made

Groq hosts open-weight models (Llama, Qwen, GPT-OSS, etc) on an OpenAI-compatible
/chat/completions endpoint. Docs: https://console.groq.com/docs/api-reference
"""

import json
import re
import frappe
from frappe import _
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Reasoning-capable models (Qwen3, GPT-OSS, DeepSeek-R1 distills) emit a
# <think>...</think> block before the answer unless told otherwise. We ask
# Groq to strip it server-side via reasoning_format, and also strip
# defensively client-side in case a future model on this list ignores it.
REASONING_MODEL_PREFIXES = ("qwen/", "openai/gpt-oss", "deepseek")
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class ClaudeClientError(Exception):
	pass


def get_settings():
	settings = frappe.get_single("AI Settings")
	if not settings.enable_ai_features:
		frappe.throw(_("AI Features are disabled in AI Settings."))
	if not settings.get_password("groq_api_key", raise_exception=False):
		frappe.throw(_("Groq API Key is not configured in AI Settings."))
	return settings


def is_module_enabled(fieldname):
	"""Check a specific feature toggle, e.g. is_module_enabled('enable_risk_prediction')."""
	settings = frappe.get_single("AI Settings")
	return bool(settings.enable_ai_features) and bool(settings.get(fieldname))


def call_claude(prompt, system=None, max_tokens=None, temperature=None, model=None):
	"""
	Generic call to the Groq chat-completions API (OpenAI-compatible shape).
	Returns the text of the first choice's message content.
	"""
	settings = get_settings()
	api_key = settings.get_password("groq_api_key")

	messages = []
	if system:
		messages.append({"role": "system", "content": system})
	messages.append({"role": "user", "content": prompt})

	chosen_model = model or settings.model or DEFAULT_MODEL

	payload = {
		"model": chosen_model,
		# Groq deprecated `max_tokens` in favor of `max_completion_tokens`.
		"max_completion_tokens": int(max_tokens or settings.max_tokens or 1024),
		"messages": messages,
	}

	temp = temperature if temperature is not None else settings.temperature
	if temp is not None:
		payload["temperature"] = float(temp)

	if chosen_model.startswith(REASONING_MODEL_PREFIXES):
		# Return only the final answer, not the chain-of-thought.
		payload["reasoning_format"] = "parsed"

	headers = {
		"Authorization": f"Bearer {api_key}",
		"content-type": "application/json",
	}

	try:
		response = requests.post(GROQ_API_URL, headers=headers, data=json.dumps(payload), timeout=60)
		response.raise_for_status()
	except requests.exceptions.RequestException:
		frappe.log_error(title="Groq API Error", message=frappe.get_traceback())
		raise ClaudeClientError("Groq API request failed. See Error Log for details.")

	data = response.json()
	choices = data.get("choices") or []
	if not choices:
		frappe.log_error(title="Groq API Error", message=f"No choices in response:\n{data}")
		raise ClaudeClientError("Groq API returned no choices.")

	content = choices[0].get("message", {}).get("content") or ""
	# Defensive strip in case reasoning_format="parsed" wasn't honored for
	# some model/version. Cheap no-op when there's no <think> block.
	content = THINK_BLOCK_RE.sub("", content)
	return content.strip()


def call_claude_json(prompt, system=None, max_tokens=None, model=None):
	"""
	Calls the LLM and expects a pure JSON response (list or dict).
	Strips markdown code fences defensively, then parses.
	Raises ClaudeClientError on malformed JSON (never guesses / half-parses).
	"""
	json_system = (
		(system or "")
		+ "\n\nRespond ONLY with valid JSON. No preamble, no explanation, no markdown code fences."
	)
	raw = call_claude(prompt, system=json_system, max_tokens=max_tokens, model=model)
	cleaned = raw.strip()
	if cleaned.startswith("```"):
		cleaned = cleaned.strip("`")
		if cleaned.lower().startswith("json"):
			cleaned = cleaned[4:]
	cleaned = cleaned.strip()
	try:
		return json.loads(cleaned)
	except json.JSONDecodeError as e:
		frappe.log_error(title="Groq JSON Parse Error", message=f"{e}\n\nRaw response:\n{raw}")
		raise ClaudeClientError(f"Could not parse Groq response as JSON: {e}")

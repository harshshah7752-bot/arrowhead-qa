"""Build system + user prompts from config."""
from __future__ import annotations
import json
from .config import Config


def build_system_prompt(cfg: Config) -> str:
    cats = [c for c in cfg.categories if c.enabled]
    cat_lines = [
        f"{i+1}. {c.id} (default severity: {c.severity}) — {c.description}"
        for i, c in enumerate(cats)
    ]
    rule_lines = [
        f"- {r.id} (severity: {r.severity}) — {r.description}"
        for r in cfg.custom_rules
    ]

    fewshot_block = ""
    if cfg.few_shot:
        examples = "\n\n".join(
            f"EXAMPLE INPUT:\n{ex.input}\n\nEXAMPLE FLAG:\n{json.dumps(ex.flag, indent=2)}"
            for ex in cfg.few_shot
        )
        fewshot_block = f"\n\n# Few-shot anchors\n{examples}\n"

    rules_block = ""
    if rule_lines:
        rules_block = "\n\n# Company-specific custom rules (treat with priority)\n" + "\n".join(rule_lines)

    return f"""{cfg.persona.strip()}

# Output schema (STRICT JSON, no prose outside JSON)
{{
  "call_summary": "1-2 sentence summary",
  "overall_severity": "none|low|medium|high|critical",
  "language_quality": {{
    "bot_language": "en|hi|mixed|other",
    "customer_language": "en|hi|mixed|other",
    "code_switching_issues": "..."
  }},
  "metrics": {{
    "total_turns": 0,
    "duration_seconds": 0.0,
    "customer_repeated_greeting_count": 0,
    "bot_self_repetition_count": 0,
    "long_silences_count": 0,
    "interruptions_count": 0,
    "customer_frustration_signals": 0
  }},
  "flags": [
    {{
      "category": "<id from categories below>",
      "severity": "low|medium|high|critical",
      "turn_index": 0,
      "timestamp": "mm:ss",
      "speaker": "bot|customer|both|unknown",
      "quote": "<verbatim transcript snippet>",
      "explanation": "<grounded reasoning>",
      "recommendation": "<concrete fix>"
    }}
  ],
  "transcript": "<full diarized transcript with [mm:ss] BOT/CUSTOMER: lines>"
}}

# Error categories — flag EVERY occurrence; multiple flags per category allowed
{chr(10).join(cat_lines)}
{rules_block}
{fewshot_block}

# Rules
- Be exhaustive. Multiple flags per category allowed.
- Use VERBATIM quotes in the quote field. Never paraphrase.
- Ground every flag in audio evidence (silence duration, tone, overlap, repetition).
- For multilingual calls, transcribe in original language; do not auto-translate the quote field.
- If audio is empty or unreadable, return flags=[] and put the issue in call_summary.
- Output JSON only. No markdown fences. No prose.
"""


def build_audio_user_prompt(cfg: Config, source: str) -> str:
    return f"""Audio recording of an AI voice bot calling a customer.
Source: {source}
Expected language: {cfg.analysis.expected_language}

Tasks:
1. Diarize and transcribe with [mm:ss] timestamps and BOT/CUSTOMER labels.
2. Detect EVERY error per the categories in the system prompt. Use audio signals,
   not just words (silences, overlaps, tone, prosody, repetition).
3. Populate the metrics block accurately.
4. Return JSON only, matching the schema exactly.
"""


def build_text_user_prompt(cfg: Config, source: str, transcript: str) -> str:
    return f"""Call transcript scraped from Arrowhead dashboard.
Source: {source}

TRANSCRIPT (raw text — diarization may be imperfect):
---
{transcript}
---

Detect every error per the categories. Return JSON only.
"""

# arrowhead-qa

Gemini-powered QA analyzer for Arrowhead AI voice-bot call recordings. Feed it a
call audio (.wav) URL or a dashboard link, get back a JSON + Markdown report
flagging every quality issue: repeated greetings, bot self-repetition, missed
escalations, hallucinations, code-switch errors, compliance misses, and 25+
other categories. Every flag is fully configurable.

## Why audio over dashboard transcript

| Signal | Dashboard text | Raw audio (this tool) |
|---|---|---|
| Repeated hellos | sometimes deduped by STT | preserved |
| Silences / dead air | invisible | measurable |
| Interruptions / talk-over | invisible | audible |
| Tone (frustration, anger) | words only | direct |
| Robotic prosody | invisible | audible |
| Access | needs dashboard login + selectors | just a URL |

The `audio` mode is the recommended path. `dashboard` mode is a fallback.

## Install

Requires Python ≥ 3.10.

```bash
git clone https://github.com/<you>/arrowhead-qa
cd arrowhead-qa
python -m venv .venv && source .venv/bin/activate
pip install -e .
# Only needed if you'll use the `dashboard` fallback mode:
playwright install chromium
```

Grab a Gemini API key from https://aistudio.google.com/apikey and put it in
`.env`:

```bash
cp .env.example .env
# edit .env → GEMINI_API_KEY=...
```

## Quick start

```bash
# Analyze a call recording from a presigned S3 URL
arrowhead-qa audio "https://voicebot-calls-prod.s3.amazonaws.com/.../call.wav?X-Amz-Signature=..."

# Or a local file
arrowhead-qa audio ./recordings/call.wav

# Process many calls
arrowhead-qa batch examples/urls.txt --csv reports/summary.csv

# Fallback: scrape transcript from dashboard (first run prompts login)
arrowhead-qa dashboard "https://dashboard-bot.arrowhead.team/customers/<id>?call_id=<id>&tab=CALLS&call_tab=TRANSCRIPT"
```

Reports are written to `reports/report-<timestamp>.{json,md}`.

## Tweaking the analysis

The full ruleset lives in [`config/default.yaml`](config/default.yaml). Override
any piece of it locally:

```bash
arrowhead-qa init-config         # writes arrowhead-qa.yaml in cwd
$EDITOR arrowhead-qa.yaml        # tweak categories, severities, persona, rules
arrowhead-qa audio <url>         # auto-picks up ./arrowhead-qa.yaml
# or explicitly:
arrowhead-qa audio <url> --config path/to/custom.yaml
```

What you can change:

- **`persona`** — system role Gemini plays. Make it stricter, domain-specific, multilingual.
- **`categories`** — add, remove, disable, or re-weight any of the 30 default error categories.
- **`custom_rules`** — inject company-specific policy ("must say disclaimer X in first 30s").
- **`few_shot`** — anchor judgement with real labeled examples from your calls.
- **`analysis.min_severity`** — hide noise below `medium` from the rendered table (raw JSON still has it).
- **`analysis.expected_language`** — `auto | en | hi | hi-en | ...`
- **`model.name`** — swap `gemini-2.5-pro` ↔ `gemini-2.5-flash` for cost/speed.
- **`model.temperature`** — 0.0 for maximum determinism in QA work.

CLI flags (`--model`, `--min-severity`, `--lang`) override the config per run
without editing it. See an opinionated healthcare example at
[`examples/example-config.yaml`](examples/example-config.yaml).

```bash
arrowhead-qa list-categories         # show active categories
arrowhead-qa list-categories -c examples/example-config.yaml
```

## What gets detected (default categories)

`repeated_greeting`, `bot_self_repetition`, `customer_repetition`,
`long_silence`, `no_response_to_question`, `misunderstanding`, `interruption`,
`talk_over`, `wrong_language`, `unnatural_phrasing`, `hallucination`,
`pii_leak`, `compliance_issue`, `tone_mismatch`, `customer_frustration`,
`asked_for_human`, `hangup_threat`, `premature_hangup`, `loop`,
`dtmf_or_ivr_confusion`, `background_noise_ignored`, `wrong_name_usage`,
`context_loss`, `promise_broken`, `unclear_purpose`, `abrupt_topic_shift`,
`data_capture_failure`, `confirmation_missing`,
`negative_sentiment_unaddressed`, `other`.

Each flag carries: severity, timestamp, speaker, verbatim quote, explanation,
and a concrete recommendation.

## How the analysis is kept solid

- **Strict JSON schema** validated with Pydantic; Gemini gets a corrective
  retry on bad output (`model.max_retries`).
- **Verbatim quoting required** — the prompt forbids paraphrasing, so flags
  remain auditable against the recording.
- **Audio-grounded** — the prompt instructs Gemini to use silences, overlaps,
  and tone, not just transcribed words.
- **Temperature 0.1 default** — deterministic enough for QA, configurable.
- **Per-category severities + min-severity filter** — tune what counts as
  signal vs noise without changing code.
- **Custom rules + few-shot examples** — anchor company policy and edge cases.

## Project layout

```
arrowhead-qa/
├── config/default.yaml        # editable ruleset
├── examples/                  # urls.txt, example-config.yaml
├── src/arrowhead_qa/
│   ├── cli.py                 # typer CLI (audio | dashboard | batch | init-config | list-categories)
│   ├── config.py              # YAML + pydantic loader, deep-merge user overrides
│   ├── schema.py              # AnalysisResult schema (Flag, Metrics, ...)
│   ├── prompts.py             # builds system + user prompts from config
│   ├── gemini.py              # client wrapper, upload, retry, JSON validation
│   ├── analyze.py             # analyze_audio() / analyze_text()
│   ├── dashboard.py           # playwright fallback scraper
│   └── report.py              # rich terminal output + JSON/markdown writers
├── pyproject.toml
└── README.md
```

## Security notes

- Presigned S3 URLs contain a signature in the query string. Do not paste them
  into public chats or commit them.
- `.env` is gitignored. Never commit `GEMINI_API_KEY`.
- Reports may contain customer PII pulled from call audio. Treat the `reports/`
  directory as sensitive.

## License

MIT — see [LICENSE](LICENSE).

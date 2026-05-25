"""Gemini client wrapper with retry + JSON validation."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any
import urllib.request
import tempfile
from urllib.parse import urlparse

from google import genai
from google.genai import types
from pydantic import ValidationError

from .config import Config
from .schema import AnalysisResult


def get_client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set. Put it in .env or environment.")
    return client_from_key(key)


def client_from_key(key: str) -> genai.Client:
    return genai.Client(api_key=key)


def download_to_tempfile(url: str) -> Path:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    urllib.request.urlretrieve(url, tmp.name)
    return Path(tmp.name)


def upload_and_wait(client: genai.Client, path: Path, timeout_s: int = 120):
    f = client.files.upload(file=str(path))
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        f = client.files.get(name=f.name)
        state = f.state.name if hasattr(f.state, "name") else str(f.state)
        if state == "ACTIVE":
            return f
        if state == "FAILED":
            raise RuntimeError("Gemini file upload FAILED")
        time.sleep(1)
    raise TimeoutError("Gemini file upload did not become ACTIVE in time")


def call_gemini_json(
    client: genai.Client,
    cfg: Config,
    contents: list[Any],
    system_prompt: str,
) -> AnalysisResult:
    """Call Gemini, validate JSON against AnalysisResult, retry on failure."""
    last_err: Exception | None = None
    for attempt in range(cfg.model.max_retries + 1):
        resp = client.models.generate_content(
            model=cfg.model.name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=cfg.model.temperature,
            ),
        )
        raw = resp.text or "{}"
        try:
            data = json.loads(raw)
            return AnalysisResult(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            # Append a corrective message and retry
            contents = contents + [
                f"Your previous response failed validation: {e}. "
                f"Return JSON ONLY, matching the schema in the system prompt exactly."
            ]
            continue
    raise RuntimeError(f"Gemini returned invalid JSON after {cfg.model.max_retries+1} attempts: {last_err}")

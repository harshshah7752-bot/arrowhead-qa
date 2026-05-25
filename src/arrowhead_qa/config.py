"""Config loader. Merges default.yaml with user overrides."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent.parent
DEFAULT_CONFIG = REPO_DIR / "config" / "default.yaml"


class ModelCfg(BaseModel):
    name: str = "gemini-2.5-pro"
    temperature: float = 0.1
    max_retries: int = 2


class AnalysisCfg(BaseModel):
    expected_language: str = "auto"
    min_severity: str = "low"
    mode: str = "single_pass"


class OutputCfg(BaseModel):
    save_json: bool = True
    save_markdown: bool = True
    reports_dir: str = "reports"


class Category(BaseModel):
    id: str
    enabled: bool = True
    severity: str = "medium"
    description: str


class CustomRule(BaseModel):
    id: str
    severity: str = "medium"
    description: str


class FewShot(BaseModel):
    input: str
    flag: dict[str, Any]


class Config(BaseModel):
    model: ModelCfg = Field(default_factory=ModelCfg)
    analysis: AnalysisCfg = Field(default_factory=AnalysisCfg)
    output: OutputCfg = Field(default_factory=OutputCfg)
    persona: str = ""
    categories: list[Category] = Field(default_factory=list)
    few_shot: list[FewShot] = Field(default_factory=list)
    custom_rules: list[CustomRule] = Field(default_factory=list)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(user_path: str | Path | None = None) -> Config:
    with open(DEFAULT_CONFIG) as f:
        data = yaml.safe_load(f) or {}

    if user_path:
        p = Path(user_path)
        if not p.exists():
            raise FileNotFoundError(f"config not found: {p}")
        with open(p) as f:
            user = yaml.safe_load(f) or {}
        # For list fields, user can replace entirely or augment via merge_lists keys.
        # Simple rule: lists are replaced if present in user config; dicts deep-merged.
        data = _deep_merge(data, user)
    else:
        # Auto-detect local ./arrowhead-qa.yaml
        local = Path.cwd() / "arrowhead-qa.yaml"
        if local.exists():
            with open(local) as f:
                user = yaml.safe_load(f) or {}
            data = _deep_merge(data, user)

    return Config(**data)

"""Pydantic schema for Gemini's JSON response."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

Severity = Literal["none", "low", "medium", "high", "critical"]


class Flag(BaseModel):
    category: str
    severity: Severity
    turn_index: Optional[int] = None
    timestamp: Optional[str] = None  # mm:ss or hh:mm:ss
    speaker: Literal["bot", "customer", "both", "unknown"] = "unknown"
    quote: str = ""
    explanation: str = ""
    recommendation: str = ""


class LanguageQuality(BaseModel):
    bot_language: str = "unknown"
    customer_language: str = "unknown"
    code_switching_issues: str = ""


class Metrics(BaseModel):
    total_turns: int = 0
    duration_seconds: Optional[float] = None
    customer_repeated_greeting_count: int = 0
    bot_self_repetition_count: int = 0
    long_silences_count: int = 0
    interruptions_count: int = 0
    customer_frustration_signals: int = 0


class AnalysisResult(BaseModel):
    call_summary: str = ""
    overall_severity: Severity = "none"
    language_quality: LanguageQuality = Field(default_factory=LanguageQuality)
    metrics: Metrics = Field(default_factory=Metrics)
    flags: list[Flag] = Field(default_factory=list)
    transcript: str = ""

    def severity_at_or_above(self, threshold: Severity) -> list[Flag]:
        order = ["none", "low", "medium", "high", "critical"]
        cutoff = order.index(threshold)
        return [f for f in self.flags if order.index(f.severity) >= cutoff]

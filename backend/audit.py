"""Append-only audit trail of agent-loop activity: output/audit_trail.json.

One entry (AuditEntry in models.py) per agent-loop iteration, that is, per model response: the
time, which tools it called with short arguments and results, the stop reason, tokens, and
whether it ended the run. Entries are only ever added, never removed, across server restarts.
Summarize it with:  .venv/bin/python audit_report.py
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from models import AuditEntry

AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"
MAX_TEXT = 200  # characters kept from any argument, result, or message

_lock = threading.Lock()
_LONG_NUMBER = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")  # card-like numbers
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact(text: str) -> str:
    """Hide card-like numbers and email addresses before anything is written."""
    return _EMAIL.sub("[email]", _LONG_NUMBER.sub("[redacted number]", text))


def shorten(value: Any, limit: int = MAX_TEXT) -> str:
    text = value.model_dump_json() if isinstance(value, BaseModel) else str(value)
    text = redact(" ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def short_args(args: dict[str, Any]) -> dict[str, Any]:
    return {k: (shorten(v, 80) if isinstance(v, str) else v) for k, v in args.items()}


def append(entries: list[AuditEntry]) -> None:
    """Add entries to the end of output/audit_trail.json, keeping every earlier entry."""
    if not entries:
        return
    with _lock:
        existing = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
        existing.extend(e.model_dump(mode="json") for e in entries)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(AUDIT_PATH)  # atomic swap: a crash mid-write never loses earlier entries

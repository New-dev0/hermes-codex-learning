from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|authorization|bearer)\s*[:=]\s*['\"]?[^\s'\"]+"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]

SENSITIVE_PATH_FRAGMENTS = [
    ".env",
    "auth.json",
    ".git-credentials",
    "id_rsa",
    "id_ed25519",
    "cookies",
    "cookie",
    "credentials",
    "keychain",
]


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw_stdin": redact(raw)[:4000]}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if re.search(r"(?i)(token|secret|password|passwd|authorization|cookie|key)", str(k)):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    text = value
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=[REDACTED]", text)
    return text


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()


def codex_learning_dir() -> Path:
    return hermes_home() / "codex-learning"


def event_path(session_id: str) -> Path:
    return codex_learning_dir() / "events" / f"{safe_name(session_id)}.jsonl"


def run_summary_path(session_id: str) -> Path:
    return codex_learning_dir() / "runs" / f"{safe_name(session_id)}.summary.json"


def safe_name(name: str | None) -> str:
    raw = name or "unknown-session"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)[:160] or "unknown-session"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hermes_available() -> bool:
    return shutil.which("hermes") is not None or (hermes_home() / "hermes-agent").exists()


def append_event(event_name: str, payload: dict[str, Any], extra: dict[str, Any] | None = None) -> Path:
    session_id = str(payload.get("session_id") or "unknown-session")
    path = event_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": now_iso(),
        "event": event_name,
        "session_id": session_id,
        "cwd": payload.get("cwd"),
        "model": payload.get("model"),
        "permission_mode": payload.get("permission_mode"),
        "hermes_home": str(hermes_home()),
        "hermes_available": hermes_available(),
        "payload": redact(compact_payload(payload)),
    }
    if extra:
        event["extra"] = redact(extra)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    keep = {}
    for key in [
        "hook_event_name", "source", "turn_id", "tool_name", "tool_use_id",
        "tool_input", "tool_response", "cwd", "transcript_path", "session_id",
    ]:
        if key in payload:
            keep[key] = payload[key]
    return keep


def create_hermes_inbox_skill() -> Path | None:
    home = hermes_home()
    if not home.exists():
        return None
    skill_dir = home / "skills" / "codex-learning-inbox"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill = skill_dir / "SKILL.md"
    content = """---
name: codex-learning-inbox
description: Review Codex hook summaries exported by the Hermes Codex Learning plugin and convert useful findings into Hermes memories, skills, or reports.
---

# Codex Learning Inbox

Use this skill when asked to review what Codex learned or when improving Hermes from Codex runs.

Read local summaries from:

```text
~/.hermes/codex-learning/runs/*.summary.json
~/.hermes/codex-learning/events/*.jsonl
```

Process:
1. Read the newest run summaries.
2. Redact any sensitive values before quoting.
3. Classify candidates:
   - durable user preference → Hermes memory candidate
   - reusable workflow → skill candidate
   - tool-specific failure/workaround → skill/tool quirk candidate
   - project convention → project guidance candidate
   - one-off status → ignore
4. Do not store transient PR numbers, commit SHAs, temporary issue IDs, or metrics as durable memory.
5. Patch existing Hermes skills when a loaded skill was stale or incomplete.
6. Ask before creating a brand-new skill unless the user explicitly requested autonomous skill creation.
"""
    if not skill.exists() or "Codex Learning Inbox" not in skill.read_text(encoding="utf-8", errors="ignore"):
        skill.write_text(content, encoding="utf-8")
    return skill


def command_string(payload: dict[str, Any]) -> str:
    ti = payload.get("tool_input") or {}
    if isinstance(ti, dict):
        return str(ti.get("command") or ti.get("cmd") or ti)
    return str(ti)


def looks_sensitive_command(command: str) -> str | None:
    c = command.lower()
    readers = ("cat", "less", "more", "head", "tail", "grep", "rg", "sed", "awk", "python", "node", "perl", "type", "Get-Content".lower())
    if not any(r.lower() in c for r in readers):
        return None
    for frag in SENSITIVE_PATH_FRAGMENTS:
        if frag.lower() in c:
            return frag
    return None


def emit_json(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False))

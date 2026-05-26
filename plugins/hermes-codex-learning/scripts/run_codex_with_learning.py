#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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

FAILURE_MARKERS = ["traceback", "error", "failed", "permission denied", "exception", "runtimeerror"]
LEARNING_MARKERS = ["hermes learning candidates", "remember", "skill candidate", "memory candidate", "tool quirk", "project convention"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value)[:160] or "codex-run"


def redact(text: str) -> str:
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub(lambda m: re.split(r"[:=]", m.group(0), 1)[0] + "=[REDACTED]", out)
    return out


def detect_markers(text: str, markers: list[str]) -> list[str]:
    lower = text.lower()
    return [m for m in markers if m in lower]


def create_inbox_skill(hermes_home: Path) -> Path:
    skill_dir = hermes_home / "skills" / "codex-learning-inbox"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill = skill_dir / "SKILL.md"
    if not skill.exists():
        skill.write_text("""---
name: codex-learning-inbox
description: Review Codex learning summaries exported by hooks or the Codex learning wrapper and convert useful findings into Hermes memories, skills, or reports.
---

# Codex Learning Inbox

Use this skill when asked to review what Codex learned or when improving Hermes from Codex runs.

Read local summaries from:

```text
~/.hermes/codex-learning/runs/*.summary.json
~/.hermes/codex-learning/events/*.jsonl
~/.hermes/codex-learning/reviews/*.review.md
```

Rules:
1. Redact secrets before quoting.
2. Classify observations into memory candidates, skill candidates, tool quirks, project conventions, quarantined observations, and transient noise.
3. Do not store one-off task progress, PR numbers, commit SHAs, temporary metrics, or raw secrets as durable memory.
4. Prefer skill patches for reusable workflows and tool quirks.
""", encoding="utf-8")
    return skill


def extract_session_id(output: str) -> str | None:
    match = re.search(r"session id:\s*([A-Za-z0-9_.:-]+)", output, re.I)
    return match.group(1) if match else None


def build_summary(session_id: str, cwd: str, command: list[str], output: str, returncode: int) -> dict[str, Any]:
    clean_output = redact(output)
    failure_markers = detect_markers(clean_output, FAILURE_MARKERS)
    learning_markers = detect_markers(clean_output, LEARNING_MARKERS)
    learning_section = ""
    match = re.search(r"(?is)(Hermes learning candidates.*)$", clean_output)
    if match:
        learning_section = match.group(1)[0:2000]
    failure_excerpt = ""
    if failure_markers:
        idxs = [clean_output.lower().find(m) for m in failure_markers if clean_output.lower().find(m) >= 0]
        start = max(0, min(idxs) - 500) if idxs else 0
        failure_excerpt = clean_output[start:start + 1500]
    return {
        "schema_version": 2,
        "generated_at": now_iso(),
        "source": "run_codex_with_learning",
        "session_id": session_id,
        "cwd": cwd,
        "command": [redact(part) for part in command],
        "returncode": returncode,
        "event_counts": {"CodexExec": 1, "ParsedOutput": 1},
        "failure_events": ([{"markers": failure_markers, "excerpt": failure_excerpt}] if failure_markers else []),
        "learning_markers": ([{"markers": learning_markers, "excerpt": learning_section}] if learning_markers else []),
        "recommended_hermes_review": bool(failure_markers or learning_markers),
        "review_instructions": "Ask Hermes to load codex-learning-inbox and review this summary for memory/skill candidates.",
    }


def write_artifacts(hermes_home: Path, summary: dict[str, Any], raw_output: str) -> tuple[Path, Path]:
    session_id = safe_name(str(summary["session_id"]))
    events_dir = hermes_home / "codex-learning" / "events"
    runs_dir = hermes_home / "codex-learning" / "runs"
    events_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)
    event_path = events_dir / f"{session_id}.jsonl"
    summary_path = runs_dir / f"{session_id}.summary.json"
    event = {
        "ts": now_iso(),
        "event": "CodexExec",
        "session_id": summary["session_id"],
        "cwd": summary.get("cwd"),
        "hermes_home": str(hermes_home),
        "payload": {"output_excerpt": redact(raw_output)[-4000:]},
        "extra": {
            "failure_markers": summary["failure_events"][0]["markers"] if summary["failure_events"] else [],
            "learning_markers": summary["learning_markers"][0]["markers"] if summary["learning_markers"] else [],
        },
    }
    event_path.write_text(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return event_path, summary_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run codex exec and export a Hermes learning summary from the real Codex output.")
    parser.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    parser.add_argument("--session-label", default=None)
    parser.add_argument("--review", action="store_true", help="Run review_codex_learning.py after writing the summary.")
    parser.add_argument("codex_args", nargs=argparse.REMAINDER, help="Arguments after -- are passed to codex exec.")
    args = parser.parse_args()

    codex_args = args.codex_args
    if codex_args and codex_args[0] == "--":
        codex_args = codex_args[1:]
    if not codex_args:
        parser.error("pass codex exec arguments after --")

    hermes_home = Path(args.hermes_home).expanduser().resolve()
    hermes_home.mkdir(parents=True, exist_ok=True)
    create_inbox_skill(hermes_home)

    command = ["codex", "exec", *codex_args]
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    output = proc.stdout or ""
    print(output, end="")
    session_id = args.session_label or extract_session_id(output) or f"codex-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    summary = build_summary(session_id, os.getcwd(), command, output, proc.returncode)
    event_path, summary_path = write_artifacts(hermes_home, summary, output)
    print(f"\n[hermes-codex-learning] event: {event_path}")
    print(f"[hermes-codex-learning] summary: {summary_path}")
    if args.review:
        review_script = Path(__file__).with_name("review_codex_learning.py")
        review = subprocess.run([sys.executable, str(review_script), "--hermes-home", str(hermes_home), "--limit", "1"], text=True)
        if review.returncode != 0:
            return review.returncode
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|authorization|bearer)\s*[:=]\s*['\"]?[^\s'\"]+"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]


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
        text = pat.sub(lambda m: re.split(r"[:=]", m.group(0), 1)[0] + "=[REDACTED]", text)
    return text


def load_summaries(runs: Path, limit: int) -> list[tuple[Path, dict[str, Any]]]:
    files = sorted(runs.glob("*.summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    loaded = []
    for path in files:
        try:
            loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except Exception as exc:
            loaded.append((path, {"error": f"failed to parse summary: {exc}"}))
    return loaded


def classify(summary: dict[str, Any]) -> dict[str, list[str]]:
    out = {
        "memory_candidates": [],
        "skill_candidates": [],
        "tool_quirks": [],
        "project_conventions": [],
        "quarantined_observations": [],
        "discarded_or_transient": [],
    }
    failures = summary.get("failure_events") or []
    markers = summary.get("learning_markers") or []
    for failure in failures:
        markers_text = ", ".join(map(str, failure.get("markers", []))) or "failure"
        excerpt = str(failure.get("excerpt", ""))[:600]
        redacted_excerpt = redact(excerpt)
        out["tool_quirks"].append(f"Observed tool failure markers ({markers_text}). Excerpt: {redacted_excerpt}")
        out["quarantined_observations"].append(
            "Failure observation requires Hermes review before becoming memory/skill because it may be task-specific."
        )
    for marker in markers:
        marker_text = ", ".join(map(str, marker.get("markers", []))) or "learning marker"
        out["skill_candidates"].append(
            f"Codex emitted learning marker ({marker_text}); inspect run transcript/events before patching a skill."
        )
        out["quarantined_observations"].append(
            "Learning marker captured but quarantined until Hermes confirms it is stable, non-secret, and reusable."
        )
    if not failures and not markers:
        out["discarded_or_transient"].append("No failure events or learning markers found in this summary.")
    return out


def render_review(path: Path, summary: dict[str, Any], classified: dict[str, list[str]]) -> str:
    safe_summary = redact(summary)
    lines = [
        "# Codex Learning Review",
        "",
        f"Source summary: `{path}`",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"Session: `{safe_summary.get('session_id', 'unknown')}`",
        "",
        "## Event counts",
        "",
    ]
    for event, count in sorted((safe_summary.get("event_counts") or {}).items()):
        lines.append(f"- {event}: {count}")
    for title, key in [
        ("Memory candidates", "memory_candidates"),
        ("Skill candidates", "skill_candidates"),
        ("Tool quirks", "tool_quirks"),
        ("Project conventions", "project_conventions"),
        ("Quarantined observations", "quarantined_observations"),
        ("Discarded or transient", "discarded_or_transient"),
    ]:
        lines.extend(["", f"## {title}", ""])
        items = classified.get(key) or []
        if not items:
            lines.append("- None.")
        else:
            for item in items:
                lines.append(f"- {item}")
    lines.extend([
        "",
        "## Action policy",
        "",
        "- Do not auto-write arbitrary Hermes memory from this file.",
        "- Safe next action: Hermes reviews this file, then applies explicit memory/skill patches only when stable and non-secret.",
        "- One-off task status, PR numbers, commit SHAs, and raw secrets stay discarded/quarantined.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Codex hook summaries into quarantined Hermes learning review files.")
    parser.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    hermes_home = Path(args.hermes_home).expanduser().resolve()
    runs = hermes_home / "codex-learning" / "runs"
    reviews = hermes_home / "codex-learning" / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)

    summaries = load_summaries(runs, args.limit)
    if not summaries:
        print(f"No Codex learning summaries found in {runs}")
        return 1

    for source, summary in summaries:
        session = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(summary.get("session_id") or source.stem))[:160]
        review_path = reviews / f"{session}.review.md"
        review_path.write_text(render_review(source, summary, classify(summary)), encoding="utf-8")
        print(review_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

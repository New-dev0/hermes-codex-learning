from __future__ import annotations

import json
from collections import Counter
from common import append_event, event_path, read_stdin_json, run_summary_path, emit_json, redact, now_iso

payload = read_stdin_json()
append_event("Stop", payload)
session_id = str(payload.get("session_id") or "unknown-session")
path = event_path(session_id)
events = []
if path.exists():
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                pass
counts = Counter(e.get("event") for e in events)
failure_events = []
learning_markers = []
for e in events:
    extra = e.get("extra") or {}
    if extra.get("failure_markers"):
        failure_events.append({"ts": e.get("ts"), "markers": extra.get("failure_markers"), "excerpt": extra.get("response_excerpt", "")[:500]})
    if extra.get("learning_markers"):
        learning_markers.append({"ts": e.get("ts"), "markers": extra.get("learning_markers")})
summary = {
    "schema_version": 1,
    "generated_at": now_iso(),
    "session_id": session_id,
    "cwd": payload.get("cwd"),
    "event_counts": dict(counts),
    "failure_events": redact(failure_events[-10:]),
    "learning_markers": redact(learning_markers[-10:]),
    "recommended_hermes_review": bool(failure_events or learning_markers),
    "review_instructions": "Ask Hermes to load the codex-learning-inbox skill and review this summary for memory/skill candidates."
}
out = run_summary_path(session_id)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
emit_json({
    "systemMessage": f"Hermes Codex Learning exported session summary to {out}",
    "hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": f"Codex session summary for Hermes is available at {out}."
    }
})

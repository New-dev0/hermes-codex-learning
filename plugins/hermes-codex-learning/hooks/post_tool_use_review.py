from common import append_event, read_stdin_json, emit_json

payload = read_stdin_json()
raw = str(payload.get("tool_response") or payload.get("_raw_stdin") or "")
low = raw.lower()
patterns = []
for marker in ["traceback", "error", "failed", "not found", "permission denied", "timed out", "no such file", "command not found", "rate limit"]:
    if marker in low:
        patterns.append(marker)
append_event("PostToolUse", payload, {"failure_markers": patterns, "response_excerpt": raw[:1000]})
if patterns:
    emit_json({
        "systemMessage": "Tool result may contain a reusable Hermes learning candidate: " + ", ".join(patterns[:8])
    })
else:
    emit_json({"continue": True})

from common import append_event, read_stdin_json, emit_json

payload = read_stdin_json()
text = str(payload.get("prompt") or payload.get("user_prompt") or payload.get("message") or payload.get("_raw_stdin") or "")
markers = ["remember", "don't do", "do not", "not like that", "wrong", "instead", "always", "never", "preference", "use this"]
found = [m for m in markers if m.lower() in text.lower()]
append_event("UserPromptSubmit", payload, {"learning_markers": found})
if found:
    emit_json({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "This prompt contains possible Hermes learning/correction markers: " + ", ".join(found[:8])
        }
    })
else:
    emit_json({"continue": True})

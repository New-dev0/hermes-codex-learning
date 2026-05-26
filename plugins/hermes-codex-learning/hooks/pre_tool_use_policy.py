from common import append_event, command_string, looks_sensitive_command, read_stdin_json, emit_json

payload = read_stdin_json()
cmd = command_string(payload)
reason = looks_sensitive_command(cmd)
append_event("PreToolUse", payload, {"command_excerpt": cmd[:500], "blocked_sensitive_fragment": reason})
if reason:
    emit_json({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Hermes Codex Learning policy blocked a command that appears to read sensitive credential material matching '{reason}'."
        }
    })
else:
    extra = None
    if "~/.hermes" in cmd or "/.hermes" in cmd:
        extra = "Command touches Hermes state. Avoid mutating memories, skills, plugins, cron, or auth unless the user explicitly requested it."
    if extra:
        emit_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": extra
            }
        })
    else:
        emit_json({"continue": True})

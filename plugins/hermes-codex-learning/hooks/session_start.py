from common import append_event, create_hermes_inbox_skill, hermes_available, hermes_home, read_stdin_json, emit_json

payload = read_stdin_json()
skill_path = create_hermes_inbox_skill()
append_event("SessionStart", payload, {"inbox_skill": str(skill_path) if skill_path else None})

if hermes_available():
    emit_json({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "Hermes Agent is present on this machine. If you discover reusable workflows, "
                "tool quirks, or user corrections, include a concise 'Hermes learning candidates' "
                "section in the final answer. Local Codex hook summaries are being written under "
                f"{hermes_home()}/codex-learning/."
            )
        }
    })
else:
    emit_json({"systemMessage": "Hermes Codex Learning plugin active; Hermes was not detected on PATH/home yet."})

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]
CODEX_TOOL_MATCHER = "Bash|shell|exec|apply_patch|Edit|Write|mcp__.*"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"hooks": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        backup = path.with_suffix(path.suffix + ".invalid")
        shutil.copy2(path, backup)
        raise SystemExit(f"Invalid JSON in {path}; copied to {backup}: {exc}") from exc


def script_for(plugin_root: Path, event: str) -> Path:
    mapping = {
        "SessionStart": "session_start.py",
        "UserPromptSubmit": "user_prompt_submit.py",
        "PreToolUse": "pre_tool_use_policy.py",
        "PostToolUse": "post_tool_use_review.py",
        "Stop": "stop_export_summary.py",
    }
    return plugin_root / "hooks" / mapping[event]


def hook_group(plugin_root: Path, event: str) -> dict[str, Any]:
    script = script_for(plugin_root, event).resolve()
    if not script.exists():
        raise SystemExit(f"Missing hook script: {script}")
    group: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": f"python3 {script}",
                "timeout": 30 if event == "Stop" else 10,
                "statusMessage": {
                    "SessionStart": "Connecting Codex session to Hermes learning inbox",
                    "UserPromptSubmit": "Scanning prompt for Hermes learning signals",
                    "PreToolUse": "Checking Hermes/Codex learning safety policy",
                    "PostToolUse": "Capturing tool result for Hermes learning",
                    "Stop": "Exporting Codex session summary for Hermes",
                }[event],
            }
        ]
    }
    if event == "SessionStart":
        group["matcher"] = "startup|resume|clear|compact"
    if event in {"PreToolUse", "PostToolUse"}:
        group["matcher"] = CODEX_TOOL_MATCHER
    return group


def is_our_group(group: dict[str, Any]) -> bool:
    for hook in group.get("hooks", []):
        command = str(hook.get("command", ""))
        if "hermes-codex-learning" in command and "/hooks/" in command:
            return True
    return False


def merge_hooks(existing: dict[str, Any], plugin_root: Path) -> dict[str, Any]:
    hooks = existing.setdefault("hooks", {})
    for event in EVENTS:
        groups = hooks.setdefault(event, [])
        groups = [g for g in groups if not is_our_group(g)]
        groups.append(hook_group(plugin_root, event))
        hooks[event] = groups
    return existing


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Hermes Codex Learning hooks into Codex user hooks.json.")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
    parser.add_argument("--plugin-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser().resolve()
    plugin_root = Path(args.plugin_root).expanduser().resolve()
    path = codex_home / "hooks.json"
    merged = merge_hooks(load_json(path), plugin_root)
    if args.dry_run:
        print(json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        write_json_atomic(path, merged)
        print(f"Installed Hermes Codex Learning hooks into {path}")
        print("Start a new Codex session and review/trust hooks with /hooks if prompted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

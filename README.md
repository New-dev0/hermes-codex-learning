# Hermes Codex Learning

A Codex plugin that helps **Hermes Agent** learn from Codex sessions running on the same machine.

The plugin packages Codex lifecycle hooks and a reusable Codex skill. Once installed and trusted in Codex, the hooks observe Codex sessions, redact sensitive values, write structured learning events into the local Hermes home, and export per-session summaries that Hermes can use to improve skills, memories, and tool reliability notes.

It is for Hermes Agent self-learning and self-improvement.

## What it does

When Codex runs, this plugin can:

- detect whether Hermes is installed on the machine
- write Codex lifecycle events to `~/.hermes/codex-learning/events/`
- export session summaries to `~/.hermes/codex-learning/runs/`
- create/update a small Hermes skill at `~/.hermes/skills/codex-learning-inbox/SKILL.md`
- detect user corrections and self-improvement candidates
- detect tool failures and workaround candidates
- protect common secret files from accidental reads through Codex shell/tool calls
- add small model-visible context at session start when Hermes is present

The plugin does **not** send telemetry to a server. Everything is local.

## Repository layout

```text
.
├── .agents/plugins/marketplace.json
└── plugins/hermes-codex-learning/
    ├── .codex-plugin/plugin.json
    ├── skills/hermes-learning-bridge/SKILL.md
    ├── hooks/hooks.json
    ├── hooks/*.py
    ├── scripts/summarize_codex_run.py
    └── assets/
```

## Install in Codex

From this repository root:

```bash
codex plugin marketplace add .
```

Or from GitHub after publishing:

```bash
codex plugin marketplace add https://github.com/New-dev0/hermes-codex-learning
```

Then open Codex and install/enable the plugin:

```text
/plugins
```

After enabling, start a new Codex thread. Codex hook changes and plugin capabilities are loaded at session/thread startup.

## Hook trust

Codex requires non-managed hooks to be reviewed and trusted before they run. Use:

```text
/hooks
```

Review the hook definitions. The hooks are command hooks and run local Python scripts from the installed plugin root.

## Hermes-side output

Default output paths:

```text
~/.hermes/codex-learning/events/<session_id>.jsonl
~/.hermes/codex-learning/runs/<session_id>.summary.json
~/.hermes/skills/codex-learning-inbox/SKILL.md
```

Set `HERMES_HOME` before launching Codex if your Hermes home is somewhere else.

## Design principle

Codex hooks are used as lifecycle instrumentation. Hermes remains the durable learning system.

Codex session → hook event log → local Hermes inbox → Hermes skill/memory/curator review.

## Safety

The hooks redact common secret-looking values before writing logs. They also block obvious shell attempts to read sensitive Hermes/Codex auth files such as:

- `~/.hermes/.env`
- `~/.hermes/auth.json`
- `~/.codex/auth.json`
- `.env`
- `.git-credentials`
- SSH private keys

This is a best-effort local policy layer, not a complete sandbox.

## Current status

Initial public scaffold. The plugin is intentionally conservative: it writes learning artifacts locally and does not automatically mutate Hermes memories or existing user skills except creating a dedicated `codex-learning-inbox` skill if missing.

## End-to-end verification

```bash
# 1. Marketplace + install
codex plugin marketplace add https://github.com/New-dev0/hermes-codex-learning
codex plugin add hermes-codex-learning --marketplace hermes-codex-learning-marketplace

# 2. Verify install
codex plugin marketplace list
codex plugin list | grep hermes-codex-learning

# 3. Trust hooks interactively, or bypass only for CI/local automation
codex
# then run /hooks and approve Hermes Codex Learning hooks

# 4. Run a tiny Codex session
mkdir -p /tmp/hermes-codex-e2e && cd /tmp/hermes-codex-e2e && git init
codex exec --sandbox workspace-write --dangerously-bypass-hook-trust \
  'Run one harmless shell command: python3 -c '''print("hermes-codex-e2e")'''. Then answer DONE.'

# 5. Check Hermes artifacts
find ~/.hermes/codex-learning ~/.hermes/skills/codex-learning-inbox -maxdepth 4 -type f -print
python3 ~/.codex/plugins/cache/hermes-codex-learning-marketplace/hermes-codex-learning/0.1.0/scripts/summarize_codex_run.py
```

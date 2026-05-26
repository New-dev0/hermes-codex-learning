# Design: Hermes Codex Learning

## Problem

Codex can perform coding work that reveals reusable workflows, project conventions, tool failures, and user corrections. Hermes has strong durable learning surfaces — memories, skills, session search, curator, cron, and plugins — but Codex work is usually summarized as prose and can lose the structured learning signal.

## Approach

Use Codex hooks as lifecycle instrumentation. The plugin does not try to become Hermes. It writes redacted local artifacts that Hermes can later review.

## Event flow

```text
Codex lifecycle event
  -> plugin hook script
  -> redacted JSONL event under ~/.hermes/codex-learning/events/
  -> Stop hook exports ~/.hermes/codex-learning/runs/*.summary.json
  -> Hermes loads codex-learning-inbox skill and reviews candidates
```

## Why hooks

Hooks run at the right moments:

- SessionStart: detect Hermes and inject small context
- UserPromptSubmit: catch corrections/preferences
- PreToolUse: block obvious secret reads and warn on Hermes state mutation
- PostToolUse: capture failure patterns and workaround candidates
- Stop: summarize the run for Hermes

## Non-goals

- No remote telemetry
- No automatic mutation of arbitrary Hermes memories
- No automatic patching of existing user skills
- No secret capture
- No dependency on SwitchX

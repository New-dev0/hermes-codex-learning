---
name: hermes-learning-bridge
description: Use when Codex is working on a machine that also runs Hermes Agent and the user wants Codex work to feed Hermes self-learning/self-improvement.
---

# Hermes Learning Bridge

Use this skill when Codex is running on a machine that also has Hermes Agent installed.

Goal: produce work artifacts and learning artifacts that Hermes can reuse later.

## Operating rules

1. Keep normal task execution first: edit code, run tests, verify results.
2. When you discover a reusable workflow, tool quirk, failure pattern, or user correction, make it explicit in the final answer under `Hermes learning candidates`.
3. Do not put secrets, tokens, cookies, auth files, private keys, or raw environment dumps into learning artifacts.
4. Prefer stable lessons over transient task progress.
5. Distinguish:
   - durable user preference
   - project convention
   - tool quirk
   - reusable workflow
   - temporary task state
   - sensitive data to discard
6. If Hermes is available, the bundled hooks write local summaries under `~/.hermes/codex-learning/`.

## Good learning candidates

- A repeated command or validation sequence that should become a Hermes skill.
- A tool-specific error and the workaround that fixed it.
- A repo convention that should be written to AGENTS.md or a skill.
- A user correction that should change future behavior.
- A safety rule that should prevent a bad action next time.

## Bad learning candidates

- PR numbers, issue numbers, commit SHAs, temporary metrics, or one-off task status.
- Secrets or credential paths beyond generic path names.
- Unverified guesses.
- A failed workaround that was never validated.

## Final answer section

When relevant, add:

```text
Hermes learning candidates:
- Skill candidate: ...
- Memory candidate: ...
- Tool quirk: ...
- Project convention: ...
- Ignore as transient: ...
```

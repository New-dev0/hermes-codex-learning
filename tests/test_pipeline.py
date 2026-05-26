import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins" / "hermes-codex-learning"


def run_py(script: Path, *args: str, env: dict | None = None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        env=merged,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PipelineTests(unittest.TestCase):
    def test_install_codex_hooks_merges_absolute_commands_and_codex_exec_matcher(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            codex_home = root / ".codex"
            existing = codex_home / "hooks.json"
            existing.parent.mkdir(parents=True)
            existing.write_text(json.dumps({
                "hooks": {
                    "Stop": [{"hooks": [{"type": "command", "command": "echo existing"}]}]
                }
            }), encoding="utf-8")

            result = run_py(
                PLUGIN / "scripts" / "install_codex_hooks.py",
                "--codex-home", str(codex_home),
                "--plugin-root", str(PLUGIN),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(existing.read_text(encoding="utf-8"))
            self.assertIn("SessionStart", data["hooks"])
            self.assertTrue(any("echo existing" in h["hooks"][0]["command"] for h in data["hooks"]["Stop"]))

            pre = data["hooks"]["PreToolUse"]
            post = data["hooks"]["PostToolUse"]
            self.assertTrue(any("exec" in group.get("matcher", "") for group in pre))
            self.assertTrue(any("exec" in group.get("matcher", "") for group in post))
            for event_groups in data["hooks"].values():
                for group in event_groups:
                    for hook in group["hooks"]:
                        if "hermes-codex-learning" in hook["command"]:
                            self.assertNotIn("${PLUGIN_ROOT}", hook["command"])
                            self.assertIn(str(PLUGIN), hook["command"])

    def test_run_codex_with_learning_parses_real_codex_output_into_summary(self):
        with tempfile.TemporaryDirectory() as td:
            hermes_home = Path(td) / ".hermes"
            fake_bin = Path(td) / "bin"
            fake_bin.mkdir()
            codex = fake_bin / "codex"
            codex.write_text("""#!/usr/bin/env python3
import sys
print('OpenAI Codex v0.test')
print('session id: real-wrapper-test')
print('Traceback (most recent call last):')
print('RuntimeError: token=abc123 secret=hide-me')
print('DONE')
print('Hermes learning candidates')
print('- Tool quirk: failed Python command should be captured')
print('- Skill candidate: review Codex summaries')
""", encoding="utf-8")
            codex.chmod(0o755)
            env = {"PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}

            result = run_py(
                PLUGIN / "scripts" / "run_codex_with_learning.py",
                "--hermes-home", str(hermes_home),
                "--review",
                "--", "--cd", str(Path(td)), "prompt",
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = hermes_home / "codex-learning" / "runs" / "real-wrapper-test.summary.json"
            event = hermes_home / "codex-learning" / "events" / "real-wrapper-test.jsonl"
            review = hermes_home / "codex-learning" / "reviews" / "real-wrapper-test.review.md"
            self.assertTrue(summary.exists())
            self.assertTrue(event.exists())
            self.assertTrue(review.exists())
            data = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(data["source"], "run_codex_with_learning")
            self.assertTrue(data["recommended_hermes_review"])
            self.assertIn("runtimeerror", data["failure_events"][0]["markers"])
            self.assertNotIn("hide-me", summary.read_text(encoding="utf-8"))
            self.assertIn("[REDACTED]", summary.read_text(encoding="utf-8"))

    def test_review_codex_learning_writes_quarantined_review_without_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            hermes_home = Path(td) / ".hermes"
            runs = hermes_home / "codex-learning" / "runs"
            runs.mkdir(parents=True)
            (runs / "real.summary.json").write_text(json.dumps({
                "session_id": "real",
                "event_counts": {"PostToolUse": 1, "Stop": 1},
                "failure_events": [{"markers": ["traceback"], "excerpt": "Traceback token=abcd1234 secret=shhh"}],
                "learning_markers": [{"markers": ["remember"]}],
                "recommended_hermes_review": True,
            }), encoding="utf-8")

            result = run_py(
                PLUGIN / "scripts" / "review_codex_learning.py",
                "--hermes-home", str(hermes_home),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            review = hermes_home / "codex-learning" / "reviews" / "real.review.md"
            self.assertTrue(review.exists())
            text = review.read_text(encoding="utf-8")
            self.assertIn("# Codex Learning Review", text)
            self.assertIn("Quarantined observations", text)
            self.assertIn("Skill candidates", text)
            self.assertIn("[REDACTED]", text)
            self.assertNotIn("shhh", text)


if __name__ == "__main__":
    unittest.main()

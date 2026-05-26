#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / ".hermes" / "codex-learning" / "runs"
    files = sorted(root.glob("*.summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print(f"No Codex learning summaries found in {root}")
        return 1
    for path in files[:10]:
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"{path.name}: recommended_review={data.get('recommended_hermes_review')} events={data.get('event_counts')}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

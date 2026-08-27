#!/usr/bin/env python3
"""Run the project's canonical local cipher workbench."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from puzzle_agent.cipher_workbench import CipherWorkbench  # noqa: E402
from puzzle_agent.domain import PuzzleInput  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze text with common puzzle cipher transforms")
    parser.add_argument("text")
    parser.add_argument("--key", action="append", default=[], help="Candidate Vigenere key; repeatable")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    candidates = CipherWorkbench(max_candidates=args.limit).analyze(
        PuzzleInput(content=args.text), tuple(args.key)
    )
    print(json.dumps([asdict(item) for item in candidates], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

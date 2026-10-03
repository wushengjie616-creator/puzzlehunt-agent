from __future__ import annotations

from typing import Any
import json

from .components.sudoku import replay_trace, solve_sudoku


class PaperPuzzleGateway:
    """One explicit dispatch boundary for all paper-puzzle components."""

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "sudoku",
                "name": "普通数独",
                "enabled": True,
                "mode": "solver",
                "description": "裸单与行/列/宫隐单；完整可回放过程",
            },
            {
                "id": "minesweeper",
                "name": "扫雷",
                "enabled": True,
                "mode": "game",
                "description": "本地互动游戏；确定性逻辑提示，不猜雷",
            },
            {"id": "nonogram", "name": "数织", "enabled": False, "description": "路线图"},
            {"id": "kakuro", "name": "数和", "enabled": False, "description": "路线图"},
        ]

    def run(self, envelope: dict[str, Any]) -> dict[str, Any]:
        kind = envelope.get("kind")
        if kind != "sudoku":
            raise ValueError(f"Unsupported paper puzzle component: {kind}")
        return solve_sudoku(envelope.get("canonical"))

    def replay(self, canonical: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
        return replay_trace(canonical, steps)

    def advise_stall(self, result: dict[str, Any], provider) -> dict[str, Any]:
        if result.get("status") != "STALLED":
            raise ValueError("Advisory is only available for a stalled puzzle")
        prompt = {
            "status": result["status"],
            "grid": result["grid"],
            "candidates": result["candidates"],
            "verified_techniques": [
                "naked_single", "hidden_single_row", "hidden_single_column",
                "hidden_single_region",
            ],
        }
        content = provider.complete([{
            "role": "system",
            "content": (
                "Analyze the stalled Sudoku and return JSON with analysis and "
                "suggested_technique. This is advisory only: do not claim or apply assignments."
            ),
        }, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}])
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Sudoku advisory provider returned invalid JSON") from exc
        analysis = parsed.get("analysis")
        technique = parsed.get("suggested_technique")
        if not isinstance(analysis, str) or not analysis.strip():
            raise ValueError("Sudoku advisory requires analysis")
        if not isinstance(technique, str) or not technique.strip():
            raise ValueError("Sudoku advisory requires suggested_technique")
        return {
            "status": "UNVERIFIED_ADVISORY",
            "analysis": analysis.strip(),
            "suggested_technique": technique.strip(),
            "board_fingerprint": result["state_fingerprint"],
        }

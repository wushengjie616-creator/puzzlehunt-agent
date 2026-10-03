from __future__ import annotations

from typing import Any
import json

from .components.sudoku import replay_trace, solve_sudoku
from .components.nonogram import (
    replay_trace as replay_nonogram_trace,
    solve_nonogram,
)
from .components.rule_based import solve_rule_puzzle, synthesize_program


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
            {
                "id": "nonogram",
                "name": "数织",
                "enabled": True,
                "mode": "solver",
                "description": "逐行逐列模式交集；完整可回放过程",
            },
            {
                "id": "rule_puzzle",
                "name": "按规则推理",
                "enabled": True,
                "mode": "method_synthesis_solver",
                "description": "先从题面规则生成受限推理方法，再由确定性引擎执行",
            },
            {"id": "kakuro", "name": "数和", "enabled": False, "description": "路线图"},
        ]

    def run(
        self,
        envelope: dict[str, Any],
        *,
        solve_mode: str = "full",
        provider=None,
    ) -> dict[str, Any]:
        if solve_mode not in {"full", "next_step"}:
            raise ValueError("solve_mode must be full or next_step")
        kind = envelope.get("kind")
        if kind == "sudoku":
            return solve_sudoku(
                envelope.get("canonical"),
                max_steps=1 if solve_mode == "next_step" else None,
            )
        if kind == "nonogram":
            if solve_mode != "full":
                raise ValueError("solve_mode next_step is only supported for sudoku")
            return solve_nonogram(envelope.get("canonical"))
        if kind == "rule_puzzle":
            if provider is None:
                raise ValueError("rule_puzzle requires a method-synthesis provider")
            source = envelope.get("canonical")
            program = synthesize_program(source, provider)
            result = solve_rule_puzzle(
                source, program, max_steps=1 if solve_mode == "next_step" else None,
            )
            result["method_program"] = program
            return result
        raise ValueError(f"Unsupported paper puzzle component: {kind}")

    def replay(
        self,
        canonical: dict[str, Any],
        steps: list[dict[str, Any]],
        *,
        kind: str = "sudoku",
    ) -> dict[str, Any]:
        if kind == "sudoku":
            return replay_trace(canonical, steps)
        if kind == "nonogram":
            return replay_nonogram_trace(canonical, steps)
        raise ValueError(f"Unsupported paper puzzle component: {kind}")

    def advise_stall(
        self, result: dict[str, Any], provider, *, kind: str = "sudoku",
    ) -> dict[str, Any]:
        if result.get("status") != "STALLED":
            raise ValueError("Advisory is only available for a stalled puzzle")
        if kind == "sudoku":
            prompt = {
                "status": result["status"],
                "grid": result["grid"],
                "candidates": result["candidates"],
                "verified_techniques": [
                    "naked_single", "hidden_single_row", "hidden_single_column",
                    "hidden_single_region",
                ],
            }
            puzzle_name = "Sudoku"
        elif kind == "nonogram":
            prompt = {
                "status": result["status"],
                "row_clues": result["row_clues"],
                "column_clues": result["column_clues"],
                "grid": result["grid"],
                "verified_techniques": ["line_pattern_intersection"],
            }
            puzzle_name = "Nonogram"
        else:
            raise ValueError(f"Unsupported paper puzzle component: {kind}")
        content = provider.complete([{
            "role": "system",
            "content": (
                f"Analyze the stalled {puzzle_name} and return JSON with analysis and "
                "suggested_technique. This is advisory only: do not claim or apply cell assignments."
            ),
        }, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}])
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"{puzzle_name} advisory provider returned invalid JSON") from exc
        analysis = parsed.get("analysis")
        technique = parsed.get("suggested_technique")
        if not isinstance(analysis, str) or not analysis.strip():
            raise ValueError(f"{puzzle_name} advisory requires analysis")
        if not isinstance(technique, str) or not technique.strip():
            raise ValueError(f"{puzzle_name} advisory requires suggested_technique")
        return {
            "status": "UNVERIFIED_ADVISORY",
            "analysis": analysis.strip(),
            "suggested_technique": technique.strip(),
            "board_fingerprint": result["state_fingerprint"],
        }

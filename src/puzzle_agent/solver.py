from dataclasses import asdict
import json
from typing import Protocol

from .cipher_workbench import CipherWorkbench
from .domain import PuzzleInput, SolveResult
from .prompt import build_messages


class CompletionProvider(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


class PuzzleSolver:
    def __init__(self, provider: CompletionProvider, workbench: CipherWorkbench | None = None):
        self.provider = provider
        self.workbench = workbench or CipherWorkbench()

    def solve(self, puzzle: PuzzleInput, keys: tuple[str, ...] = ()) -> SolveResult:
        puzzle.validate()
        candidates = self.workbench.analyze(puzzle, keys)
        raw_response = self.provider.complete(build_messages(puzzle, candidates))
        try:
            data = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("Model returned invalid JSON; no retry was attempted") from error
        return SolveResult.from_dict(data)


class OfflineProvider:
    def complete(self, messages: list[dict[str, str]]) -> str:
        user_content = messages[-1]["content"]
        marker = "CIPHER_CANDIDATES_JSON:\n"
        candidates = json.loads(user_content.split(marker, 1)[1]) if marker in user_content else []
        best = next((item for item in candidates if item.get("score", 0) >= 0.7), None)
        result = SolveResult(
            answer=best["output"] if best else None,
            confidence="medium" if best else "low",
            reasoning_summary=(
                f"Offline mode selected the highest-scoring {best['method']} candidate.",
            ) if best else ("Offline mode found no high-quality deterministic candidate.",),
            key_evidence=(best["output"],) if best else (),
            methods_tried=tuple(sorted({item["method"] for item in candidates})),
            missing_information=() if best else ("A language model analysis was not run in offline mode.",),
        )
        return json.dumps(asdict(result), ensure_ascii=False)

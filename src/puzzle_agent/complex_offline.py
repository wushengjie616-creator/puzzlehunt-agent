"""Deterministic staged provider for offline graph demonstrations."""

import json


class OfflineStageProvider:
    def complete(self, messages: list[dict[str, str]]) -> str:
        stage = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        state = json.loads(messages[1]["content"])
        puzzle = state["puzzle"]

        if stage == "OBSERVE_CLASSIFY":
            response = {
                "observations": [
                    {"id": "o-title", "text": puzzle.get("title", ""), "source": "title"},
                    {"id": "o-flavor", "text": puzzle.get("flavor_text", ""), "source": "flavor_text"},
                    {"id": "o-content", "text": puzzle.get("content", ""), "source": "content"},
                ],
                "flavor_associations": [],
            }
        elif stage == "HYPOTHESIZE_PLAN":
            response = {
                "hypotheses": [
                    {"id": "h-cipher", "mechanism": "common cipher or encoding", "confidence": 0.6},
                    {"id": "h-extraction", "mechanism": "positional extraction", "confidence": 0.3},
                ],
                "plan": [{
                    "id": "plan-cipher",
                    "tool": "cipher_workbench",
                    "purpose": "test deterministic common transforms",
                }],
            }
        elif stage == "EVALUATE_EVIDENCE":
            candidates = [
                item for item in state.get("evidence", [])
                if item.get("kind") == "cipher_candidate"
            ]
            best = max(candidates, key=lambda item: item.get("score", 0), default=None)
            response = {
                "evidence_assessment": [{
                    "hypothesis_id": "h-cipher",
                    "effect": "supports" if best else "inconclusive",
                }],
                "answer_candidates": ([{
                    "answer": best["output"],
                    "confidence": "high" if best.get("score", 0) >= 0.8 else "medium",
                    "evidence_ids": [best["id"]],
                }] if best else []),
            }
        elif stage == "VERIFY_ANSWER":
            candidates = state.get("answer_candidates", [])
            best = candidates[0] if candidates else None
            response = {
                "answer": best.get("answer") if best else None,
                "confidence": best.get("confidence", "low") if best else "low",
                "checks": {
                    "format": bool(best and best.get("answer")),
                    "evidence": bool(best and best.get("evidence_ids")),
                },
            }
        else:
            raise ValueError(f"Unsupported offline stage: {stage}")
        return json.dumps(response, ensure_ascii=False)

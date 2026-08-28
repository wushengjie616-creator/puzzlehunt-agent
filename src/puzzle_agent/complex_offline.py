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
                "tensions": [{"id": "t-content", "signal_ids": ["o-content"], "question": "what structure explains the content?"}],
            }
        elif stage == "ASSOCIATE_THEME":
            response = {
                "flavor_associations": [],
                "association_candidates": [
                    {"id": "a-cipher", "ontology": "classical encoding", "bridge": [], "signal_ids": ["o-content"], "prediction": "a bounded transform yields language", "falsifier": "no transform yields language", "confidence": 0.5},
                    {"id": "a-layout", "ontology": "layout", "bridge": [], "signal_ids": ["o-content"], "prediction": "positions carry information", "falsifier": "layout is uniform", "confidence": 0.3},
                    {"id": "a-language", "ontology": "wordplay", "bridge": [], "signal_ids": ["o-content"], "prediction": "surface wording has systematic ambiguity", "falsifier": "wording is literal", "confidence": 0.2},
                ],
            }
        elif stage == "MATERIALIZE_SUBPROBLEMS":
            response = {
                "structure_model": {
                    "kind": "atomic",
                    "unit_count": 1,
                    "grouping_rule": "the complete content is one encoded carrier",
                    "dependencies": [],
                },
                "subproblems": [{
                    "id": "sp-content",
                    "input_excerpt": puzzle.get("content", ""),
                    "signal_ids": ["o-content"],
                    "group": "content",
                    "depends_on": [],
                    "predicted_product": "a decoded word or instruction",
                    "status": "open",
                }],
                "subproblem_results": [],
            }
        elif stage == "VALIDATE_SUBPROBLEMS":
            response = {
                "validated_results": [],
                "contradicted_result_ids": [],
                "needs_test_result_ids": [],
                "unresolved_subproblem_ids": ["sp-content"],
                "issues": ["the offline fixture leaves semantic candidates unresolved"],
            }
        elif stage == "HYPOTHESIZE_PLAN":
            response = {
                "hypotheses": [
                    {"id": "h-cipher", "mechanism": "common cipher or encoding", "association_id": "a-cipher", "prediction": "one candidate is language", "falsifier": "no candidate is language", "confidence": 0.6},
                    {"id": "h-extraction", "mechanism": "positional extraction", "association_id": "a-layout", "prediction": "positions form language", "falsifier": "positions are noise", "confidence": 0.3},
                ],
                "plan": [{
                    "id": "plan-cipher",
                    "tool": "cipher_workbench",
                    "arguments": {},
                    "signal_ids": ["o-content"],
                    "purpose": "test deterministic common transforms",
                    "prediction": "one bounded transform yields language",
                    "falsifier": "no bounded transform yields language",
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
                "intermediate_answers": ([{
                    "value": best["output"],
                    "role": "decoded_carrier",
                    "evidence_ids": [best["id"]],
                }] if best else []),
            }
        elif stage == "VERIFY_INTERMEDIATES":
            intermediates = state.get("intermediate_answers", [])
            response = {
                "validated_intermediates": intermediates,
                "checks": {
                    "evidence_backed": bool(intermediates),
                    "reproducible": bool(intermediates),
                    "distinct_from_final": bool(intermediates),
                    "extraction_ready": bool(intermediates),
                },
                "issues": [] if intermediates else ["no intermediate carrier"],
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
                    "flavor_callback": bool(best),
                    "clue_coverage": bool(best),
                    "all_elements_consumed": bool(best),
                    "independent_derivation": bool(best),
                },
            }
        else:
            raise ValueError(f"Unsupported offline stage: {stage}")
        return json.dumps(response, ensure_ascii=False)

from dataclasses import asdict
import json

from .domain import CipherCandidate, PuzzleInput


def build_messages(puzzle: PuzzleInput, candidates: list[CipherCandidate]) -> list[dict[str, str]]:
    system = """You are a careful puzzle-solving agent. Use the title, flavor text, content, and notes together. Form multiple hypotheses and reject them using evidence. Local cipher candidates may be false positives. Never force an answer: use null when evidence is insufficient. Return only one JSON object with keys answer, confidence, reasoning_summary, key_evidence, methods_tried, alternatives, and missing_information. confidence must be low, medium, or high. Give concise, verifiable reasoning summaries, not hidden chain-of-thought."""
    puzzle_json = json.dumps({
        "title": puzzle.title,
        "flavor_text": puzzle.flavor_text,
        "content": puzzle.content,
        "notes": puzzle.notes,
    }, ensure_ascii=False, indent=2)
    candidates_json = json.dumps([asdict(candidate) for candidate in candidates], ensure_ascii=False, indent=2)
    user = (
        "Solve this puzzle. Preserve the original language of clues and answer in the most appropriate language.\n"
        f"PUZZLE_JSON:\n{puzzle_json}\n"
        f"CIPHER_CANDIDATES_JSON:\n{candidates_json}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

import base64
import binascii
import re

from .domain import CipherCandidate, PuzzleInput


def caesar_decode(text: str, shift: int) -> str:
    shift %= 26
    result: list[str] = []
    for char in text:
        if "A" <= char <= "Z":
            result.append(chr((ord(char) - ord("A") - shift) % 26 + ord("A")))
        elif "a" <= char <= "z":
            result.append(chr((ord(char) - ord("a") - shift) % 26 + ord("a")))
        else:
            result.append(char)
    return "".join(result)


def atbash(text: str) -> str:
    result: list[str] = []
    for char in text:
        if "A" <= char <= "Z":
            result.append(chr(ord("Z") - (ord(char) - ord("A"))))
        elif "a" <= char <= "z":
            result.append(chr(ord("z") - (ord(char) - ord("a"))))
        else:
            result.append(char)
    return "".join(result)


def decode_base(text: str, base: int) -> str | None:
    compact = "".join(text.split())
    try:
        if base == 16:
            raw = base64.b16decode(compact.upper(), casefold=True)
        elif base == 32:
            raw = base64.b32decode(compact.upper() + "=" * (-len(compact) % 8), casefold=True)
        elif base == 64:
            raw = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=True)
        else:
            raise ValueError("base must be 16, 32, or 64")
        return raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


_MORSE = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z", "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7", "---..": "8",
    "----.": "9",
}


def decode_morse(text: str) -> str | None:
    words = re.split(r"\s*/\s*|\s{2,}", text.strip())
    decoded_words: list[str] = []
    for word in words:
        symbols = word.split()
        if not symbols or any(symbol not in _MORSE for symbol in symbols):
            return None
        decoded_words.append("".join(_MORSE[symbol] for symbol in symbols))
    return " ".join(decoded_words)


def decode_a1z26(text: str) -> str | None:
    tokens = re.findall(r"\d+", text)
    if not tokens or re.sub(r"[\d\s,;:/|.\-]+", "", text):
        return None
    numbers = [int(token) for token in tokens]
    if any(number < 1 or number > 26 for number in numbers):
        return None
    return "".join(chr(ord("A") + number - 1) for number in numbers)


def decode_bacon(text: str) -> str | None:
    words = re.split(r"\s*/\s*", text.strip().lower())
    decoded: list[str] = []
    for word in words:
        compact = re.sub(r"\s+", "", word)
        if not compact or set(compact) - {"a", "b"} or len(compact) % 5:
            return None
        letters: list[str] = []
        for index in range(0, len(compact), 5):
            value = int(compact[index:index + 5].replace("a", "0").replace("b", "1"), 2)
            if value >= 26:
                return None
            letters.append(chr(ord("A") + value))
        decoded.append("".join(letters))
    return " ".join(decoded)


def decode_ascii_decimal(text: str) -> str | None:
    if re.search(r"(^|[\s,;|/])-\d", text):
        return None
    if re.sub(r"[\d\s,;:/|.-]+", "", text):
        return None
    tokens = re.findall(r"\d+", text)
    if not tokens:
        return None
    values = [int(token) for token in tokens]
    if any(value < 0 or value > 127 for value in values):
        return None
    return "".join(chr(value) for value in values)


def vigenere_decode(text: str, key: str) -> str:
    clean_key = "".join(char.upper() for char in key if char.isascii() and char.isalpha())
    if not clean_key:
        raise ValueError("Vigenere key must contain letters")
    result: list[str] = []
    key_index = 0
    for char in text:
        if char.isascii() and char.isalpha():
            base = ord("A") if char.isupper() else ord("a")
            shift = ord(clean_key[key_index % len(clean_key)]) - ord("A")
            result.append(chr((ord(char) - base - shift) % 26 + base))
            key_index += 1
        else:
            result.append(char)
    return "".join(result)


def rail_fence_decode(text: str, rails: int) -> str:
    if rails < 2:
        raise ValueError("Rail Fence requires at least two rails")
    if rails >= len(text):
        return text
    pattern = list(range(rails)) + list(range(rails - 2, 0, -1))
    rail_for_position = [pattern[index % len(pattern)] for index in range(len(text))]
    counts = [rail_for_position.count(rail) for rail in range(rails)]
    rows: list[list[str]] = []
    offset = 0
    for count in counts:
        rows.append(list(text[offset:offset + count]))
        offset += count
    positions = [0] * rails
    output: list[str] = []
    for rail in rail_for_position:
        output.append(rows[rail][positions[rail]])
        positions[rail] += 1
    return "".join(output)


def _binary_to_text(text: str) -> str | None:
    compact = re.sub(r"[\s,_-]", "", text)
    if not compact or set(compact) - {"0", "1"} or len(compact) % 8:
        return None
    try:
        return bytes(int(compact[index:index + 8], 2) for index in range(0, len(compact), 8)).decode("utf-8")
    except UnicodeDecodeError:
        return None


def _score_text(text: str) -> float:
    if not text or not all(char.isprintable() or char in "\r\n\t" for char in text):
        return 0.0
    lowered = text.strip().lower()
    score = 0.25
    letters = [char for char in lowered if char.isascii() and char.isalpha()]
    if letters:
        vowel_ratio = sum(char in "aeiou" for char in letters) / len(letters)
        if 0.2 <= vowel_ratio <= 0.6:
            score += 0.15
    common_words = {"hello", "answer", "attackatdawn", "puzzle", "secret", "the", "this"}
    if lowered.replace(" ", "") in common_words:
        score += 0.6
    elif any(word in lowered.split() for word in common_words):
        score += 0.35
    return min(score, 1.0)


class CipherWorkbench:
    def __init__(self, max_candidates: int = 40, max_total_chars: int = 8000):
        self.max_candidates = max_candidates
        self.max_total_chars = max_total_chars

    def analyze(self, puzzle: PuzzleInput, keys: tuple[str, ...] = ()) -> list[CipherCandidate]:
        candidates: list[CipherCandidate] = []
        segments = (
            ("title", puzzle.title),
            ("flavor_text", puzzle.flavor_text),
            ("content", puzzle.content),
            ("notes", puzzle.notes or ""),
        )

        def add(method: str, source: str, output: str | None, parameters=None, warnings=()):
            if output is None or not output or output == source:
                return
            candidates.append(CipherCandidate(
                method=method,
                source_segment=segment_name,
                output=output,
                score=_score_text(output),
                parameters=parameters or {},
                warnings=tuple(warnings),
            ))

        for segment_name, source in segments:
            source = source.strip()
            if not source:
                continue
            for shift in range(1, 26):
                add("caesar", source, caesar_decode(source, shift), {"shift": shift})
            add("atbash", source, atbash(source))
            add("reverse", source, source[::-1])
            for base in (16, 32, 64):
                add(f"base{base}", source, decode_base(source, base))
            add("binary", source, _binary_to_text(source))
            add("morse", source, decode_morse(source))
            add("a1z26", source, decode_a1z26(source))
            add("bacon", source, decode_bacon(source))
            add("ascii_decimal", source, decode_ascii_decimal(source))
            for key in keys:
                try:
                    add("vigenere", source, vigenere_decode(source, key), {"key": key})
                except ValueError:
                    continue
            if len(source) >= 4:
                for rails in range(2, min(5, len(source) - 1) + 1):
                    add("rail_fence", source, rail_fence_decode(source, rails), {"rails": rails})
            lines = [line.strip() for line in source.splitlines() if line.strip()]
            if len(lines) >= 2:
                add("acrostic_first", source, "".join(line[0] for line in lines))
                add("acrostic_last", source, "".join(line[-1] for line in lines))
            add("odd_positions", source, source[::2])
            add("even_positions", source, source[1::2])

        unique: dict[tuple[str, str, str], CipherCandidate] = {}
        for candidate in candidates:
            key = (candidate.method, candidate.source_segment, candidate.output)
            unique.setdefault(key, candidate)
        ordered = sorted(unique.values(), key=lambda item: (-item.score, item.method, item.output))
        selected: list[CipherCandidate] = []
        total_chars = 0
        for candidate in ordered:
            if len(selected) >= self.max_candidates:
                break
            if total_chars + len(candidate.output) > self.max_total_chars:
                continue
            selected.append(candidate)
            total_chars += len(candidate.output)
        return selected

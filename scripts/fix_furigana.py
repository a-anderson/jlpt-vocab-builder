"""Fix incorrect bracket-notation furigana in a single-column CSV."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ollama as ollama_client

DATA_DIR = Path('data')
KANA_RE = re.compile(r'[぀-ヿ]')
_KANJI = r'[一-鿿々]'  # includes iteration mark 々
KANJI_RE = re.compile(_KANJI)
# Matches a kanji not followed by another kanji or '[' — i.e. the last kanji in a compound run
_TERMINAL_KANJI_RE = re.compile(_KANJI + r'(?!' + _KANJI + r'|\[)')


def _chat(model: str, prompt: str) -> str:
    response = ollama_client.chat(
        model=model,
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.1},
    )
    return response.message.content.strip()


def strip_brackets(word: str) -> str:
    return re.sub(r'\[[^\]]*\]', '', word)


def needs_fix(word: str) -> bool:
    """Return True if bracket notation is invalid.

    Valid notation: every "terminal" kanji (not followed by another kanji) must be
    immediately followed by a non-empty kana bracket. A non-terminal kanji (part of
    a compound run) is covered by the bracket on the last kanji in the run.
    e.g. 今朝[けさ] and 火[か]曜[よう]日[び] are both valid.
    """
    if not KANJI_RE.search(word):
        return False
    # Terminal kanji not followed by bracket
    if _TERMINAL_KANJI_RE.search(word):
        return True
    # Bracket immediately after kana (invalid placement)
    if re.search(r'[぀-ヿ]\[', word):
        return True
    # Empty or non-kana bracket
    for m in re.finditer(r'\[([^\]]*)\]', word):
        r = m.group(1)
        if not r or re.search(r'[^぀-ヿ]', r):
            return True
    return False


def reading_from_notation(word: str) -> str:
    """Extract the full reading from valid bracket notation.

    For each kana character: add it.
    For each kanji run followed by [bracket]: add the bracket content.
    """
    reading = ''
    i = 0
    while i < len(word):
        c = word[i]
        if c == '[':
            end = word.index(']', i)
            reading += word[i + 1:end]
            i = end + 1
        elif KANA_RE.match(c):
            reading += c
            i += 1
        else:
            i += 1
    return reading


def build_reading_index(directory: Path = DATA_DIR / 'jitendex-yomitan') -> dict[str, str]:
    """Build term → reading from Jitendex, keeping highest-popularity entry."""
    index: dict[str, tuple[str, int]] = {}
    for path in sorted(directory.glob('term_bank_*.json')):
        with open(path, encoding='utf-8') as f:
            entries = json.load(f)
        for entry in entries:
            term, reading, pop = entry[0], entry[1], (entry[4] if len(entry) > 4 else 0)
            if term not in index or index[term][1] < pop:
                index[term] = (reading, pop)
    return {t: v[0] for t, v in index.items()}


def fix_word(plain: str, reading: str, model: str) -> str | None:
    """Ask model to produce correct bracket notation. Returns None if output is invalid."""
    prompt = (
        f"The Japanese word is '{plain}' and its reading is '{reading}'.\n"
        f"Rewrite it with furigana bracket notation using these rules:\n"
        f"- Normally put the reading for each kanji immediately after it: 火[か]曜[よう]日[び]\n"
        f"- If the word has an irregular/ateji reading that cannot be split per-kanji, "
        f"put one bracket after the last kanji covering all of them: 今朝[けさ]\n"
        f"- Never bracket hiragana or katakana characters.\n"
        f"Return ONLY the word with brackets, nothing else."
    )
    result = _chat(model, prompt).strip()

    if strip_brackets(result) != plain:
        return None
    # All brackets must contain kana only
    for m in re.finditer(r'\[([^\]]*)\]', result):
        if not m.group(1) or re.search(r'[^぀-ヿ]', m.group(1)):
            return None
    # Reading from model output must match known reading.
    # We compare bracket-content sum only (ignoring bare kana prefix/suffix)
    # to handle honorific お/ご prefixes that appear in both bare kana and in compound brackets.
    brackets_reading = ''.join(m.group(1) for m in re.finditer(r'\[([^\]]+)\]', result))
    bare_kana_in_plain = ''.join(c for c in plain if KANA_RE.match(c))
    # The bracket sum should equal reading minus leading bare kana from plain
    expected = reading
    for c in bare_kana_in_plain:
        if expected.startswith(c):
            expected = expected[len(c):]
    if brackets_reading != expected and brackets_reading != reading:
        return None
    return result


def process_lines(lines: list[str], reading_index: dict[str, str], model: str) -> tuple[list[str], int]:
    """Process lines of bracket-notation words; return (fixed_lines, change_count)."""
    fixed_lines = []
    changed = 0

    for line in lines:
        word = line.rstrip(',')
        suffix = ',' if line.endswith(',') else ''

        if word.startswith('#') or not needs_fix(word):
            fixed_lines.append(line)
            continue

        plain = strip_brackets(word)
        known_reading = reading_index.get(plain) or reading_from_notation(word)

        if not known_reading:
            print(f"  SKIP: {word!r}")
            fixed_lines.append(line)
            continue

        result = fix_word(plain, known_reading, model)

        if result is None:
            # Fallback: bracket whole compound (put one bracket after last kanji)
            last_kanji = max(i for i, c in enumerate(plain) if KANJI_RE.match(c))
            result = plain[:last_kanji + 1] + f'[{known_reading}]' + plain[last_kanji + 1:]
            print(f"  FALLBACK {word!r} → {result!r}")
        else:
            print(f"  {word!r} → {result!r}")

        if result != word:
            changed += 1
        fixed_lines.append(result + suffix)

    return fixed_lines, changed


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True, help='Text or csv file with one word per line; lines starting with # are ignored')
    parser.add_argument('--model', required=True, help='Ollama model name')
    args = parser.parse_args()

    print('Loading Jitendex reading index...')
    reading_index = build_reading_index()

    input_path = Path(args.file)
    lines = input_path.read_text(encoding='utf-8').splitlines()
    fixed_lines, changed = process_lines(lines, reading_index, args.model)

    input_path.write_text('\n'.join(fixed_lines), encoding='utf-8')
    print(f"\nDone. {changed} words fixed in {input_path}")


if __name__ == '__main__':
    main()

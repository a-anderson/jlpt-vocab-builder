"""Build a JLPT N4–N1 vocabulary CSV for Anki import.

Usage:
  python build_jlpt_csv.py --model gemma4:e4b
  python build_jlpt_csv.py --model gemma4:e4b --levels n4 n3
  python build_jlpt_csv.py --model gemma4:e4b --resume
"""

import argparse
import csv
import json
import re
from pathlib import Path

import fugashi
import requests
from tqdm import tqdm

from dictionary import build_french_index, build_jitendex_index
from furigana import bracket_to_ruby, normalise_furigana
from normalise import normalise_word
from pitch_accent import get_pitch_columns, plain_kana

try:
    import ollama as ollama_client
except ImportError:
    ollama_client = None

LEVELS = ['n4', 'n3', 'n2', 'n1']
CHADMURO_URL = 'https://raw.githubusercontent.com/chadmuro/jlpt-vocab/main/data/{level}/vocabulary.ts'
JITENDEX_DIR = Path('jitendex-yomitan')
FRENCH_DIR = Path('JMdict_french')
OUTPUT_CSV = Path('jlpt_vocab.csv')

CSV_COLUMNS = [
    '単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図',
    '英語訳', '仏語訳', '例文', '例文振り仮名', '英語例文', '仏語例文',
    '日本語ターゲット', 'レベル',
]


# ---------------------------------------------------------------------------
# Stage 1: Word list
# ---------------------------------------------------------------------------

def fetch_chadmuro_words(level: str) -> list[dict]:
    """Fetch and parse a chadmuro vocabulary.ts file for the given JLPT level."""
    resp = requests.get(CHADMURO_URL.format(level=level), timeout=30)
    resp.raise_for_status()
    words = []
    for entry in re.findall(r'\{[^}]+\}', resp.text, re.DOTALL):
        kanji = _ts_field(entry, 'kanji')
        if not kanji:
            continue
        words.append({
            '単語': kanji.strip(),
            '振り仮名_raw': (_ts_field(entry, 'japanese') or kanji).strip(),
            '英語訳_raw': (_ts_field(entry, 'english') or '').strip(),
            'レベル': level.upper(),
        })
    return words


def _ts_field(entry: str, field: str) -> str | None:
    m = re.search(field + r':\s*"([^"]+)"', entry)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Stage 2: Morphological analysis (fugashi)
# ---------------------------------------------------------------------------

_tagger: fugashi.Tagger | None = None


def _get_tagger() -> fugashi.Tagger:
    global _tagger
    if _tagger is None:
        _tagger = fugashi.Tagger()
    return _tagger


def word_in_sentence(word: str, sentence: str) -> bool:
    """Return True only if word appears as a distinct morphological token."""
    if not sentence:
        return False
    try:
        for token in _get_tagger()(sentence):
            lemma = token.feature.lemma or token.surface
            if lemma == word or token.surface == word:
                return True
    except Exception:
        pass
    return False


def extract_target(word: str, sentence: str) -> str:
    """Find the surface form of word as it appears in sentence."""
    if not sentence:
        return ''
    try:
        for token in _get_tagger()(sentence):
            lemma = token.feature.lemma or token.surface
            if lemma == word or token.surface == word:
                return token.surface
    except Exception:
        pass
    return word if word in sentence else ''


# ---------------------------------------------------------------------------
# Stage 3: Ollama generation
# ---------------------------------------------------------------------------

def _ollama_chat(model: str, prompt: str) -> str:
    response = ollama_client.chat(
        model=model,
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.3},
    )
    return response.message.content.strip()


def _parse_json(raw: str) -> dict:
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE)
    return json.loads(raw.strip())


def ollama_generate(
    word: str,
    model: str,
    en_gloss: str,
    pos: str,
    need_sentence: bool,
    existing_jp: str = '',
    existing_en: str = '',
    need_french_gloss: bool = False,
) -> dict:
    """Call Ollama to generate or complete sentence data for a word."""
    if ollama_client is None:
        return _empty_ollama()

    french_word_line = '  "仏語訳": "<French translation(s) of the word, semicolon-separated if multiple>",\n' if need_french_gloss else ''

    if need_sentence:
        prompt = f"""You are creating Japanese language study materials for a JLPT learner.

Target word: {word}
Part of speech: {pos}
English meaning: {en_gloss}

Write ONE example sentence that:
- Uses {word} naturally in a way that clearly illustrates its meaning and typical usage
- Is appropriately complex for a learner studying this word

Rules for 例文振り仮名:
- Reproduce the sentence exactly, adding <ruby>kanji<rt>reading</rt></ruby> tags
- Add furigana ONLY on kanji — never on hiragana, katakana, or punctuation
- Do NOT wrap katakana words in ruby tags

Respond ONLY with a JSON object, no markdown, no explanation:
{{
  "例文": "<sentence in natural Japanese>",
  "例文振り仮名": "<sentence with ruby tags on kanji only>",
  "英語例文": "<natural English translation>",
  "仏語例文": "<natural French translation>",
{french_word_line}  "日本語ターゲット": "<surface form of {word} as it appears in the sentence>"
}}"""
    else:
        prompt = f"""You are creating Japanese language study materials for a JLPT learner.

Target word: {word}
Part of speech: {pos}
Japanese sentence: {existing_jp}
English translation: {existing_en}

Rules for 例文振り仮名:
- Reproduce the sentence exactly, adding <ruby>kanji<rt>reading</rt></ruby> tags
- Add furigana ONLY on kanji — never on hiragana, katakana, or punctuation
- Do NOT wrap katakana words in ruby tags

Respond ONLY with a JSON object, no markdown, no explanation:
{{
  "仏語例文": "<natural French translation of the Japanese sentence>",
  "例文振り仮名": "<sentence with ruby tags on kanji only>",
{french_word_line}  "日本語ターゲット": "<surface form of {word} as it appears in the sentence>"
}}"""

    try:
        result = _parse_json(_ollama_chat(model, prompt))
        if result.get('例文振り仮名'):
            result['例文振り仮名'] = normalise_furigana(result['例文振り仮名'])
        return result
    except Exception as e:
        print(f'  [Ollama error for {word}]: {e}')
        return _empty_ollama()


def _empty_ollama() -> dict:
    return {'例文': '', '英語例文': '', '仏語例文': '', '例文振り仮名': '', '日本語ターゲット': '', '仏語訳': ''}


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def load_checkpoint(checkpoint_path: Path) -> set[str]:
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            return set(json.load(f))
    return set()


def save_checkpoint(done: set[str], checkpoint_path: Path) -> None:
    with open(checkpoint_path, 'w') as f:
        json.dump(list(done), f)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description='Build JLPT vocabulary CSV')
    parser.add_argument('--model', required=True, help='Ollama model name, e.g. gemma4:e4b')
    parser.add_argument('--levels', nargs='+', default=LEVELS, choices=LEVELS)
    parser.add_argument('--resume', action='store_true', help='Skip already-processed words')
    parser.add_argument('--output', default=str(OUTPUT_CSV))
    args = parser.parse_args()

    output_path = Path(args.output)
    checkpoint_path = output_path.with_name(output_path.stem + '_checkpoint.json')
    done = load_checkpoint(checkpoint_path) if args.resume else set()

    print('Fetching word lists...')
    all_words: list[dict] = []
    for level in args.levels:
        words = fetch_chadmuro_words(level)
        print(f'  {level.upper()}: {len(words)} words')
        all_words.extend(words)

    seen: set[str] = set()
    unique_words = []
    for w in all_words:
        if w['単語'] not in seen:
            seen.add(w['単語'])
            unique_words.append(w)
    print(f'Total unique words: {len(unique_words)}')

    print('Building dictionary indexes...')
    jitendex = build_jitendex_index(JITENDEX_DIR)
    french = build_french_index(FRENCH_DIR)
    print(f'  Jitendex: {len(jitendex)} entries, JMdict French: {len(french)} entries')

    mode = 'a' if (output_path.exists() and args.resume) else 'w'
    with open(output_path, mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS)
        if mode == 'w':
            writer.writeheader()

        for entry in tqdm(unique_words, desc='Processing words'):
            word = entry['単語']
            if args.resume and word in done:
                continue

            振り仮名 = bracket_to_ruby(entry['振り仮名_raw'])
            norm = normalise_word(word)
            lookup_forms = norm['lookup_forms']
            inferred_pos = norm['inferred_pos']

            jm = next((jitendex[f] for f in lookup_forms if f in jitendex), {})
            品詞 = jm.get('品詞', '') or inferred_pos
            英語訳 = jm.get('英語訳', '') or entry.get('英語訳_raw', '')
            例文 = jm.get('例文', '')
            英語例文 = jm.get('英語例文', '')
            例文振り仮名 = jm.get('例文振り仮名', '')

            仏語訳 = next((french[f] for f in lookup_forms if f in french), '')
            need_french_gloss = not bool(仏語訳) and bool(英語訳)

            # Verify Jitendex sentence contains the word as a real morphological token
            if 例文 and not word_in_sentence(lookup_forms[0], 例文):
                例文 = ''
                英語例文 = ''
                例文振り仮名 = ''

            if 例文:
                # Furigana already extracted from Jitendex; only call Ollama for FR + target
                ollama_data = ollama_generate(
                    word, args.model, 英語訳, 品詞,
                    need_sentence=False, existing_jp=例文, existing_en=英語例文,
                    need_french_gloss=need_french_gloss,
                )
                if need_french_gloss:
                    仏語訳 = ollama_data.get('仏語訳', '')
                仏語例文 = ollama_data.get('仏語例文', '')
                日本語ターゲット = ollama_data.get('日本語ターゲット', '') or extract_target(lookup_forms[0], 例文)
                if not 例文振り仮名:
                    例文振り仮名 = ollama_data.get('例文振り仮名', '')
            else:
                ollama_data = ollama_generate(
                    word, args.model, 英語訳, 品詞,
                    need_sentence=True,
                    need_french_gloss=need_french_gloss,
                )
                if need_french_gloss:
                    仏語訳 = ollama_data.get('仏語訳', '')
                例文 = ollama_data.get('例文', '')
                英語例文 = ollama_data.get('英語例文', '')
                仏語例文 = ollama_data.get('仏語例文', '')
                例文振り仮名 = ollama_data.get('例文振り仮名', '')
                日本語ターゲット = ollama_data.get('日本語ターゲット', '') or extract_target(lookup_forms[0], 例文)

            reading = plain_kana(entry['振り仮名_raw'])
            pitch_cols = get_pitch_columns(lookup_forms[0], reading)

            writer.writerow({k: v.replace('\x00', '') for k, v in {
                '単語': word,
                '振り仮名': 振り仮名,
                '品詞': 品詞,
                'ピッチアクセント': pitch_cols['ピッチアクセント'],
                'ピッチアクセント図': pitch_cols['ピッチアクセント図'],
                '英語訳': 英語訳,
                '仏語訳': 仏語訳,
                '例文': 例文,
                '例文振り仮名': 例文振り仮名,
                '英語例文': 英語例文,
                '仏語例文': 仏語例文,
                '日本語ターゲット': 日本語ターゲット,
                'レベル': entry['レベル'],
            }.items()})
            csvfile.flush()
            done.add(word)
            save_checkpoint(done, checkpoint_path)

    print(f'\nDone. {len(done)} rows → {output_path}')


if __name__ == '__main__':
    main()

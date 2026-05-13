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

from dictionary import build_jitendex_index, build_jmdict_index
from drop_words import drop_from_csv, drop_from_checkpoint, load_checkpoint, save_checkpoint
from furigana import bracket_to_ruby, normalise_furigana
from normalise import normalise_word
from pitch_accent import get_pitch_columns, plain_kana

try:
    import ollama as ollama_client
except ImportError:
    ollama_client = None

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

LEVELS = ['n4', 'n3', 'n2', 'n1']
CHADMURO_URL = 'https://raw.githubusercontent.com/chadmuro/jlpt-vocab/main/data/{level}/vocabulary.ts'
DATA_DIR = Path('data')
JITENDEX_DIR = DATA_DIR / 'jitendex-yomitan'
OUTPUT_CSV = Path('jlpt_vocab.csv')

LANGUAGES: dict[str, tuple[str, str]] = {
    'french':  ('仏', 'JMdict_french'),
    'spanish': ('西', 'JMdict_spanish'),
    'german':  ('独', 'JMdict_german'),
    'dutch':   ('蘭', 'JMdict_dutch'),
    'russian': ('露', 'JMdict_russian'),
    'swedish': ('瑞', 'JMdict_swedish'),
}


def make_csv_columns(langs: list[str]) -> list[str]:
    """Build the ordered column list for the given language selection."""
    cols = ['単語', '振り仮名', '品詞', 'ピッチアクセント', 'ピッチアクセント図', '英語訳']
    for lang in langs:
        cols.append(f'{LANGUAGES[lang][0]}語訳')
    cols += ['例文', '例文振り仮名', '英語例文']
    for lang in langs:
        cols.append(f'{LANGUAGES[lang][0]}語例文')
    cols += ['日本語ターゲット', 'レベル']
    return cols


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
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if repair_json is not None:
            return json.loads(repair_json(raw))
        raise


def ollama_generate(
    word: str,
    model: str,
    en_gloss: str,
    pos: str,
    need_sentence: bool,
    existing_jp: str = '',
    existing_en: str = '',
    langs: list[str] | None = None,
    need_gloss_for: list[str] | None = None,
) -> dict:
    """Call Ollama to generate or complete sentence data for a word."""
    if ollama_client is None:
        return _empty_ollama(langs)

    langs = langs or []
    need_gloss_for = need_gloss_for or []

    gloss_lines = ''.join(
        f'  "{LANGUAGES[l][0]}語訳": "<{l.capitalize()} translation(s) of the word, semicolon-separated if multiple>",\n'
        for l in need_gloss_for
    )

    if need_sentence:
        sentence_lang_lines = ''.join(
            f'  "{LANGUAGES[l][0]}語例文": "<natural {l.capitalize()} translation>",\n'
            for l in langs
        )
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
{sentence_lang_lines}{gloss_lines}  "日本語ターゲット": "<surface form of {word} as it appears in the sentence>"
}}"""
    else:
        sentence_lang_lines = ''.join(
            f'  "{LANGUAGES[l][0]}語例文": "<natural {l.capitalize()} translation of the Japanese sentence>",\n'
            for l in langs
        )
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
  "例文振り仮名": "<sentence with ruby tags on kanji only>",
{sentence_lang_lines}{gloss_lines}  "日本語ターゲット": "<surface form of {word} as it appears in the sentence>"
}}"""

    for _ in range(2):
        try:
            result = _parse_json(_ollama_chat(model, prompt))
            if result.get('例文振り仮名'):
                result['例文振り仮名'] = normalise_furigana(result['例文振り仮名'])
            return result
        except Exception as e:
            last_error = e
    print(f'  [Ollama error for {word}]: {last_error}')
    return _empty_ollama(langs)


def ollama_generate_furigana(word: str, reading: str, model: str) -> str:
    """Ask Ollama for per-character ruby HTML for a mixed kanji+kana word."""
    if ollama_client is None:
        return ''
    prompt = f"""Convert the Japanese word to bracket-notation furigana.
Word: {word}
Reading: {reading}

Rules:
- Only add readings on kanji characters, never on hiragana
- Format: kanji[reading] for each kanji group, e.g. 食[た]べる

Respond with ONLY the bracket-notation string, nothing else."""
    for _ in range(2):
        try:
            raw = _ollama_chat(model, prompt).strip()
            return bracket_to_ruby(raw)
        except Exception:
            pass
    return ''


def _empty_ollama(langs: list[str] | None = None) -> dict:
    base = {'例文': '', '英語例文': '', '例文振り仮名': '', '日本語ターゲット': ''}
    for lang in (langs or []):
        abbrev = LANGUAGES[lang][0]
        base[f'{abbrev}語訳'] = ''
        base[f'{abbrev}語例文'] = ''
    return base


# ---------------------------------------------------------------------------
# Repair helpers
# ---------------------------------------------------------------------------

def find_repair_candidates(csv_path: Path, repair_cols: list[str]) -> set[str]:
    """Return words that have at least one empty value in repair_cols."""
    if not csv_path.exists():
        return set()
    candidates = set()
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if any(not row.get(col, '').strip() for col in repair_cols if col in row):
                candidates.add(row['単語'])
    return candidates


def detect_csv_languages(csv_path: Path) -> list[str]:
    """Return language keys present in the CSV header, in LANGUAGES order."""
    if not csv_path.exists():
        return []
    with open(csv_path, newline='', encoding='utf-8') as f:
        fieldnames = csv.DictReader(f).fieldnames or []
    return [lang for lang in LANGUAGES if f'{LANGUAGES[lang][0]}語訳' in fieldnames]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description='Build JLPT vocabulary CSV')
    parser.add_argument('--model', required=True, help='Ollama model name, e.g. gemma4:e4b')
    parser.add_argument('--levels', nargs='+', default=LEVELS, choices=LEVELS)
    parser.add_argument('--resume', action='store_true', help='Skip already-processed words')
    parser.add_argument('--output', default=str(OUTPUT_CSV))
    parser.add_argument(
        '--languages', nargs='+', default=['french'],
        choices=list(LANGUAGES.keys()),
        help='Languages to include (default: french)',
    )
    parser.add_argument('--repair', action='store_true',
                        help='Find rows with empty Ollama-generated fields and reprocess them')
    args = parser.parse_args()

    output_path = Path(args.output)
    checkpoint_path = output_path.with_name(output_path.stem + '_checkpoint.json')
    done = load_checkpoint(checkpoint_path) if (args.resume or args.repair) else set()

    if args.repair:
        # Infer languages from the CSV header rather than requiring --languages.
        # This prevents silently checking the wrong columns if the user forgets to
        # pass --languages when their CSV has multiple languages.
        effective_langs = detect_csv_languages(output_path) or args.languages
        repair_cols = ['例文振り仮名', '日本語ターゲット', '例文'] + [
            f'{LANGUAGES[l][0]}語例文' for l in effective_langs
        ]
        candidates = find_repair_candidates(output_path, repair_cols)
        if candidates:
            print(f'Repairing {len(candidates)} incomplete rows...')
            drop_from_csv(output_path, candidates)
            drop_from_checkpoint(checkpoint_path, candidates)
            done -= candidates
        args.resume = True
        args.languages = effective_langs

    from download import ensure_all
    ensure_all(args.languages)

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
    lang_indexes: dict[str, dict[str, str]] = {
        lang: build_jmdict_index(DATA_DIR / dir_name)
        for lang, (_, dir_name) in LANGUAGES.items()
        if lang in args.languages
    }
    print(f'  Jitendex: {len(jitendex)} entries')

    csv_columns = make_csv_columns(args.languages)
    mode = 'a' if (output_path.exists() and args.resume) else 'w'
    with open(output_path, mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
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

            lang_glosses: dict[str, str] = {}
            need_gloss_for: list[str] = []
            for lang in args.languages:
                abbrev = LANGUAGES[lang][0]
                gloss = next((lang_indexes[lang][f] for f in lookup_forms if f in lang_indexes[lang]), '')
                lang_glosses[f'{abbrev}語訳'] = gloss
                if not gloss and 英語訳:
                    need_gloss_for.append(lang)

            # Verify Jitendex sentence contains the word as a real morphological token
            if 例文 and not word_in_sentence(lookup_forms[0], 例文):
                例文 = ''
                英語例文 = ''
                例文振り仮名 = ''

            if 例文:
                ollama_data = ollama_generate(
                    word, args.model, 英語訳, 品詞,
                    need_sentence=False, existing_jp=例文, existing_en=英語例文,
                    langs=args.languages, need_gloss_for=need_gloss_for,
                )
            else:
                ollama_data = ollama_generate(
                    word, args.model, 英語訳, 品詞,
                    need_sentence=True,
                    langs=args.languages, need_gloss_for=need_gloss_for,
                )

            for lang in need_gloss_for:
                abbrev = LANGUAGES[lang][0]
                lang_glosses[f'{abbrev}語訳'] = ollama_data.get(f'{abbrev}語訳', '')

            lang_examples: dict[str, str] = {
                f'{LANGUAGES[l][0]}語例文': ollama_data.get(f'{LANGUAGES[l][0]}語例文', '')
                for l in args.languages
            }

            if not 例文:
                例文 = ollama_data.get('例文', '')
                英語例文 = ollama_data.get('英語例文', '')
                例文振り仮名 = ollama_data.get('例文振り仮名', '')
            elif not 例文振り仮名:
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
                **lang_glosses,
                '例文': 例文,
                '例文振り仮名': 例文振り仮名,
                '英語例文': 英語例文,
                **lang_examples,
                '日本語ターゲット': 日本語ターゲット,
                'レベル': entry['レベル'],
            }.items()})
            csvfile.flush()
            done.add(word)
            save_checkpoint(done, checkpoint_path)

    end_repair_cols = ['例文振り仮名', '日本語ターゲット', '例文'] + [
        f'{LANGUAGES[l][0]}語例文' for l in args.languages
    ]
    incomplete = find_repair_candidates(output_path, end_repair_cols)
    if incomplete:
        print(f'\nWarning: {len(incomplete)} rows have empty fields. Re-run with --repair to fix them.')

    print(f'\nDone. {len(done)} rows → {output_path}')


if __name__ == '__main__':
    main()

"""Core pipeline functions: constants, word fetching, Ollama generation, repair helpers."""

import csv
import json
import re
from pathlib import Path

import fugashi
import requests

from jlpt_vocab.furigana import bracket_to_ruby, normalise_furigana
from jlpt_vocab.normalise import normalise_word

try:
    import ollama as ollama_client
except ImportError:
    ollama_client = None

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

LEVELS = ['n4', 'n3', 'n2', 'n1']
# Fetched on every run (not cached to disk), so lives here rather than download.py.
CHADMURO_URL = 'https://raw.githubusercontent.com/chadmuro/jlpt-vocab/main/data/{level}/vocabulary.ts'
DATA_DIR = Path('data')
JITENDEX_DIR = DATA_DIR / 'jitendex-yomitan'
OUTPUT_CSV = Path('output/jlpt_vocab.csv')

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
        # Some counters repeat the kanji once per reading: "～杯、～杯、～杯" → "～杯"
        kanji = '、'.join(dict.fromkeys(kanji.split('、')))
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

# not thread-safe; this tool is single-process only
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
# Word processing (shared core used by build.py and add_words.py)
# ---------------------------------------------------------------------------

def process_word(
    word: str,
    model: str,
    jitendex: dict,
    lang_indexes: dict[str, dict],
    langs: list[str],
    en_gloss_fallback: str = '',
) -> tuple[dict, list[str], str]:
    """Resolve dictionary data and run Ollama for a single word.

    Returns (content, lookup_forms, jitendex_reading) where content contains
    only CSV column fields and the other two values are for caller use (pitch
    lookup, furigana generation).
    """
    norm = normalise_word(word)
    lookup_forms = norm['lookup_forms']
    inferred_pos = norm['inferred_pos']

    jm = next((jitendex[f] for f in lookup_forms if f in jitendex), {})
    品詞 = jm.get('品詞', '') or inferred_pos
    英語訳 = jm.get('英語訳', '') or en_gloss_fallback
    例文 = jm.get('例文', '')
    英語例文 = jm.get('英語例文', '')
    例文振り仮名 = jm.get('例文振り仮名', '')

    if 例文 and not word_in_sentence(lookup_forms[0], 例文):
        例文 = 英語例文 = 例文振り仮名 = ''

    lang_glosses: dict[str, str] = {}
    need_gloss_for: list[str] = []
    for lang in langs:
        abbrev = LANGUAGES[lang][0]
        gloss = next((lang_indexes[lang][fm] for fm in lookup_forms if fm in lang_indexes[lang]), '')
        lang_glosses[f'{abbrev}語訳'] = gloss
        if not gloss and 英語訳:
            need_gloss_for.append(lang)

    if 例文:
        ollama_data = ollama_generate(
            word, model, 英語訳, 品詞,
            need_sentence=False, existing_jp=例文, existing_en=英語例文,
            langs=langs, need_gloss_for=need_gloss_for,
        )
    else:
        ollama_data = ollama_generate(
            word, model, 英語訳, 品詞,
            need_sentence=True, langs=langs, need_gloss_for=need_gloss_for,
        )

    for lang in need_gloss_for:
        abbrev = LANGUAGES[lang][0]
        lang_glosses[f'{abbrev}語訳'] = ollama_data.get(f'{abbrev}語訳', '')

    lang_examples = {
        f'{LANGUAGES[l][0]}語例文': ollama_data.get(f'{LANGUAGES[l][0]}語例文', '')
        for l in langs
    }

    if not 例文:
        例文 = ollama_data.get('例文', '')
        英語例文 = ollama_data.get('英語例文', '')
        例文振り仮名 = ollama_data.get('例文振り仮名', '')
    elif not 例文振り仮名:
        例文振り仮名 = ollama_data.get('例文振り仮名', '')

    日本語ターゲット = ollama_data.get('日本語ターゲット', '') or extract_target(lookup_forms[0], 例文)

    content = {
        '品詞': 品詞,
        '英語訳': 英語訳,
        **lang_glosses,
        '例文': 例文,
        '例文振り仮名': 例文振り仮名,
        '英語例文': 英語例文,
        **lang_examples,
        '日本語ターゲット': 日本語ターゲット,
    }
    return content, lookup_forms, jm.get('読み', '')


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
            if any(not (row.get(col) or '').strip() for col in repair_cols if col in row):
                candidates.add(row['単語'])
    return candidates


def detect_csv_languages(csv_path: Path) -> list[str]:
    """Return language keys present in the CSV header, in LANGUAGES order."""
    if not csv_path.exists():
        return []
    with open(csv_path, newline='', encoding='utf-8') as f:
        fieldnames = csv.DictReader(f).fieldnames or []
    return [lang for lang in LANGUAGES if f'{LANGUAGES[lang][0]}語訳' in fieldnames]

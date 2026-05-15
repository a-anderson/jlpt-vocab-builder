"""Jitendex and JMdict French index builders."""

import json
from pathlib import Path

# POS codes checked in priority order (vt before vi to avoid substring collisions)
_POS_MAP = [
    ('vt',    '他動詞'),
    ('vi',    '自動詞'),
    ('v1',    '一段動詞'),
    ('v5u',   '五段動詞（う）'),
    ('v5k-s', '五段動詞（く）'),
    ('v5k',   '五段動詞（く）'),
    ('v5g',   '五段動詞（ぐ）'),
    ('v5s',   '五段動詞（す）'),
    ('v5t',   '五段動詞（つ）'),
    ('v5n',   '五段動詞（ぬ）'),
    ('v5b',   '五段動詞（ぶ）'),
    ('v5m',   '五段動詞（む）'),
    ('v5r',   '五段動詞（る）'),
    ('vk',    'カ変動詞'),
    ('vs-i',  'サ変動詞（する）'),
    ('adj-i',  'い形容詞'),
    ('adj-na', 'な形容詞'),
    ('adj-no', 'の形容詞'),
    ('n',    '名詞'),
    ('adv',  '副詞'),
    ('prt',  '助詞'),
    ('conj', '接続詞'),
    ('pn',   '代名詞'),
    ('int',  '感動詞'),
    ('exp',  '表現'),
    ('suf',  '接尾語'),
    ('pref', '接頭語'),
]

_SKIP_CONTENT = frozenset({
    'extra-info', 'attribution', 'xref', 'xref-content', 'xref-glossary',
    'info-gloss', 'refGlosses', 'references', 'notes', 'formsTable',
})


# ---------------------------------------------------------------------------
# Structured content traversal helpers
# ---------------------------------------------------------------------------

def _text(node, skip_tags: frozenset = frozenset()) -> str:
    """Recursively extract plain text from a Jitendex content node."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return ''.join(_text(n, skip_tags) for n in node)
    if isinstance(node, dict):
        if node.get('tag') in skip_tags:
            return ''
        return _text(node.get('content', ''), skip_tags)
    return ''


def _find_pos_codes(node) -> list[str]:
    """Collect JMDict POS codes from part-of-speech-info span nodes."""
    if isinstance(node, list):
        return [c for item in node for c in _find_pos_codes(item)]
    if not isinstance(node, dict):
        return []
    data = node.get('data', {})
    if data.get('content') == 'part-of-speech-info':
        code = data.get('code', '')
        return [code] if code else []
    return _find_pos_codes(node.get('content', []))


def _find_glosses(node) -> list[str]:
    """Collect gloss strings from glossary ul nodes, skipping non-gloss content."""
    if isinstance(node, list):
        return [g for item in node for g in _find_glosses(item)]
    if not isinstance(node, dict):
        return []
    data_content = node.get('data', {}).get('content', '')
    if data_content in _SKIP_CONTENT:
        return []
    if node.get('tag') == 'ul' and data_content == 'glossary':
        items = node.get('content', [])
        if isinstance(items, dict):
            items = [items]
        return [t for li in items if (t := _text(li).strip())]
    return _find_glosses(node.get('content', []))


def _ruby_html(node) -> str:
    """Convert a Jitendex content node to HTML ruby string.

    ruby nodes become <ruby>base<rt>reading</rt></ruby>.
    rt nodes are rendered inside ruby. All other nodes recurse normally.
    """
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return ''.join(_ruby_html(n) for n in node)
    if not isinstance(node, dict):
        return ''
    tag = node.get('tag', '')
    content = node.get('content', '')
    if tag == 'rt':
        return f'<rt>{_ruby_html(content)}</rt>'
    if tag == 'ruby':
        items = content if isinstance(content, list) else [content]
        base = ''.join(_ruby_html(i) for i in items if not (isinstance(i, dict) and i.get('tag') == 'rt'))
        rt = next((_ruby_html(i) for i in items if isinstance(i, dict) and i.get('tag') == 'rt'), '')
        return f'<ruby>{base}{rt}</ruby>'
    return _ruby_html(content)


def _find_example(node) -> tuple[str, str, str] | None:
    """Return (jp_plain, en, jp_furigana) from the first example-sentence node, or None."""
    if isinstance(node, list):
        for item in node:
            result = _find_example(item)
            if result:
                return result
        return None
    if not isinstance(node, dict):
        return None
    if node.get('data', {}).get('content') == 'example-sentence':
        jp = furigana = en = ''
        parts = node.get('content', [])
        if isinstance(parts, dict):
            parts = [parts]
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = part.get('data', {}).get('content', '')
            if part_type == 'example-sentence-a':
                inner = part.get('content', '')
                jp = _text(inner, skip_tags=frozenset({'rt'})).strip()
                furigana = _ruby_html(inner).strip()
            elif part_type == 'example-sentence-b':
                children = part.get('content', [])
                if isinstance(children, dict):
                    children = [children]
                for span in children:
                    if isinstance(span, dict) and span.get('lang') == 'en':
                        en = _text(span.get('content', '')).strip()
                        break
        return (jp, en, furigana) if jp else None
    return _find_example(node.get('content', []))


def _codes_to_hinshi(codes: list[str]) -> str:
    code_set = set(codes)
    for code, hinshi in _POS_MAP:
        if code in code_set:
            return hinshi
    return ''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_jitendex_index(directory: Path) -> dict[str, dict]:
    """Build a headword index from Jitendex yomitan term banks.

    Returns headword → {'品詞', '英語訳', '例文', '英語例文', '例文振り仮名'}
    Keeps the highest-popularity entry per headword. Also indexes by reading so
    that kana-only lookups (e.g. 'ある') find the kanji entry ('有る').
    """
    index: dict[str, dict] = {}
    reading_best: dict[str, tuple[int, str]] = {}  # reading → (pop, term)

    for path in sorted(directory.glob('term_bank_*.json')):
        with open(path, encoding='utf-8') as f:
            entries = json.load(f)
        for entry in entries:
            term = entry[0]
            reading = entry[1] if len(entry) > 1 else ''
            popularity = entry[4] if len(entry) > 4 else 0
            definitions = entry[5] if len(entry) > 5 else []

            existing = index.get(term)
            if existing and existing['_pop'] >= popularity:
                continue

            glosses = _find_glosses(definitions)
            if not glosses:
                continue

            pos_codes = _find_pos_codes(definitions)
            example = _find_example(definitions)

            index[term] = {
                '品詞': _codes_to_hinshi(pos_codes),
                '英語訳': '; '.join(glosses),
                '読み': reading,
                '例文': example[0] if example else '',
                '英語例文': example[1] if example else '',
                '例文振り仮名': example[2] if example else '',
                '_pop': popularity,
            }

            if reading and reading != term:
                existing_rb = reading_best.get(reading)
                if not existing_rb or existing_rb[0] < popularity:
                    reading_best[reading] = (popularity, term)

    for reading, (_, best_term) in reading_best.items():
        if reading not in index:
            index[reading] = dict(index[best_term])

    for v in index.values():
        del v['_pop']

    return index


def build_jmdict_index(directory: Path) -> dict[str, str]:
    """Build a headword → gloss index from a JMdict yomitan term bank directory."""
    index: dict[str, tuple[str, int]] = {}

    for path in sorted(directory.glob('term_bank_*.json')):
        with open(path, encoding='utf-8') as f:
            entries = json.load(f)
        for entry in entries:
            term = entry[0]
            popularity = entry[4] if len(entry) > 4 else 0
            definitions = entry[5] if len(entry) > 5 else []

            existing = index.get(term)
            if existing and existing[1] >= popularity:
                continue

            glosses = [d for d in definitions if isinstance(d, str) and d.strip()]
            if glosses:
                index[term] = ('; '.join(glosses), popularity)

    return {term: glosses for term, (glosses, _) in index.items()}

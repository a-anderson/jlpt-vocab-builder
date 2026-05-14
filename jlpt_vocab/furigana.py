"""Furigana conversion and normalisation."""

import re

_CJK = r'一-鿿㐀-䶿'
_HIRAGANA = '぀-ゟ'
_KATAKANA = '゠-ヿ'

_RUBY_REPL = r'<ruby>\1<rt>\2</rt></ruby>'


def bracket_to_ruby(raw: str) -> str:
    """Convert chadmuro bracket-notation furigana to HTML ruby.

    '食[た]べる'              → '<ruby>食<rt>た</rt></ruby>べる'
    '（ご） 主[しゅ] 人[じん]' → '（ご）<ruby>主<rt>しゅ</rt></ruby><ruby>人<rt>じん</rt></ruby>'
    'のど'                    → 'のど'
    """
    result = re.sub(
        rf'([{_CJK}][^\[\]\s]*)\[([^\]]+)\]',
        _RUBY_REPL,
        raw,
    )
    result = re.sub(r'</ruby>\s+<ruby>', '</ruby><ruby>', result)
    result = re.sub(r'\s+<ruby>', '<ruby>', result)
    return result.strip()


def normalise_furigana(html: str) -> str:
    """Normalise inconsistent furigana conventions from Ollama output.

    Handles redundant ruby on kana, paren readings on katakana, and
    converts halfwidth/fullwidth/bracket notation to ruby HTML.
    """
    # Strip redundant ruby where base is already pure kana
    html = re.sub(
        rf'<ruby>([{_HIRAGANA}{_KATAKANA}]+)<rt>[{_HIRAGANA}{_KATAKANA}]+</rt></ruby>',
        r'\1',
        html,
    )
    # Strip paren readings on pure katakana words
    html = re.sub(rf'([{_KATAKANA}]+)\([{_HIRAGANA}]+\)', r'\1', html)
    html = re.sub(rf'([{_KATAKANA}]+)（[{_HIRAGANA}]+）', r'\1', html)
    # Convert various notation styles to ruby (base must start with CJK)
    _base = rf'[{_CJK}][^\s(（）\[\]]*'
    html = re.sub(rf'({_base})\(([{_HIRAGANA}]+)\)', _RUBY_REPL, html)
    html = re.sub(rf'({_base})（([{_HIRAGANA}]+)）', _RUBY_REPL, html)
    html = re.sub(rf'({_base})\[([{_HIRAGANA}]+)\]', _RUBY_REPL, html)
    return html

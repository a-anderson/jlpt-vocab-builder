"""Headword normalisation for chadmuro vocabulary entries."""

import re

_SUFFIX_POS = {
    'な': 'な形容詞',
    'する': 'サ変動詞（する）',
    'の': 'の形容詞',
}


def normalise_word(word: str) -> dict:
    """Return lookup forms and inferred POS for a chadmuro headword.

    Handles prefix parens: '（ご）主人' → forms=['ご主人', '主人']
    Handles suffix parens: '残念（な）'  → forms=['残念'], pos='な形容詞'
    Handles leading tilde:  '～以上'     → forms=['以上']
    Handles trailing tilde: '真～'       → forms=['真']

    Returns {'lookup_forms': list[str], 'inferred_pos': str}
    """
    prefix = re.match(r'^（([^）]+)）(.+)$', word)
    if prefix:
        affix, base = prefix.group(1), prefix.group(2).strip()
        return {'lookup_forms': [affix + base, base], 'inferred_pos': ''}

    suffix = re.match(r'^(.+?)（([^）]+)）$', word)
    if suffix:
        base, tag = suffix.group(1).strip(), suffix.group(2)
        return {'lookup_forms': [base], 'inferred_pos': _SUFFIX_POS.get(tag, '')}

    # ～ is a chadmuro convention marking affix words; strip it for dictionary lookup
    if word.startswith('～') and word != '～':
        return {'lookup_forms': [word[1:]], 'inferred_pos': ''}

    if word.endswith('～') and word != '～':
        return {'lookup_forms': [word[:-1]], 'inferred_pos': ''}

    return {'lookup_forms': [word], 'inferred_pos': ''}

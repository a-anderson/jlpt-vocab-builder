"""Shared pytest fixtures."""

import json
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def sample_example_node():
    """Exact Jitendex example-sentence node structure for 食べる, sense 1.

    Japanese: もっと果物を食べるべきです。
    English:  You should eat more fruit.
    Furigana: もっと<ruby>果<rt>くだ</rt></ruby><ruby>物<rt>もの</rt></ruby>を<ruby>食<rt>た</rt></ruby>べるべきです。
    """
    return {
        'tag': 'div',
        'data': {'content': 'example-sentence'},
        'content': [
            {
                'tag': 'div',
                'data': {'content': 'example-sentence-a'},
                'content': {
                    'tag': 'span',
                    'lang': 'ja',
                    'content': [
                        'もっと',
                        {'tag': 'ruby', 'content': ['果', {'tag': 'rt', 'content': 'くだ'}]},
                        {'tag': 'ruby', 'content': ['物', {'tag': 'rt', 'content': 'もの'}]},
                        'を',
                        {
                            'tag': 'span',
                            'data': {'content': 'example-keyword'},
                            'content': [
                                {'tag': 'ruby', 'content': ['食', {'tag': 'rt', 'content': 'た'}]},
                                'べる',
                            ],
                        },
                        'べきです。',
                    ],
                },
            },
            {
                'tag': 'div',
                'data': {'content': 'example-sentence-b'},
                'content': [
                    {'tag': 'span', 'lang': 'en', 'content': 'You should eat more fruit.'},
                ],
            },
        ],
    }


@pytest.fixture
def sample_pos_node():
    """A structured-content tree containing two part-of-speech-info spans."""
    return [
        {
            'tag': 'span',
            'data': {'content': 'part-of-speech-info', 'code': 'vt'},
            'content': '他動詞',
        },
        {
            'tag': 'span',
            'data': {'content': 'part-of-speech-info', 'code': 'v1'},
            'content': '一段動詞',
        },
        {
            'tag': 'div',
            'data': {'content': 'glossary'},
            'content': 'should not appear as POS',
        },
    ]


@pytest.fixture
def sample_glossary_node():
    """A structured-content tree with one glossary ul and one extra-info block to skip."""
    return [
        {
            'tag': 'ul',
            'data': {'content': 'glossary'},
            'content': [
                {'tag': 'li', 'content': 'to eat'},
                {'tag': 'li', 'content': 'to consume'},
            ],
        },
        {
            'tag': 'div',
            'data': {'content': 'extra-info'},
            'content': [
                {
                    'tag': 'ul',
                    'data': {'content': 'glossary'},
                    'content': [{'tag': 'li', 'content': 'should be skipped'}],
                },
            ],
        },
    ]


@pytest.fixture
def sample_ruby_node():
    """A Jitendex-style content tree containing ruby and plain text nodes."""
    return [
        'もっと',
        {'tag': 'ruby', 'content': ['果', {'tag': 'rt', 'content': 'くだ'}]},
        {'tag': 'ruby', 'content': ['物', {'tag': 'rt', 'content': 'もの'}]},
        'を食べる。',
    ]


@pytest.fixture(scope='session')
def jitendex_dir():
    return REPO_ROOT / 'data' / 'jitendex-yomitan'


@pytest.fixture(scope='session')
def french_dir():
    return REPO_ROOT / 'data' / 'JMdict_french'


@pytest.fixture(scope='session')
def jitendex_index(jitendex_dir):
    from dictionary import build_jitendex_index
    return build_jitendex_index(jitendex_dir)


@pytest.fixture(scope='session')
def french_index(french_dir):
    from dictionary import build_french_index
    return build_french_index(french_dir)

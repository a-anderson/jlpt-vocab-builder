"""Append arbitrary words to a vocabulary CSV outside the JLPT word list."""

import argparse
import csv
import re
import sys
from pathlib import Path

from tqdm import tqdm

from build_jlpt_csv import (
    LANGUAGES, make_csv_columns, ollama_generate, ollama_generate_furigana,
    word_in_sentence, extract_target,
)
from dictionary import build_jitendex_index, build_jmdict_index
from download import ensure_all, DATA_DIR
from furigana import bracket_to_ruby
from normalise import normalise_word
from pitch_accent import get_pitch_columns, plain_kana
from drop_words import load_checkpoint, save_checkpoint

DEFAULT_OUTPUT = Path('custom_words.csv')

_HAS_KANA = re.compile(r'[぀-ヿ]')


def _word_furigana(word: str, reading: str, model: str) -> str:
    """Return ruby HTML furigana for a word given its kana reading."""
    if '[' in word:
        return bracket_to_ruby(word)
    if not reading:
        return ''
    if not _HAS_KANA.search(word):
        return f'<ruby>{word}<rt>{reading}</rt></ruby>'
    return ollama_generate_furigana(word, reading, model)


def add_words(words: list[str], output_path: Path, model: str, langs: list[str]) -> None:
    ensure_all(langs)

    jitendex = build_jitendex_index(DATA_DIR / 'jitendex-yomitan')
    lang_indexes = {
        lang: build_jmdict_index(DATA_DIR / LANGUAGES[lang][1])
        for lang in langs
    }

    checkpoint_path = output_path.with_name(output_path.stem + '_checkpoint.json')
    done = load_checkpoint(checkpoint_path)
    csv_columns = make_csv_columns(langs)

    if output_path.exists():
        with open(output_path, newline='', encoding='utf-8') as f:
            existing_fieldnames = csv.DictReader(f).fieldnames or []
        if existing_fieldnames != csv_columns:
            detected = [lang for lang in LANGUAGES if f'{LANGUAGES[lang][0]}語訳' in existing_fieldnames]
            sys.exit(
                f'Error: {output_path.name} was built with --languages {detected}.\n'
                f'Cannot append with --languages {langs}.\n'
                f'To add a new language first: python add_language_columns.py --language <lang> --output {output_path} --model {model}'
            )

    mode = 'a' if output_path.exists() else 'w'
    with open(output_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        if mode == 'w':
            writer.writeheader()

        for word in tqdm(words, desc='Processing words'):
            if word in done:
                continue

            norm = normalise_word(word)
            lookup_forms = norm['lookup_forms']
            inferred_pos = norm['inferred_pos']

            jm = next((jitendex[fm] for fm in lookup_forms if fm in jitendex), {})
            品詞 = jm.get('品詞', '') or inferred_pos
            英語訳 = jm.get('英語訳', '')
            例文 = jm.get('例文', '')
            英語例文 = jm.get('英語例文', '')
            例文振り仮名 = jm.get('例文振り仮名', '')

            if 例文 and not word_in_sentence(lookup_forms[0], 例文):
                例文 = 英語例文 = 例文振り仮名 = ''

            lang_glosses = {}
            need_gloss_for = []
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
            jitendex_reading = jm.get('読み', '')
            振り仮名 = _word_furigana(word, jitendex_reading, model)
            reading = plain_kana(word)
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
                'レベル': 'Custom',
            }.items()})
            f.flush()
            done.add(word)
            save_checkpoint(done, checkpoint_path)

    print(f'Done. {len(done)} word(s) written to {output_path}.')
    print('Run `python generate_pitch_svgs.py` to generate pitch diagrams for new entries.')


def main() -> None:
    parser = argparse.ArgumentParser(description='Add custom words to a vocabulary CSV.')
    parser.add_argument('words', nargs='+', help='Words to add')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT), help='CSV file (default: custom_words.csv)')
    parser.add_argument('--model', required=True, help='Ollama model name')
    parser.add_argument('--languages', nargs='+', default=['french'], choices=list(LANGUAGES.keys()))
    args = parser.parse_args()
    add_words(args.words, Path(args.output), args.model, args.languages)


if __name__ == '__main__':
    main()

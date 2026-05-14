"""Append arbitrary words to a vocabulary CSV outside the JLPT word list."""

import argparse
import csv
import re
import sys
from pathlib import Path

from tqdm import tqdm

from jlpt_vocab.csv_utils import load_checkpoint, save_checkpoint
from jlpt_vocab.dictionary import build_jitendex_index, build_jmdict_index
from jlpt_vocab.download import ensure_all, DATA_DIR
from jlpt_vocab.furigana import bracket_to_ruby
from jlpt_vocab.pitch_accent import get_pitch_columns, plain_kana
from jlpt_vocab.pipeline import (
    LANGUAGES, make_csv_columns, process_word, ollama_generate_furigana,
)

DEFAULT_OUTPUT = Path('output/custom_words.csv')

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
                f'To add a new language first: python scripts/add_language.py --language <lang> --output {output_path} --model {model}'
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = 'a' if output_path.exists() else 'w'
    with open(output_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        if mode == 'w':
            writer.writeheader()

        for word in tqdm(words, desc='Processing words'):
            if word in done:
                continue

            content, lookup_forms, jitendex_reading = process_word(
                word, model, jitendex, lang_indexes, langs,
            )
            振り仮名 = _word_furigana(word, jitendex_reading, model)
            reading = plain_kana(word)
            pitch_cols = get_pitch_columns(lookup_forms[0], reading)

            writer.writerow({k: v.replace('\x00', '') for k, v in {
                '単語': word,
                '振り仮名': 振り仮名,
                'ピッチアクセント': pitch_cols['ピッチアクセント'],
                'ピッチアクセント図': pitch_cols['ピッチアクセント図'],
                **content,
                'レベル': 'Custom',
            }.items()})
            f.flush()
            done.add(word)
            save_checkpoint(done, checkpoint_path)

    print(f'Done. {len(done)} word(s) written to {output_path}.')
    print('Run `python scripts/generate_svgs.py` to generate pitch diagrams for new entries.')


def _read_words_file(path: Path) -> list[str]:
    """Read one word per line; skip blank lines and # comments."""
    with path.open(encoding='utf-8') as f:
        return [ln for ln in (line.strip() for line in f) if ln and not ln.startswith('#')]


def add_words_from_args(
    cli_words: list[str],
    file_path: Path | None,
    output_path: Path,
    model: str,
    langs: list[str],
) -> None:
    """Merge words from a file and CLI args, deduplicate, then call add_words."""
    if file_path is not None:
        if not file_path.exists():
            sys.exit(f'File not found: {file_path}')
        words = _read_words_file(file_path) + list(cli_words)
    else:
        words = list(cli_words)

    words = list(dict.fromkeys(words))

    if not words:
        sys.exit('No words provided. Pass words as arguments or use --file.')

    add_words(words, output_path, model, langs)


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Add custom words to a vocabulary CSV.')
    parser.add_argument('words', nargs='*', default=[], help='Words to add')
    parser.add_argument('--file', default=None, help='Text file with one word per line; lines starting with # are ignored')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT), help='CSV file (default: output/custom_words.csv)')
    parser.add_argument('--model', required=True, help='Ollama model name')
    parser.add_argument('--languages', nargs='*', default=[],
                        choices=list(LANGUAGES.keys()),
                        help='Extra languages to include alongside English (default: none — English only)')
    return parser


def main() -> None:
    args = _make_parser().parse_args()
    file_path = Path(args.file) if args.file else None
    add_words_from_args(args.words, file_path, Path(args.output), args.model, args.languages)


if __name__ == '__main__':
    main()

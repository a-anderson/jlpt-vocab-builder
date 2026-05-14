"""Build a JLPT N4–N1 vocabulary CSV for Anki import.

Usage:
  python scripts/build.py --model gemma4:e4b
  python scripts/build.py --model gemma4:e4b --levels n4 n3
  python scripts/build.py --model gemma4:e4b --resume
  python scripts/build.py --model gemma4:e4b --output output/n4.csv
"""

import argparse
import csv
from pathlib import Path

from tqdm import tqdm

from jlpt_vocab.csv_utils import drop_from_csv, drop_from_checkpoint, load_checkpoint, save_checkpoint
from jlpt_vocab.dictionary import build_jitendex_index, build_jmdict_index
from jlpt_vocab.download import ensure_all
from jlpt_vocab.furigana import bracket_to_ruby
from jlpt_vocab.pitch_accent import get_pitch_columns, plain_kana
from jlpt_vocab.pipeline import (
    LEVELS, DATA_DIR, JITENDEX_DIR, OUTPUT_CSV, LANGUAGES, make_csv_columns,
    fetch_chadmuro_words, process_word, find_repair_candidates, detect_csv_languages,
)


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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = 'a' if (output_path.exists() and args.resume) else 'w'
    with open(output_path, mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
        if mode == 'w':
            writer.writeheader()

        for entry in tqdm(unique_words, desc='Processing words'):
            word = entry['単語']
            if args.resume and word in done:
                continue

            content, lookup_forms, _ = process_word(
                word, args.model, jitendex, lang_indexes, args.languages,
                en_gloss_fallback=entry.get('英語訳_raw', ''),
            )
            振り仮名 = bracket_to_ruby(entry['振り仮名_raw'])
            reading = plain_kana(entry['振り仮名_raw'])
            pitch_cols = get_pitch_columns(lookup_forms[0], reading)

            writer.writerow({k: v.replace('\x00', '') for k, v in {
                '単語': word,
                '振り仮名': 振り仮名,
                'ピッチアクセント': pitch_cols['ピッチアクセント'],
                'ピッチアクセント図': pitch_cols['ピッチアクセント図'],
                **content,
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

"""Add a new language's gloss and example sentence columns to an existing CSV."""

import argparse
import csv
from pathlib import Path

from tqdm import tqdm

from build_jlpt_csv import LANGUAGES, ollama_generate
from dictionary import build_jmdict_index
from download import ensure_jmdict, DATA_DIR
from drop_words import load_checkpoint, save_checkpoint
from normalise import normalise_word


def add_language_columns(csv_path: Path, lang: str, model: str) -> None:
    abbrev, dir_name = LANGUAGES[lang]
    gloss_col = f'{abbrev}語訳'
    example_col = f'{abbrev}語例文'

    ensure_jmdict(lang)
    lang_index = build_jmdict_index(DATA_DIR / dir_name)

    checkpoint_path = csv_path.with_name(f'{csv_path.stem}_add_{lang}_checkpoint.json')
    done = load_checkpoint(checkpoint_path)

    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return

    if gloss_col in rows[0] and example_col in rows[0]:
        print(f'{lang.capitalize()} columns already exist in {csv_path} — nothing to do.')
        checkpoint_path.unlink(missing_ok=True)
        return

    new_fieldnames = list(rows[0].keys()) + [gloss_col, example_col]
    out_path = csv_path.with_suffix('.tmp')

    if out_path.exists() and done:
        mode = 'a'
    else:
        if not out_path.exists() and done:
            # Previous run completed and renamed .tmp to original; stale checkpoint
            checkpoint_path.unlink(missing_ok=True)
            return
        mode = 'w'

    with open(out_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        if mode == 'w':
            writer.writeheader()

        for row in tqdm(rows, desc=f'Adding {lang}'):
            word = row['単語']
            if word in done:
                continue

            lookup_forms = normalise_word(word)['lookup_forms']
            gloss = next((lang_index[fm] for fm in lookup_forms if fm in lang_index), '')
            need_gloss = not bool(gloss) and bool(row.get('英語訳', ''))

            example_translation = ''
            if row.get('例文'):
                ollama_data = ollama_generate(
                    word=word, model=model,
                    en_gloss=row.get('英語訳', ''), pos=row.get('品詞', ''),
                    need_sentence=False,
                    existing_jp=row['例文'], existing_en=row.get('英語例文', ''),
                    langs=[lang], need_gloss_for=[lang] if need_gloss else [],
                )
                if need_gloss:
                    gloss = ollama_data.get(gloss_col, '')
                example_translation = ollama_data.get(example_col, '')

            row[gloss_col] = gloss
            row[example_col] = example_translation
            writer.writerow(row)
            f.flush()
            done.add(word)
            save_checkpoint(done, checkpoint_path)

    out_path.replace(csv_path)
    checkpoint_path.unlink(missing_ok=True)
    print(f'Done. {lang.capitalize()} columns added to {csv_path}.')
    print('Run `python generate_pitch_svgs.py` if you have not already done so.')


def main() -> None:
    parser = argparse.ArgumentParser(description='Add language columns to an existing CSV.')
    parser.add_argument('--language', required=True, choices=list(LANGUAGES.keys()))
    parser.add_argument('--output', required=True, help='CSV file to update')
    parser.add_argument('--model', required=True, help='Ollama model name')
    args = parser.parse_args()
    add_language_columns(Path(args.output), args.language, args.model)


if __name__ == '__main__':
    main()

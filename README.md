# JLPT Vocab Builder

[![tests](https://github.com/a-anderson/jlpt-vocab-builder/actions/workflows/test.yml/badge.svg)](https://github.com/a-anderson/jlpt-vocab-builder/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Builds a JLPT N4–N1 vocabulary CSV (~6,000 words) suitable for import into Anki or any SRS tool. Each row contains the word, furigana, part of speech, pitch accent, English and optional language glosses, an example sentence with furigana markup, sentence translations, the surface form of the word as used in the sentence, and a reference to a pitch accent diagram SVG.

---

## Output

`output/jlpt_vocab.csv` — one row per word, 11 columns by default (English only):

| Column                             | Example                                     |
| ---------------------------------- | ------------------------------------------- |
| 単語 (word)                        | 食べる                                      |
| 振り仮名 (furigana)                | `<ruby>食<rt>た</rt></ruby>べる`            |
| 品詞 (part of speech)              | 他動詞                                      |
| ピッチアクセント (pitch pattern)   | `2`                                         |
| ピッチアクセント図 (pitch diagram) | `3_2.svg`                                   |
| 英語訳 (English gloss)             | to eat; to consume                          |
| 例文 (example sentence)            | 毎朝ご飯を食べる。                          |
| 例文振り仮名 (sentence furigana)   | `<ruby>毎朝<rt>まいあさ</rt></ruby>ご飯を…` |
| 英語例文 (English sentence)        | I eat rice every morning.                   |
| 日本語ターゲット (surface form)    | 食べた                                      |
| レベル (JLPT level)                | N4                                          |

With `--languages`, two columns are added per language: a gloss column (e.g. `仏語訳`) and a sentence column (e.g. `仏語例文`).

Furigana columns use HTML `<ruby>` tags. Enable **Allow HTML in fields** when importing into Anki.

---

## Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) running locally with a model pulled, e.g. `ollama pull gemma4:e4b`

Data files are **downloaded automatically on first run** into the `data/` directory. Manual download locations (if you prefer to pre-populate):

| File                              | Source                                                                                                                                                      |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data/jitendex-yomitan/`          | [Jitendex for Yomitan](https://github.com/stephenmk/stephenmk.github.io/releases/latest/download/jitendex-yomitan.zip) — extract zip contents into folder   |
| `data/JMdict_{lang}/`             | [JMdict for Yomitan](https://github.com/yomidevs/jmdict-yomitan/releases/latest) — only needed when passing `--languages`; extract zip contents into folder |
| `data/nhk_data/ACCDB_unicode.csv` | [NHK pronunciation CSV](https://raw.githubusercontent.com/javdejong/nhk-pronunciation/master/ACCDB_unicode.csv)                                             |
| `data/accents.txt`                | [Kanjium pitch accents](https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt)                                   |

---

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e .                  # installs package and all runtime dependencies
pip install -r requirements-dev.txt  # dev dependencies (pytest)
python -m unidic download         # downloads full UniDic (~750 MB); skip if running tests only
```

---

## Running

```bash
source venv/bin/activate

# Full run (all levels, English only)
python scripts/build.py --model gemma4:e4b

# Add extra languages alongside English
python scripts/build.py --model gemma4:e4b --languages french
python scripts/build.py --model gemma4:e4b --languages french spanish german

# Subset of levels
python scripts/build.py --model gemma4:e4b --levels n4 n3

# Resume after interruption (languages auto-detected from the existing CSV)
python scripts/build.py --model gemma4:e4b --resume

# Append pitch-accent citation particles (が/よ) to 単語 and 振り仮名
python scripts/build.py --model gemma4:e4b --particles

# Generate pitch accent SVGs (run once after CSV is complete)
python scripts/generate_svgs.py

# Generate pitch accent SVGs from a specified CSV file
python scripts/generate_svgs.py --input output/n4.csv --out_dir output/pitch_svgs/

# Draw a diagram for a phrase or compound by hand — see "Pitch diagrams for
# phrases and compound words" below for the full flag reference
python scripts/phrase_svg.py --mora 5 --rise 1 --drop 4 --particles 3
```

The pipeline writes rows incrementally and checkpoints after every word, so `--resume` picks up exactly where it left off.

> **Note on speed:** Each word requires one or two Ollama calls (sentence generation, furigana, translations). Expect roughly 20 seconds per word on a modern laptop — around 45 hours for the full 6,000-word dataset. Parallel runs across four terminals cut this proportionally.

### Parallel runs

Run one level per terminal to process levels concurrently:

```bash
python scripts/build.py --model gemma4:e4b --levels n4 --output output/n4.csv
python scripts/build.py --model gemma4:e4b --levels n3 --output output/n3.csv
python scripts/build.py --model gemma4:e4b --levels n2 --output output/n2.csv
python scripts/build.py --model gemma4:e4b --levels n1 --output output/n1.csv
```

Concatenate when all are done, then deduplicate (words that appear in multiple level lists are common):

```bash
head -1 output/n4.csv > output/jlpt_vocab.csv
for f in output/n4.csv output/n3.csv output/n2.csv output/n1.csv; do tail -n +2 "$f"; done >> output/jlpt_vocab.csv

python scripts/dedup_words.py --output output/jlpt_vocab.csv
```

---

## Pitch diagrams for phrases and compound words

Words whose pitch rises and falls more than once — phrases like `腹が立つ` and `頭が上がらない`, or
compounds like `年末年始` — have no single accent pattern number, so the pipeline leaves them as
`unknown.svg`. `phrase_svg.py` draws these by hand, producing a diagram visually identical to the
generated ones:

```bash
# 腹が立つ (はらがたつ) — rises after は, falls after た, が is the 3rd mora
python scripts/phrase_svg.py --mora 5 --rise 1 --drop 4 --particles 3

# Multiple rises and falls, and more than one particle
python scripts/phrase_svg.py --mora 8 --rise 1 5 --drop 3 --particles 3 8

# Batch: one set of flags per line
python scripts/phrase_svg.py --file phrases.txt
```

`--rise N` and `--drop N` both name the boundary **after** mora N — `--drop 2` means the pitch falls
after the second mora. This is the same numbering as the accent pattern, so `--drop N` is exactly
pattern N. The phrase starts low unless `--rise 0` is given, which is the boundary before the first
mora. On a four-mora word:

| Contour   | Levels | Flags                | Equivalent |
| --------- | ------ | -------------------- | ---------- |
| Heiban    | `LHHH` | `--rise 1`           | `4_0.svg`  |
| Atamadaka | `HLLL` | `--rise 0 --drop 1`  | `4_1.svg`  |
| Nakadaka  | `LHLL` | `--rise 1 --drop 2`  | `4_2.svg`  |
| Nakadaka  | `LHHL` | `--rise 1 --drop 3`  | `4_3.svg`  |
| Odaka     | `LHHH` | `--rise 1 --drop 4`  | `4_4.svg`  |

Repeat either flag for a phrase that goes up and down more than once, e.g. `--rise 1 5 --drop 3`.

| Flag          | Meaning                                                          |
| ------------- | ---------------------------------------------------------------- |
| `--mora`      | Total mora in the phrase, particles included                     |
| `--rise`      | Pitch rises after mora N; `0` means the phrase starts high       |
| `--drop`      | Pitch falls after mora N; same numbering as the accent pattern   |
| `--particles` | Mora drawn as hollow circles — 1-indexed mora, not boundaries    |
| `--file`      | Text file of specs, one per line; `#` comments ignored           |
| `--out_dir`   | Output directory (default `output/pitch_svgs`)                   |

Each generated file prints its resulting level string (`phrase_5_r1_d4_p3.svg  LHHHL`) so the
contour can be checked before import. A toggle that does nothing is rejected — a rise while already
high, a drop while already low, or a rise and drop at the same boundary.

Files are named after the contour, e.g. `phrase_5_r1_d4_p3.svg` — identical contours reuse one file.
Copy them into your Anki media folder alongside the generated SVGs and point the row's
`ピッチアクセント図` field at the filename.

A spec file looks like:

```
# 腹が立つ / はらがたつ
--mora 5 --rise 1 --drop 4 --particles 3

# 頭が上がらない / あたまがあがらない
--mora 9 --rise 1 --drop 3 --particles 4
```

---

## Repair incomplete rows

If Ollama fails mid-run, some rows may have empty fields. Re-run with `--repair` to find and reprocess them:

```bash
python scripts/build.py --model gemma4:e4b --output output/n4.csv --repair
```

The pipeline auto-detects which languages are in the CSV — no need to pass `--languages`.

> **Note:** `--repair` only works for words in the JLPT word lists. For incomplete
> rows in a custom words file, `--repair` removes them automatically — re-run
> `add_words.py --resume` to reprocess them.

---

## Backfill missing 品詞, 英語訳, and pitch accent

If a finished CSV has rows with empty 品詞, 英語訳, or ピッチアクセント — typically kana-only words whose canonical form in Jitendex is kanji (e.g. `ある` → `有る`), bare な-adjectives (e.g. `ラッキーな`), or bare と-adverbs (e.g. `すらりと`) — backfill them from the dictionary without reprocessing the pipeline:

```bash
python scripts/repair_pos.py --output output/n4.csv
```

The script handles all combinations of missing fields in a single pass:

| 品詞 empty | ピッチアクセント empty | Action                        |
| ---------- | ---------------------- | ----------------------------- |
| yes        | yes                    | backfill both                 |
| yes        | no                     | backfill 品詞 and 英語訳 only |
| no         | yes                    | backfill pitch only           |
| no         | no                     | skip                          |

Words not found in Jitendex are left untouched.

| Flag       | Description                            |
| ---------- | -------------------------------------- |
| `--output` | CSV file to repair in place (required) |

---

## Add a language to an existing CSV

To retrofit a finished CSV with a new language's glosses and sentence translations without reprocessing everything:

```bash
python scripts/add_language.py --language german --output output/n4.csv --model gemma4:e4b
```

Supported languages: `french`, `spanish`, `german`, `dutch`, `russian`, `swedish`.

The script checkpoints after each row and can be safely interrupted and resumed.

---

## Add custom words outside the JLPT list

```bash
# Write to output/custom_words.csv (English only, created if absent)
python scripts/add_words.py 猫背 蹴る --model gemma4:e4b

# With extra languages alongside English
python scripts/add_words.py 猫背 蹴る --model gemma4:e4b --languages french

# Append to an existing CSV
python scripts/add_words.py 猫背 --output output/n4.csv --model gemma4:e4b

# Read words from a file (one word per line)
python scripts/add_words.py --file my_words.txt --model gemma4:e4b

# Combine a file with extra words on the command line
python scripts/add_words.py 納豆 --file my_words.txt --model gemma4:e4b

# With extra languages alongside English
python scripts/add_words.py 猫背 --output output/custom_words.csv --model gemma4:e4b --languages french spanish

# Resume after an interruption
python scripts/add_words.py --file my_words.txt --model gemma4:e4b --resume

# Append pitch-accent citation particles to all words (including existing rows)
python scripts/add_words.py 猫背 --output output/n4.csv --model gemma4:e4b --particles
```

The script checkpoints after every word, so `--resume` picks up exactly where it left off. To reprocess a specific word, remove it first with `drop_words.py` then re-run.

Word files support bracket notation for furigana hints, blank lines, and `#` comments:

```
# verbs
食[た]べる
飲[の]む

# nouns
猫背
```

Bracket notation (`食[た]べる`) is resolved directly without calling Ollama. Words without brackets use the dictionary reading where available, or Ollama as a fallback.

File words are processed first. Duplicates between the file and command-line arguments are silently dropped (the first occurrence wins). Custom words are written with `レベル = Custom`.

---

## Fixing furigana bracket notation

If a word file has malformed bracket notation (e.g. `火[かようび]曜日` instead of `火[か]曜[よう]日[び]`), use `fix_furigana.py` to correct the file in place:

```bash
python scripts/fix_furigana.py --file n5.csv --model gemma4:e4b
```

The script:

- Accepts any text or CSV file with one word per line
- Skips blank lines and lines starting with `#`
- Looks up the correct reading from the local Jitendex dictionary first, falling back to the reading already embedded in the broken notation
- Asks the Ollama model to redistribute the reading correctly per-kanji (e.g. `火[か]曜[よう]日[び]`)
- For ateji/irregular readings that can't be split per-kanji, brackets the whole compound (e.g. `今朝[けさ]`)
- Writes fixes back to the same file; unfixable words are left unchanged and logged

| Flag      | Description                       |
| --------- | --------------------------------- |
| `--file`  | Path to the input file (required) |
| `--model` | Ollama model name (required)      |

---

## Deduplicating a CSV

When levels are processed separately and concatenated, the same word may appear more than once. To remove duplicates:

```bash
# Preview without making changes
python scripts/dedup_words.py --output output/jlpt_vocab.csv --dry-run

# Remove duplicates in place
python scripts/dedup_words.py --output output/jlpt_vocab.csv
```

Rows are matched on **canonical word + canonical furigana**, where canonical means the trailing citation particle (が/よ) is stripped before comparing. This means a particle-suffixed row (`犬が`) and a bare row (`犬`) from two separate CSV files are treated as duplicates — the first occurrence is kept. Words that share kanji but have different readings (e.g. 人 read as ひと vs にん) are distinct canonical forms and both kept.

---

## Dropping words

To remove words from a CSV and its paired checkpoint (e.g. before reprocessing failed rows):

```bash
python scripts/drop_words.py 下りる 招致 --output output/n4.csv
```

Then re-run with `--resume` to regenerate just those rows.

---

## Append pitch-accent citation particles

For pitch accent practice, it helps to hear each word followed by its citation-form particle (が for nouns and adjectives, よ for verbs and i-adjectives) so the pitch contour of the full phrase is audible. Run this after building and deduplicating the CSV:

```bash
# Preview changes without writing
python scripts/add_particle.py --input output/jlpt_vocab.csv --dry-run

# Update in place
python scripts/add_particle.py --input output/jlpt_vocab.csv

# Write to a new file, leaving the original untouched
python scripts/add_particle.py --input output/jlpt_vocab.csv --output output/jlpt_vocab_particle.csv
```

The script appends the particle to both the `単語` and `振り仮名` columns. Words that already have the correct particle are skipped, so re-running is safe. Parts of speech with no citation particle (adverbs, conjunctions, expressions, etc.) are left unchanged.

When overwriting the input file, a backup is written to `<filename>.csv.bak` (e.g. `output/jlpt_vocab.csv.bak`) before any changes are made.

---

## Anki integration

> **TTS users:** run `add_particle.py` (or build with `--particles`) before importing — the citation-form particle is needed for the pitch contour to be audible in generated audio.

1. Import `output/jlpt_vocab.csv` via **File → Import**. Enable **Allow HTML in fields**.
2. Copy all SVGs from `output/pitch_svgs/` into your Anki media folder:
    - macOS: `cp output/pitch_svgs/*.svg ~/Library/Application\ Support/Anki2/<profile>/collection.media/`
    - Linux: `cp output/pitch_svgs/*.svg ~/.local/share/Anki2/<profile>/collection.media/`
    - Windows: copy to `%APPDATA%\Anki2\<profile>\collection.media\`
3. Reference the columns in your card template:

```html
{{振り仮名}}
<img src="{{ピッチアクセント図}}" />
{{英語訳}} {{例文振り仮名}} {{英語例文}}
```

If you included extra languages, add their columns as needed, e.g. `{{仏語訳}}` and `{{仏語例文}}` for French.

---

## Adding TTS audio to your Anki deck

Before generating audio, run `add_particle.py` (or build with `--particles`) so TTS captures the full pitch contour including the citation-form particle:

```bash
python scripts/add_particle.py --input output/jlpt_vocab.csv
```

Then see [Anki-TTS-Automation](https://github.com/a-anderson/Anki-TTS-Automation) to generate and attach audio files.

---

## Project status

This is a personal project and is **not accepting external contributions or pull requests.** Issues and bug reports are also not monitored. Feel free to fork and adapt the code for your own use under the terms of the [MIT licence](LICENSE).

---

## Tests

```bash
python -m pytest tests/ -v
```

---

## Data sources & licensing

| Source                                                          | Used for                           | Licence                                                    |
| --------------------------------------------------------------- | ---------------------------------- | ---------------------------------------------------------- |
| [chadmuro/jlpt-vocab](https://github.com/chadmuro/jlpt-vocab)   | Word lists                         | MIT                                                        |
| [Jitendex](https://github.com/stephenmk/stephenmk.github.io)    | EN glosses, POS, example sentences | CC BY-SA 4.0                                               |
| [JMdict (yomidevs)](https://github.com/yomidevs/jmdict-yomitan) | Language glosses                   | CC BY-SA 4.0                                               |
| Kanjium / NHK pitch data                                        | Pitch accent                       | Derived from commercial dictionaries — personal study only |

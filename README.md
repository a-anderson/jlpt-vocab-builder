# JLPT Vocab Builder

Builds a JLPT N4–N1 vocabulary CSV (~8,000 words) suitable for import into Anki or any SRS tool. Each row contains the word, furigana, part of speech, pitch accent, English and optional language glosses, an example sentence with furigana markup, sentence translations, the surface form of the word as used in the sentence, and a reference to a pitch accent diagram SVG.

---

## Output

`output/jlpt_vocab.csv` — one row per word, 13+ columns depending on languages selected:

| Column                             | Example                                     |
| ---------------------------------- | ------------------------------------------- |
| 単語 (word)                        | 食べる                                      |
| 振り仮名 (furigana)                | `<ruby>食<rt>た</rt></ruby>べる`            |
| 品詞 (part of speech)              | 他動詞                                      |
| ピッチアクセント (pitch pattern)   | `2`                                         |
| ピッチアクセント図 (pitch diagram) | `3_2.svg`                                   |
| 英語訳 (English gloss)             | to eat; to consume                          |
| 仏語訳 (French gloss)              | manger; consommer                           |
| 例文 (example sentence)            | 毎朝ご飯を食べる。                          |
| 例文振り仮名 (sentence furigana)   | `<ruby>毎朝<rt>まいあさ</rt></ruby>ご飯を…` |
| 英語例文 (English sentence)        | I eat rice every morning.                   |
| 仏語例文 (French sentence)         | Je mange du riz chaque matin.               |
| 日本語ターゲット (surface form)    | 食べた                                      |
| レベル (JLPT level)                | N4                                          |

Furigana columns use HTML `<ruby>` tags. Enable **Allow HTML in fields** when importing into Anki.

---

## Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) running locally with a model pulled, e.g. `ollama pull gemma4:e4b`

Data files are **downloaded automatically on first run** into the `data/` directory. Manual download locations (if you prefer to pre-populate):

| File                              | Source                                                                                                                                                    |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data/jitendex-yomitan/`          | [Jitendex for Yomitan](https://github.com/stephenmk/stephenmk.github.io/releases/latest/download/jitendex-yomitan.zip) — extract zip contents into folder |
| `data/JMdict_french/`             | [JMdict French for Yomitan](https://github.com/yomidevs/jmdict-yomitan/releases/latest/download/JMdict_french.zip) — extract zip contents into folder     |
| `data/nhk_data/ACCDB_unicode.csv` | [NHK pronunciation CSV](https://raw.githubusercontent.com/javdejong/nhk-pronunciation/master/ACCDB_unicode.csv)                                           |
| `data/accents.txt`                | [Kanjium pitch accents](https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt)                                 |

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

# Full run (all levels, French only)
python scripts/build.py --model gemma4:e4b

# Multiple languages
python scripts/build.py --model gemma4:e4b --languages french spanish german

# Subset of levels
python scripts/build.py --model gemma4:e4b --levels n4 n3

# Resume after interruption
python scripts/build.py --model gemma4:e4b --resume

# Generate pitch accent SVGs (run once after CSV is complete)
python scripts/generate_svgs.py
```

The pipeline writes rows incrementally and checkpoints after every word, so `--resume` picks up exactly where it left off.

> **Note on speed:** Each word requires one or two Ollama calls (sentence generation, furigana, translations). Expect roughly 20 seconds per word on a modern laptop — around 45 hours for the full 8,000-word dataset. Parallel runs across four terminals cut this proportionally.

### Parallel runs

Run one level per terminal to process levels concurrently:

```bash
python scripts/build.py --model gemma4:e4b --levels n4 --output output/n4.csv
python scripts/build.py --model gemma4:e4b --levels n3 --output output/n3.csv
python scripts/build.py --model gemma4:e4b --levels n2 --output output/n2.csv
python scripts/build.py --model gemma4:e4b --levels n1 --output output/n1.csv
```

Concatenate when all are done:

```bash
head -1 output/n4.csv > output/jlpt_vocab.csv
for f in output/n4.csv output/n3.csv output/n2.csv output/n1.csv; do tail -n +2 "$f"; done >> output/jlpt_vocab.csv
```

---

## Repair incomplete rows

If Ollama fails mid-run, some rows may have empty fields. Re-run with `--repair` to find and reprocess them:

```bash
python scripts/build.py --model gemma4:e4b --output output/n4.csv --repair
```

The pipeline auto-detects which languages are in the CSV — no need to pass `--languages`.

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
# Write to output/custom_words.csv (created if absent)
python scripts/add_words.py 猫背 蹴る --model gemma4:e4b

# Append to an existing CSV
python scripts/add_words.py 猫背 --output output/n4.csv --model gemma4:e4b

# Read words from a file (one word per line)
python scripts/add_words.py --file my_words.txt --model gemma4:e4b

# Combine a file with extra words on the command line
python scripts/add_words.py 納豆 --file my_words.txt --model gemma4:e4b

# With extra languages
python scripts/add_words.py 猫背 --output output/custom_words.csv --model gemma4:e4b --languages french spanish

# Resume after an interruption
python scripts/add_words.py --file my_words.txt --model gemma4:e4b --resume
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

## Dropping words

To remove words from a CSV and its paired checkpoint (e.g. before reprocessing failed rows):

```bash
python scripts/drop_words.py 下りる 招致 --output output/n4.csv
```

Then re-run with `--resume` to regenerate just those rows.

---

## Migration (existing users)

If you set up the project before the `output/` restructure, move your existing files:

```bash
mkdir -p output
mv n*.csv n*_checkpoint.json output/
mv pitch_svgs/ output/
pip install -e .
```

---

## Anki integration

1. Import `output/jlpt_vocab.csv` via **File → Import**. Enable **Allow HTML in fields**.
2. Copy all SVGs from `output/pitch_svgs/` into your Anki media folder:
    - macOS: `cp output/pitch_svgs/*.svg ~/Library/Application\ Support/Anki2/<profile>/collection.media/`
    - Linux: `cp output/pitch_svgs/*.svg ~/.local/share/Anki2/<profile>/collection.media/`
    - Windows: copy to `%APPDATA%\Anki2\<profile>\collection.media\`
3. Reference the columns in your card template:

```html
{{振り仮名}}
<img src="{{ピッチアクセント図}}" />
{{英語訳}} / {{仏語訳}} {{例文振り仮名}} {{英語例文}} / {{仏語例文}}
```

---

## Adding TTS audio to your Anki deck

To add text-to-speech audio for the vocabulary and example sentences in your deck, see [Anki-TTS-Automation](https://github.com/a-anderson/Anki-TTS-Automation).

---

## Project status

This is a personal project and is **not accepting external contributions or pull requests.** Issues and bug reports are also not monitored. Feel free to fork and adapt the code for your own use under the terms of the MIT licence.

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

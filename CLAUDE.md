# JLPT Vocabulary CSV Builder — Agent Guide

## Project purpose

Build a JLPT N4–N1 vocabulary CSV (~8,000 words) for Anki import.

Output: `output/jlpt_vocab.csv` with 13 columns — word, furigana, POS, pitch accent, English/French glosses, example sentence, sentence furigana, translations, surface form, JLPT level.

---

## Coding standards

- **Simplicity first.** Three similar lines beat a premature abstraction. Only introduce a class, helper, or abstraction when a simpler approach has been ruled out.
- **SOLID principles.** Each module has one responsibility. Functions do one thing.
- **Minimal imports.** Add a library only when stdlib cannot do the job. No `lxml` — all sources are JSON/CSV.
- **No speculative code.** No error handling for impossible cases. No feature flags. No backwards-compat shims.
- **No comments explaining *what* code does.** Only comment the *why* when it is non-obvious (a constraint, a workaround, a subtle invariant).
- **No multi-line docstrings.** One short line per function is the max.
- **Test-first.** Write `tests/test_<module>.py` before implementing. Tests must be fast, offline, and use real fixture data where possible.
- **Prefer reading local files over network calls.** All data sources are already downloaded — exhaust local sources before going online.
- **Clarify, don't assume.** If a request is ambiguous, ask before implementing. If referencing an API, data format, or external resource, verify the actual structure first (read a sample file, check the real response) — do not assume the spec or docs are accurate without confirming against real data.

---

## File structure

```
jlpt_vocab/                 — importable Python package (library code)
  __init__.py
  pipeline.py               — core pipeline logic (constants, Ollama, repair helpers)
  dictionary.py             — Jitendex + JMdict index builders
  pitch_accent.py           — Kanjium + NHK + OJAD pitch accent lookup
  download.py               — auto-download data sources on first run
  furigana.py               — bracket-to-ruby conversion and normalisation
  normalise.py              — word normalisation for chadmuro entries
  csv_utils.py              — checkpoint + CSV row-removal utilities

scripts/                    — CLI entry points (run with python scripts/<name>.py)
  build.py                  — main pipeline
  generate_svgs.py          — SVG diagram generator (run after CSV is complete)
  add_language.py           — retrofit a finished CSV with a new language
  add_words.py              — append arbitrary words to a CSV
  drop_words.py             — remove words from CSV and checkpoint
  dedup_words.py            — remove duplicate rows from a concatenated CSV
  fix_furigana.py           — fix malformed bracket-notation furigana in a word file

tests/
  test_build_pipeline.py
  test_dictionary.py
  test_pitch_accent.py
  test_furigana.py
  test_normalise.py
  test_download.py
  test_add_language_columns.py
  test_add_words.py
  test_drop_words.py

data/                       — gitignored; auto-downloaded on first run
  jitendex-yomitan/         — Jitendex (English glosses + POS + example sentences)
    term_bank_*.json        — 216 files; yomitan term bank format
  JMdict_french/            — JMdict French (French glosses)
    term_bank_*.json
  JMdict_{lang}/            — Other language glosses (spanish, german, dutch, russian, swedish)
  nhk_data/
    ACCDB_unicode.csv       — NHK pitch accent data
  accents.txt               — Kanjium pitch accent data

output/                     — gitignored; all generated files land here
  jlpt_vocab.csv            — concatenated output
  n4.csv, n3.csv, ...       — per-level outputs
  *_checkpoint.json         — resume state
  pitch_svgs/               — generated SVG files
```

---

## Data sources (all downloaded locally — read files first, no network needed)

| Source | Local path | Used for |
|---|---|---|
| Jitendex (yomitan) | `data/jitendex-yomitan/term_bank_*.json` | EN glosses, POS, example sentences |
| JMdict (any lang) | `data/JMdict_{lang}/term_bank_*.json` | Language glosses |
| Kanjium accents | `data/accents.txt` | Pitch accent (primary) |
| NHK CSV | `data/nhk_data/ACCDB_unicode.csv` | Pitch accent (fallback) |
| OJAD API | https://www.ojad.jp/api/v0/words | Pitch accent (last resort only) |
| chadmuro vocab | fetched from GitHub | Word list (N4–N1) |
| Ollama (local LLM) | localhost | Sentence generation, language translation, furigana |

---

## Yomitan term bank format

Each entry is a positional array — **index positions matter**:

```
[term, reading, def_tags, rules, popularity, definitions, sequence, term_tags]
  [0]    [1]      [2]       [3]      [4]          [5]         [6]       [7]
```

- `popularity` (index 4): higher = more common; **always keep the highest-popularity entry** per headword
- `definitions` (index 5): structured content for Jitendex; plain string list for JMdict French

**Jitendex `def_tags` (index 2):** Contains form/variant labels, NOT JMDict POS codes. Common values: `"★ priority form"` (canonical spelling, keep), `"rarely used form"`, `"old kanji form"` (variants, usually no glosses). Do NOT filter by `def_tags` — rely on the empty-glosses check to skip entries with no content.

**Jitendex POS:** Lives in the **structured content**, not `def_tags`. Find `span` nodes where `data.content == "part-of-speech-info"` and read `data.code` (e.g. `"vt"`, `"adj-i"`).

**Jitendex gloss extraction:** Traverse the structured content tree. Extract text from `ul` nodes where `data.content == "glossary"`. Do not descend into nodes where `data.content` is any of: `extra-info`, `attribution`, `xref`, `xref-content`, `xref-glossary`, `info-gloss`, `refGlosses`, `references`, `notes`, `formsTable`.

**Jitendex example sentences:** Located in `div` nodes where `data.content == "example-sentence"` (inside `extra-info` boxes). Two children:
- `data.content == "example-sentence-a"`: Japanese sentence as nested ruby elements — extract text skipping `rt` tags
- `data.content == "example-sentence-b"`: contains a `span` with `lang == "en"` holding the English translation

**JMdict French `def_tags` (index 2):** IS the POS code (e.g. `"n"`, `"v5u"`).

**JMdict French glosses:** `definitions` (index 5) is a plain list of strings — join with `"; "`.

---

## POS tag → 品詞 mapping

Check tags in this order — `vt` before `vi` before other verb tags (avoid substring false matches):

```
vt → 他動詞      vi → 自動詞      v1 → 一段動詞
v5u → 五段動詞（う）  v5k → 五段動詞（く）  v5g → 五段動詞（ぐ）
v5s → 五段動詞（す）  v5t → 五段動詞（つ）  v5n → 五段動詞（ぬ）
v5b → 五段動詞（ぶ）  v5m → 五段動詞（む）  v5r → 五段動詞（る）
vk → カ変動詞    vs-i → サ変動詞（する）
adj-i → い形容詞  adj-na → な形容詞  adj-no → の形容詞
n → 名詞   adv → 副詞   prt → 助詞   conj → 接続詞
pn → 代名詞  int → 感動詞  exp → 表現  suf → 接尾語  pref → 接頭語
```

---

## Word normalisation

Words from chadmuro may contain parenthesised content:

- **Prefix parens** `（ご）主人` → try `ご主人` first, then `主人`; strip parens for bare form
- **Suffix parens** `残念（な）`, `勉強（する）` → strip to get bare form (`残念`, `勉強`); infer POS: `な` → `な形容詞`, `する` → `サ変動詞`, `の` → `の形容詞`

`lookup_forms` is always a list. Try each form in order; use first match.

---

## Furigana format

**Word furigana** — convert bracket notation from chadmuro to ruby HTML:
- `食[た]べる` → `<ruby>食<rt>た</rt></ruby>べる`
- `（ご） 主[しゅ] 人[じん]` → `（ご）<ruby>主<rt>しゅ</rt></ruby><ruby>人<rt>じん</rt></ruby>`
- Base group must start with a CJK character (prevents absorbing preceding particles)
- Collapse spaces between adjacent ruby blocks and before ruby blocks

**Sentence furigana normalisation** — always post-process Ollama output through `normalise_furigana()`:
1. Strip redundant ruby where base is pure kana/katakana
2. Strip paren/bracket readings on pure katakana words
3. Convert `漢字(かな)` → `<ruby>漢字<rt>かな</rt></ruby>` (halfwidth, fullwidth, bracket variants)
- Never add furigana to katakana or hiragana
- Base must start with a CJK character

---

## Pitch accent lookup order

1. **Kanjium `accents.txt`** (primary, local) — tab-separated: `expression\treading\tpitch_pattern`. Keep only the first entry per expression (most common reading). Index by both expression and reading.
2. **NHK `nhk_data/ACCDB_unicode.csv`** (fallback, local) — index by cols 5 (midashigo), 7 (kanjiexpr), 6 (nhk reading); pitch pattern in col 18 (ac).
3. **OJAD API** (last resort, online only) — `https://www.ojad.jp/api/v0/words?limit=5&word={word}`

**SVG filename:** `{mora_count}_{pattern}.svg` (e.g. `3_2.svg`). Unknown → `unknown.svg`.

---

## Sentence verification (fugashi)

When a sentence comes from Jitendex, verify the word appears as a morphological token — not just a substring:

```python
for token in tagger(sentence):
    lemma = token.feature.lemma or token.surface
    if lemma == word or token.surface == word:
        return True
return False
```

This prevents e.g. `夫` matching inside `大丈夫`.

---

## Ollama usage

- Strip markdown fences before parsing JSON responses
- Log failures and continue (words with empty fields can be retried with `--resume`)
- Always run `normalise_furigana()` on `例文振り仮名` output regardless of how clean it looks
- Two prompt modes: full generation (no Jitendex sentence) and partial (Jitendex sentence found, need translations + furigana) — see `jlpt_vocab/pipeline.py:ollama_generate` for exact prompt text

---

## Running the pipeline

```bash
source venv/bin/activate

# Full run (English only, default)
python scripts/build.py --model gemma4:e4b

# Add extra languages alongside English
python scripts/build.py --model gemma4:e4b --languages french
python scripts/build.py --model gemma4:e4b --languages french spanish german

# Subset of levels
python scripts/build.py --model gemma4:e4b --levels n4 n3

# Resume after crash (languages auto-detected from the existing CSV)
python scripts/build.py --model gemma4:e4b --resume

# Repair rows with empty Ollama-generated fields
python scripts/build.py --model gemma4:e4b --output output/n4.csv --repair

# Add a language to a finished CSV
python scripts/add_language.py --language german --output output/n4.csv --model gemma4:e4b

# Deduplicate a concatenated CSV (keeps first occurrence per word+furigana pair)
python scripts/dedup_words.py --output output/jlpt_vocab.csv
python scripts/dedup_words.py --output output/jlpt_vocab.csv --dry-run  # preview only

# Add custom words outside the JLPT list
python scripts/add_words.py 猫背 蹴る --model gemma4:e4b
python scripts/add_words.py 猫背 --output output/n4.csv --model gemma4:e4b
python scripts/add_words.py --file my_words.txt --model gemma4:e4b
python scripts/add_words.py 納豆 --file my_words.txt --model gemma4:e4b  # combined; file words first, deduped

# Generate SVGs (after CSV is complete)
python scripts/generate_svgs.py
```

### Parallel runs (one level per terminal)

Each instance needs its own `--output` flag so it gets an isolated checkpoint file:

```bash
python scripts/build.py --model gemma4:e4b --levels n4 --output output/n4.csv
python scripts/build.py --model gemma4:e4b --levels n3 --output output/n3.csv
python scripts/build.py --model gemma4:e4b --levels n2 --output output/n2.csv
python scripts/build.py --model gemma4:e4b --levels n1 --output output/n1.csv
```

After all finish, concatenate then deduplicate (use a loop — BSD tail on macOS adds separators with multiple files):

```bash
head -1 output/n4.csv > output/jlpt_vocab.csv
for f in output/n4.csv output/n3.csv output/n2.csv output/n1.csv; do tail -n +2 "$f"; done >> output/jlpt_vocab.csv

python scripts/dedup_words.py --output output/jlpt_vocab.csv
```

## Running tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

---

## Key gotchas

- **JMdict French term banks** start at `term_bank_2.json` (no `term_bank_1.json`)
- **Jitendex popularity** field (index 4) may be negative — higher (less negative) = more common
- **`forms` entries** in Jitendex contain no glosses and must be skipped before any processing
- **POS tags:** strip leading sense number from `def_tags` before splitting (e.g. `"1 v5u vt"` → `"v5u vt"`)
- **OJAD rate limit:** add a short sleep between requests; handle failures silently
- **Kanjium** is the primary pitch source, not OJAD — only call OJAD if both local files fail
- **CSV incremental write:** flush after every row; save checkpoint after every word

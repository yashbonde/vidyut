# Test data

## `rv_let_corpus.tsv` — present-stem leṬ (लट्-stem)

826 present-stem subjunctive (leṬ) forms from the Rigveda, filtered from
Oliver Hellwig's morpho-lexical annotation of the Rigveda.

- **Tag filtered:** `tense_mode = "Present conjunctive (subjunctive)"`

## `rv_let_aorist_corpus.tsv` — aorist-stem leṬ (लुङ्-stem)

605 aorist-stem subjunctive forms from the Rigveda. Used for the Phase 4
implementation track (leṬ built on the aorist stem, distinct from the
present-stem leṬ in `rv_let_corpus.tsv`).

- **Tag filtered:** `tense_mode = "Aorist conj./subj."`

## `rv_let_perfect_corpus.tsv` — perfect-stem leṬ (लिट्-stem)

182 perfect-stem subjunctive forms from the Rigveda. Used for the Phase 5
implementation track (leṬ built on the perfect/reduplicated stem).

- **Tag filtered:** `tense_mode = "Perfect conjunctive (subj.)"`

## Source and license

- **Source:** Hellwig, O., Hettrich, H., Modi, A., Pinkal, M. (2018).
  *Multi-layer Annotation of the Rigveda.* LREC 2018.
  Repository: <https://github.com/OliverHellwig/sanskrit>
- **License:** CC BY 4.0

### Columns (same for all three TSVs)

| Column | Meaning |
|---|---|
| `ref` | maṇḍala.sūkta.ṛc.pāda (e.g., `1.166.14.2` = RV 1.166.14, line 2 = pādas c+d) |
| `pos` | word position within the line |
| `word` | surface form (IAST) |
| `surface_form` | canonical surface form (IAST, same as `word` for most rows) |
| `lemma` | dictionary lemma (IAST) |
| `root`, `prefixes` | usually empty |
| `person` | 1 / 2 / 3 |
| `number` | 1 (sg) / 2 (du) / 3 (pl) |
| `tense_mode` | matches the per-TSV filter above |

### Used by

- `tests/integration/rv_let_corpus.rs` — लट्-stem (active baseline, ~83% match)
- `tests/integration/rv_let_aorist_corpus.rs` — लुङ्-stem (Phase 4 scaffold; currently expected to fail until `Tinanta::let_stem(LetStem::Lun)` is implemented)
- `tests/integration/rv_let_perfect_corpus.rs` — लिट्-stem (Phase 5 scaffold; currently expected to fail until `Tinanta::let_stem(LetStem::Lit)` is implemented)

Each test reads its TSV, derives each form via vidyut, and asserts the
corpus `surface_form` appears in vidyut's output. Failures are listed all
at once in the test output.

## `dcs_tinanta_corpus.tsv`: finite verbs from the DCS

9,000 attested finite verb forms from the Digital Corpus of Sanskrit that
vidyut-prakriya derives, written by
`scripts/check_dcs_tinanta_coverage.py --sample-tsv`. The script keeps the
most frequent covered item for each (dhatu, lakara, prayoga, prefixes,
sanadi) combination, in order of corpus frequency. See
`scripts/dcs_tinanta_report.md` for the method and the full numbers.

- **Source:** Hellwig, O. (2010 to 2024). *The Digital Corpus of Sanskrit
  (DCS).* CoNLL-U dump at <https://github.com/OliverHellwig/sanskrit>
  (`dcs/data/conllu`, commit 8aeed5a1, 2026-08-24).
- **License:** CC BY 4.0

### Columns

The first ten columns follow the RV files above. The rest say how vidyut
derives the form, so a test can rebuild the `Tinanta` directly.

| Column | Meaning |
|---|---|
| `ref` | DCS chapter citation of the first occurrence (e.g. `AgniPur, 2`) |
| `sent_id` | DCS sentence id of that occurrence |
| `pos` | word position within the sentence |
| `word` | surface form in the text (IAST, may show sandhi) |
| `surface_form` | DCS unsandhied form (IAST), or `word` if DCS has none |
| `lemma` | DCS lemma (IAST), with preverbs folded in (e.g. `uddhṛ`) |
| `root` | root part of the lemma after removing the preverbs (IAST) |
| `prefixes` | upasargas and gatis as vidyut names, comma separated (`pra,AN`) |
| `person` | 1 / 2 / 3 |
| `number` | 1 (sg) / 2 (du) / 3 (pl) |
| `tense_mode` | DCS `Tense`, `Mood` and `Formation` features |
| `voice` | DCS `Voice` (`Pass` or empty) |
| `count` | tokens of this item in the corpus |
| `dhatu_code` | code in `data/dhatupatha.tsv` |
| `aupadeshika`, `gana` | the dhatu as passed to vidyut |
| `sanadi` | sanadi pratyaya, if any (`Ric`, `san`, `yaN`) |
| `lakara`, `prayoga` | the lakara and prayoga that produce the form |
| `skip_at_agama` | 1 if derived without the aT/At agama (injunctive) |
| `vidyut_form` | the matching vidyut output (SLP1) |

The dhatu given is the first one (by code) that produces the form. For a
homophonous form that can be a different root from the one the text
means (`Aha` matches the perfect of `aha~` before the laT of `brUY`), so
treat these rows as "vidyut can produce this string for this tag", not as
a gold lemmatization. vidyut was run with its default pada behavior and
without chandasa rules.

Not used by a Rust test yet. It is meant as regression data: every row is
a form the current engine produces.

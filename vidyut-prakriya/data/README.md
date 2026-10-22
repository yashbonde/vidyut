Data
====

We have designed `vidyut-prakriya` so that it can run without any side data.
But in practice, it is useful to have side data available to generate words
and show the text of specific rules.

Most of the data files here were sourced from from [ashtadhyayi.com][a-com],
and the author of ashtadhyayi.com has graciously agreed to share thse files
with us under an MIT license.

[a-com]: https://ashtadhyayi.com


`dhatupatha.tsv`
----------------

`dhatupatha.tsv` is a comprehensive Dhatupatha that we also use in our
exhaustive test suite.

This dhatupatha is a superset of traditional dhatupathas from five different
sources:

- the *Siddhāntakaumudī*
- the *Bṛhaddhātukusumākaraḥ*
- the *Mādhavīyadhātuvṛttiḥ*
- the *Kṣīrataraṅgiṇī*
- the *Dhātupradīpaḥ*

The source data is [available on Github][dhatupatha-json] as a JSON file. To
create `dhatupatha.tsv`, we downloaded this file and made the following changes:

1. First, we converted the original JSON file to a TSV file with three columns.
   For our current needs, these fields are sufficient.

2. Next, we added svaras to the dhatus in this list. Many of the dhatus here
   overlap with the dhatus used in [SanskritVerb][sanskrit-verb], a PHP-based
   Paninian generator that heavily inspired `vidyut-prakriya`. Where we could
   find an overlap, we used the svaras provided by SanskritVerb. Otherwise, we
   added svaras through a simple mechanical procedure: *aniṭ* roots have
   *anudātta* on the root vowel, *ātmanepadī* roots without *ṅit* are
   *anudāttet*, and *ubhayapadī* roots without *ñit* are *svaritet*.

3. Finally, we made a few corrections to the dhatus in this list. The original
   JSON file will likely be updated with these corrections, so we have omitted
   the details for now.

[dhatupatha-json]: https://github.com/ashtadhyayi-com/data/blob/master/dhatu/data.txt
[sanskrit-verb]: https://github.com/drdhaval2785/SanskritVerb


`dhatupatha-metadata.tsv`
-------------------------

`dhatupatha-metadata.tsv` adds an English meaning and a corpus frequency to
each dhatu in `dhatupatha.tsv`. It has one row per dhatu (the 30 `-` rows of
`dhatupatha.tsv` are left out) and is keyed by the same `code`.
`dhatupatha.tsv` itself is unchanged. The file has the following columns:

- `code`, the code of the dhatu in `dhatupatha.tsv` (e.g. `08.0010`).
- `artha_en`, an English meaning (e.g. `to do, to act, to make`).
- `dcs_count`, the number of tokens of this dhatu in the Digital Corpus of
  Sanskrit (DCS), including its prefixed forms. Shares of split tokens are
  rounded to the nearest integer.
- `dcs_count_prefixed`, the part of `dcs_count` that comes from verbs with
  preverbs (e.g. `uddhṛ` counts toward `hṛ`).
- `dcs_count_estimated`, the part of `dcs_count` whose assignment to this
  entry is an estimate (see below).
- `dcs_assign`, how the count was assigned. If an entry gets tokens in
  several ways, this column shows the least certain one:
  - `exact`: no other entry has the same root.
  - `meaning`: other entries have the same root (homonyms), and the DCS
    dictionary meaning matched this entry's English meaning best.
  - `estimated`: the meaning did not decide between homonyms. The tokens of
    a prefixed verb follow the split of its unprefixed base. Otherwise they
    go to the homonyms that ashtadhyayi.com tags as `common`, and if that
    does not decide either, they are split evenly.
  - `none`: no DCS token was assigned to this entry.

The counts are meant for ranking (for example, to show `kṛ` "to do" before
`kṛ` "to kill" in search results), not as exact statistics. Some caveats:

- Only verb tokens are counted: finite forms, participles, infinitives and
  absolutives, which DCS lemmatizes under the verb. Derived nouns and
  adjectives (`kartṛ`, `karman`) are separate lemmas in DCS and are not
  counted, because we cannot map them back to a root reliably.
- Causatives that DCS lists as separate lemmas (`kāray`, `darśay`) are not
  counted. A DCS lemma in `-ay` counts only when it matches a curadi root
  (`kathay`, `pūjay`).
- DCS gana labels are not used. For the unprefixed DCS verbs that match
  exactly one entry, the DCS label names a different gana for about a third
  of them (DCS lists the main `kṛ` as class 2, for example).
- With the DCS commit below, 92% of verb tokens are assigned to an entry, 8%
  are causatives, and under 1% match no entry. 869 of the 2,229 dhatus have
  a nonzero count.

### Sources

- English meanings come from the `artha_english` field of the ashtadhyayi.com
  dhatu data ([`dhatu/data.txt`][dhatupatha-json], last changed in commit
  `94bef12`, 2026-05-16), matched on `code` (`baseindex` in that file).
  The data is shared under the terms described at the top of this file. The
  ashtadhyayi.com data repository also states:
  "You are free to use this data in your own projects provided that
  appropriate credits are mentioned wherever applicable." Credit:
  [ashtadhyayi.com][a-com]. Its plain roots and its `common` tag are also used
  to match corpus lemmas.
- Corpus counts come from the CoNLL-U dump of the [Digital Corpus of
  Sanskrit][dcs] by Oliver Hellwig, licensed under [CC BY 4.0][cc-by]. The
  counts in this file were derived from commit `8aeed5a` (2026-08-24) of
  <https://github.com/OliverHellwig/sanskrit>. If you use these counts, please
  cite: Oliver Hellwig, *The Digital Corpus of Sanskrit (DCS)*, 2010-2024.

### How to rebuild

`scripts/create_dhatupatha_metadata.py` builds this file from the two public
sources. Its docstring describes the matching rules in detail. The output is
deterministic for fixed inputs.

```
# Download the sources somewhere outside the repository.
curl -L -o /tmp/data.txt https://raw.githubusercontent.com/ashtadhyayi-com/data/master/dhatu/data.txt
git clone --depth=1 https://github.com/OliverHellwig/sanskrit.git /tmp/sanskrit

cd scripts
uv run create_dhatupatha_metadata.py \
    --ashtadhyayi-dhatus /tmp/data.txt \
    --dcs-conllu /tmp/sanskrit/dcs/data/conllu \
    --output ../data/dhatupatha-metadata.tsv
```

[dcs]: https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/conllu
[cc-by]: https://creativecommons.org/licenses/by/4.0/


Sutra files
-----------

Our sutras are split into the following 5 files:

- `dhatupatha-ganasutras.tsv` contains gana-sutras from the Dhatupatha.
- `linganushasanam.tsv` contains sutras from the Linganushasanam.
- `phit-sutras.tsv` contains sutras from the Phit Sutras.
- `sutrapatha.tsv` contains the Ashtadhyayi.
- `unadipatha.tsv` contains the Unadipatha.

All sutra files are 2-column TSV files with the following columns:

- `code`, a short identifier for this sutra.
- `text`, the sutra text encoded in SLP1.

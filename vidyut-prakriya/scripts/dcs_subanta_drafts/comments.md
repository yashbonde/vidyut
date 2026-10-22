# Comment drafts for open subanta issues (not posted)

Each comment adds evidence from the Digital Corpus of Sanskrit (DCS, Oliver
Hellwig, CC BY 4.0, commit 8aeed5a) as measured by
`vidyut-prakriya/scripts/check_dcs_subanta_coverage.py`, with the
vidyut-prakriya WASM build served by the vidyut demo (Last-Modified
2026-10-17). Counts are DCS tokens; "cells" are the slots the issue names.

---

## #255 (palatal-sibilant stems)

Corpus data agrees. In the DCS, 1,429 tokens fall in the affected cells of
-ś stems; the current WASM build derives 481 of them and misses 835 because of
the k/ṭ problem: `dikṣu` 367 (vidyut `diwsu`/`diwtsu`), `digbhyaḥ` 118,
`vikṣu` 65, `digbhiḥ` 30, `dik`/`dig` 44, and the kvin stems `tādṛk`/`tādṛg`,
`yādṛg` (vidyut `tAdfw`/`tAdfq`). There are no attestations of the `diw` type.

## #256 (bare -at/-ant stems)

Corpus data agrees, and the scope is wider than -ant. 664 DCS tokens miss in
the affected cells of -at stems with `basic` (`arhantaḥ` 77, `bṛhantam` 63,
`bṛhantaḥ` 20, `arhantam` 25). The same limitation hits every stem whose declension
depends on an anubandha: with `basic`, the nominative of `Bagavat`,
`SrImat`, `DImat`, `Bavat`, `vidvas` and the -īyas comparatives has no num.
In the DCS 22,665 tokens are derived only when the stem is passed as a
kṛdanta or taddhitanta (`bhagavān` 3,600 alone, `bhavān` 1,306, `śrīmān` 626,
`vīryavān` 615, `vidvān` 287). If `basic` is meant to stay underived, a note
in the docs pointing to `taddhitanta(..., matup)`, `krdanta(BA, Unadi.qavatu)`
and so on would help corpus users a lot. Separately, `mahat` cannot reach
`mahAn` even as a kṛdanta (draft issue, about 1,800 tokens).

## #257 (neuter i-stems)

The accusative plural part looks fixed in the current WASM build
(`vArIRi`; 0.4.0 still gives `vAriRi`). The akṣi/asthi/dadhi/sakthi part is
confirmed: 113 DCS tokens in the cells you list (`asthiṣu` 16, `asthibhiḥ` 15,
`asthnām` 23, `akṣibhyām` and `akṣībhyām` 28, `akṣibhiḥ` 6, `akṣiṣu` 5,
`akṣṇām` 4, `dadhibhiḥ` 3), all missed; vidyut gives `asTasu`, `asTaBiH`, `asTInAm`,
`akzaByAm`.

## #258 (-in stems)

The neuter accusative plural is fixed in the current WASM build (`balIni`).
The feminine defect is confirmed, but the DCS rarely shows it because it
lemmatizes these feminines as -inī: 13 missed tokens (`svairiṇyām`,
`rūpiṇyām`, `garbhiṇīnām`). The locative singular defect is not specific to
-in: every basic stem that vidyut feminizes with ṅīp or ṅīṣ gets `-yE`
(`basic("sundara")`, Stri, Saptami gives `sundaryE`; DCS `kadalyām`,
`maṅgalyām`, `mahatyām`, `yoginyām`, 54 more tokens that only an explicit
`nyap` stem derives).

## #259 (numerals)

Supporting data: in the DCS, tri and catur occur only in the plural. The few
tokens tagged singular are `catuḥ` "four times" (suc) and sutra citations in
the Aṣṭādhyāyī, so the singular and dual cells have no real attestations.

## #260 (-is/-us ruki)

Confirmed, and it is the largest open issue in the DCS: 6,216 missed tokens
(`cakṣuṣā` 498, `haviṣā` 409, `yajuṣā` 294, `sarpiṣā` 250, `āyuṣā` 200,
`haviṣaḥ` 162, `vapuṣā` 158, `jyotiṣā` 155, `barhiṣi` 145, `dhanuṣā` 88).
The same root cause affects -iṣmat/-uṣmat stems built from these
(`āyuṣmān` 389, `āyuṣmantam` 159, `cakṣuṣmān`, `jyotiṣmatī`), including the
taddhitanta input `taddhitanta(basic("cakzus"), matup)`, which gives
`cakzusmAn`.

## #261 (bare -ṛ agent nouns)

Confirmed: 2,599 missed tokens. One correction to the report: the
accusative singular is affected too, and it is the largest cell in the
corpus (`bhartāram` 327, `savitāram` 117, `kartāram` 93, `udgātāram` 59,
`dātāram` 50, `tvaṣṭāram` 45). Both the current WASM build and 0.4.0 give
`dAtaram`, `Bartaram`.

## #271 (-mat/-mant weak cells)

Not reproduced with the corpus. The DCS has 4,724 tokens in the five cells;
the current WASM build derives 4,670 (98.9%) with `basic`, and the 6 misses
are Vedic `-ante` datives. `basic("DImat")` gives `DImate`, `DImataH`,
`DImatAm`, `DImati` in the WASM build and in 0.4.0. Could the report have
used a stem spelled `DImant`?

## #250 (eka not sarvadi)

Looks fixed in the current WASM build: `ekasmin`, `ekasmE`, `ekasmAt`,
`ekasyAH`, `ekasyAm` are derived. The DCS has 678 tokens in eka's oblique
singular cells and 660 of them are derived; the other 18 are Vedic or epic
non-pronominal forms (`eke` as a locative, `ekāt`).

## #247 (-aka feminines in -ikā)

Confirmed: 209 DCS tokens (119 types) are -ikā feminines of DCS -aka
lemmas that vidyut gives as -akā, for example `paramikām` 15, `ātmikā` 12,
`pūrvikām` 7, `sādhikā` 5, `dāyikā` 4, `lavaṇikā`, `māmikā`.

## #229 (alpa feminine)

Supporting data: all 58 feminine tokens of `alpa` in the DCS are ṭāp forms
(`alpā`, `alpām`, `alpayā`), which vidyut-prakriya derives; no `alpī` is
attested. The problem is only in the generated stem list.

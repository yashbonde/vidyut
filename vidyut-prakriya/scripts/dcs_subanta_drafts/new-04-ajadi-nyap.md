# `nyap` stems of the ajādi gaṇa get a second ṭāp (`ajAyA`, `vatsE`)

**Draft, not posted.**

## Summary

`Pratipadika.nyap("ajA")` declines as if a second ṭāp were added:

| cell | `nyap("ajA")` | `nyap("ramA")` | expected for ajA |
|---|---|---|---|
| instr. sg. | `ajAyA` | `ramayA` | `ajayA` |
| gen./loc. du. | `ajAyoH` | `ramayoH` | `ajayoH` |
| voc. sg. | `ajE` | `rame` | `aje` |

The same happens for every gaṇa member that a user would pass as nyap:
`aSvA`, `bAlA`, `vatsA`, `kokilA`, `mUzikA`, `jyezWA`, `kanizWA`, `maDyamA`,
`uzRihA`. `Pratipadika.basic("aja")` with `Linga.Stri` is correct.
Seen in the 2026-10-17 WASM build and in vidyut 0.4.0.

## Reproduce

```python
from vidyut.prakriya import Vyakarana, Pada, Pratipadika, Linga, Vibhakti, Vacana

v = Vyakarana()
for stem in ("ajA", "vatsA", "ramA"):
    for vibhakti, vacana in [(Vibhakti.Trtiya, Vacana.Eka), (Vibhakti.Sambodhana, Vacana.Eka)]:
        pada = Pada.Subanta(pratipadika=Pratipadika.nyap(stem), linga=Linga.Stri,
                            vibhakti=vibhakti, vacana=vacana)
        print(stem, vibhakti, sorted({p.text for p in v.derive(pada)}))
```

## Cause

In `stritva.rs`, the base case is

```rust
if last.has_text_in(gana::AJADI) || last.has_antya('a') {
    sp.try_add("4.1.4", wAp);
}
```

and `gana::AJADI` lists the feminine forms (`ajA`, `vatsA`, `jyezWA`, ...).
A nyap stem already carries the dummy ṭāp term from
`pratipadika_karya::add_basic`, but its text still matches the gaṇa, so a
second ṭāp is inserted. Skipping `stritva::run` when the pratipadika is
`StriNyap` (or matching the gaṇa only for non-nyap stems) should fix it.

## Grammar

- 4.1.4 *ajādyataṣ ṭāp*: SK 454 "अजा".
- The ā-stem paradigm: 7.3.105 *āṅi cāpaḥ*, SK 289 "रमया"; vocative
  "हे रमे" (7.3.106).

## Corpus evidence (DCS, Oliver Hellwig, CC BY 4.0)

83 tokens: `vatse` 33 (DKCar 2.6, sent 489018), `ajayā` 15 (BaudhŚS 6.15,
sent 682978), `bāle` 7 (AmaruŚ 1), `bālayā` 4 (MBh 3.122), `jyeṣṭhayā`,
`kaniṣṭhayā`, `madhyamayā` 4 each, `aśvayā`, `kokilayā`, `mūṣikayā`.

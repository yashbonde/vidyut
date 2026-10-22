# `mahat` as a kṛdanta gives `mahan`, not `mahAn` (6.4.10 not reached without `require`)

**Draft, not posted.** Related to #256 (bare -at/-ant stems), but this is the
kṛdanta input that the tests use, not the basic one.

## Summary

There is no public input that gives `mahAn`, `mahAntam`, `mahAntaH`:

- `Pratipadika.basic("mahat")` gives `mahat` (no num; the #256 limitation).
- `Pratipadika.krdanta(Dhatu.mula("maha~", Gana.Bhvadi), Unadi.ati)` gives
  `mahan`, `mahantO`, `mahantaH`, `mahantam`: num is added but 6.4.10 does not
  lengthen the vowel.

The integration test `sutra_6_4_10` in `tests/integration/kashika_6_4.rs`
expects `mahAn` and passes, but it builds the stem with
`create_krdanta("mahat", ...)`, which sets `.require("mahat")`.

## Reproduce

```python
from vidyut.prakriya import (Vyakarana, Pada, Pratipadika, Dhatu, Gana, Unadi,
                             Linga, Vibhakti, Vacana)

v = Vyakarana()
mahat = Pratipadika.krdanta(Dhatu.mula("maha~", Gana.Bhvadi), Unadi.ati)
for vacana in (Vacana.Eka, Vacana.Dvi, Vacana.Bahu):
    pada = Pada.Subanta(pratipadika=mahat, linga=Linga.Pum, vibhakti=Vibhakti.Prathama, vacana=vacana)
    print(vacana, sorted({p.text for p in v.derive(pada)}))
```

WASM, same input: `{"krdanta": {"dhatu": {"aupadeshika": "maha~", "gana":
"Bhvadi", ...}, "krt": null, "unadi": "ati"}}` gives `mahan`.

## Likely cause

The derivation without `require` adds the kṛt and the sup in one prakriya.
Because of *śatṛvac ca*, 3.1.68 inserts śap between `mah` and `at`
(`mah a at s`). When 6.4.10 runs in `angasya/subanta.rs`, the check is
`p.view(0, i_anga)?.has_text("mahant")`, but the terms still read
`mah` + `a` + `ant` (6.1.97 has not merged them yet), so the rule does not
fire. With `require`, `prepare_pratipadika_inner` derives `mahat` completely
first and then adds the sup, which is why the test passes. Neither the WASM
API nor the Python bindings can set `require`.

## Grammar

- Uṇādi *vartamāne pṛṣadbṛhanmahajjagacchatṛvac ca*: SK "उगित्त्वान्नुम् ।
  सान्तमहत इति दीर्घः ... महान् । महान्तौ । महान्तः".
- 6.4.10 *sāntamahataḥ saṃyogasya* (SK 317).

## Corpus evidence (DCS, Oliver Hellwig, CC BY 4.0)

1,801 tokens: `mahān` 1,573 (for example ACint 2, sent 506384), `mahāntam`
167, `mahāntaḥ` 50, duals 11. Most are in epic and puranic texts (1,201
tokens), then classical (289) and Vedic (237).

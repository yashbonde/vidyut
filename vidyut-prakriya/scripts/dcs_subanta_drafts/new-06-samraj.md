# `samrAj`: 8.3.25 *mo rāji samaḥ kvau* not applied (`saMrAw`)

**Draft, not posted.** Low frequency, but the rule is unambiguous.

## Summary

`Pratipadika.krdanta(Dhatu.mula("rAjf~^", Gana.Bhvadi).with_prefixes(["sam"]), Krt.kvip)`
gives `saMrAw`/`saMrAq`, `saMrAjO`, `saMrAjaH` with anusvara. 8.3.25 keeps the
m of sam before kvip-final rāj: `samrAw`, `samrAjO`. Seen in the 2026-10-17
WASM build and in vidyut 0.4.0.

## Reproduce

```python
from vidyut.prakriya import Vyakarana, Pada, Pratipadika, Dhatu, Gana, Krt, Linga, Vibhakti, Vacana

v = Vyakarana()
samraj = Pratipadika.krdanta(Dhatu.mula("rAjf~^", Gana.Bhvadi).with_prefixes(["sam"]), Krt.kvip)
pada = Pada.Subanta(pratipadika=samraj, linga=Linga.Pum, vibhakti=Vibhakti.Prathama, vacana=Vacana.Eka)
print(sorted({p.text for p in v.derive(pada)}))  # expected samrAw, samrAq
```

## Grammar

SK 126, 8.3.25: "क्विबन्ते राजतौ परे समो मस्य म एव स्यात् । सम्राट्". It is an
exception to 8.3.23 *mo 'nusvāraḥ*.

## Corpus evidence (DCS, Oliver Hellwig, CC BY 4.0)

42 tokens: `samrāṭ`/`samrāḍ` 30 (AgniPur 18, sent 484650; BhāgPur 3.22,
sent 91594), Vedic `samrājā` 9.

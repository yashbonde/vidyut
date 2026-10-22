# Issue drafts from the DCS tinanta check

Drafts only, not filed. One section per issue. See `dcs_tinanta_report.md`
for the method and the evidence behind each one.

---

## [prakriya] 8.3.102 missing: nis + tap gives nistapati

निस् + तप् + लट् (प्र॰ पु॰ एक॰) should be निष्टपति, not nistapati as
currently.

8.3.102 निसस्तपतावनासेवने makes the s of nis retroflex before tap when the
action is not repeated (anāsevana). From the Siddhāntakaumudī (SK 2403):

> निसस्तपतावनासेवने । षः स्यात् । आसेवनं पौनः पुन्यं ... । निष्टपति ।

Current output (same in 0.4.0 and in the current web build), for every tap
entry (01.1140, 04.0054, 10.0350) with `nis` or `nir`:

```
nis + ta\pa~ (Bhvadi), Lat, prathama eka       -> nistapati
nis + ta\pa~ (Bhvadi), VidhiLin, prathama eka  -> nistapet
nis + ta\pa~ (Bhvadi), Lut, prathama eka       -> nistaptA
```

Expected: nizwapati, nizwapet, nizwaptA.

Attestation in the DCS (all with ṣṭ; there is no tiṅanta in nistap- at all):

- निष्टपति, 12 tokens (e.g. BhārŚS 1.12)
- निष्टपतः 3, निष्टपामि 2, निष्टपेत् 2, निष्टप्ता 2

`src/tripadi/pada_8_3.rs` has 8.3.101 just before the general ṣatva rules,
but no 8.3.102. Since vidyut does not model āsevana, the simplest fix may be
to apply it by default (or as an optional rule, with the repeated sense as
the other branch). kṛdantas (निष्टप्त) are probably affected too; I only checked tiṅantas.

Found while checking tiṅanta output against the Digital Corpus of Sanskrit
(Hellwig, CC BY 4.0).

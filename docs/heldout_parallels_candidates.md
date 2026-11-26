# Held-Out Exclusion Parallels — Lexical & Pada-Level Audit (Tranche 1: GRETIL)

**Method (2026-11-23):** Screened accent-stripped `text_search` of all 17,000 Tranche 1 native
units against the 15 frozen `excluded_units` using three deterministic lexical channels (ranked
strictly by pada/4-gram/stem-cluster match; `mpnet` cosine is informational only):

1. **Exact pada-level matches** — exact hemistich/pada substrings ≥ 22 Devanāgarī chars
   (space-tolerant for Tokunaga/Fushimi word splitting) or exact contiguous spans ≥ 5 words
   (or ≥ 4 words & ≥ 20 Devanāgarī chars).
2. **Shared word 4-grams** on `text_search`.
3. **Orthography/sandhi-tolerant pada quotes** — ≥ 5 distinctive content stems (or ≥ 4 covering
   ≥ 55% of a single excluded verse) clustered inside a 25-word window (catches Nirukta/MS
   quotes with Tokunaga grammatical case-tags like `gaṅgā8`, `स`/`ष` variants, or `म्`/`ं`).

- **Frozen `excluded_units` (15) & `sha256_of_case_file`:** untouched.
- **Total approved in `parallel_units` (Tranche 1):** **20** entries (3 initial + 17 added 2026-11-23).
- **Status:** Tranche 1 screening resolved. Rerun this screen in every later tranche (`JB`, `KS`, `TB`, etc.).

---

## 1. Approved & Added to `parallel_units` in `g2_test_manifest.json` (20 entries)

| Parallel Unit | Excluded Unit(s) | Match type | Cosine (info) | Evidence (`text_search`) |
|---|---|---|---:|---|
| `AVP 7.10` | `AVŚ 19.39`, `AVŚ 5.4` | whole hymn | 0.626–0.941 | Paippalāda kuṣṭha hymn (`AVP 7.10.1–10` parallel to `AVŚ 19.39` & `AVŚ 5.4`) |
| `AVP 1.31` | `AVŚ 5.4` | whole hymn | 0.488–0.822 | Paippalāda kuṣṭha hymn (`AVP 1.31.1–4` parallel to `AVŚ 5.4`) |
| `Nir 10.31` | `RV 4.38` | exact pada | 0.803 | `RV 4.038.10`: आ दधिक्राः शवसा पञ्च कृष्टीः |
| `Nir 9.26` | `RV 10.75` | orth/sandhi quote | 0.891 | `RV 10.075.05`: गङ्गा यमुना सरस्वती शुतुद्री स्तोमम् सचता परुस्न्या… (10/10 stems) |
| `Nir 4.24` | `RV 4.38` | orth/sandhi quote | 0.813 | `RV 4.038.05`: उत स्मैनम् वस्त्रमथि न तायुम् अनु क्रोशन्ति क्षितयो भरेषु… (12/12 stems) |
| `Nir 10.29` | `RV 4.38` | exact span | 0.706 | `RV 4.038.10`: शवसा पञ्च कृष्टीः सूर्य इव (5 contig. words) |
| `Nir 10.24` | `RV 7.96` | exact pada | 0.722 | `RV 7.096.05`: ऊर्मयो मधुमन्तो घृतश्चुतः (5/5 stems) |
| `Nir 6.31` | `RV 1.174` | exact span | 0.889 | `RV 1.174.02`: दनो विश इन्द्र मृध्रवाचः |
| `AVP 19.8.13` | `AVŚ 5.4` | exact span | 0.624 | `AVŚ 5.4.4–5`: अरित्राणि हिरण्यया नावो हिरण्ययीर् आसन् याभिः कुष्ठं |
| `AVP 19.8.14` | `AVŚ 5.4` | exact pada | 0.656 | `AVŚ 5.4.2`: सुपर्णसुवने गिरौ जातं हिमवतस् परि धनैर् |
| `AVP 19.8.15` | `AVŚ 5.4` | exact pada | 0.736 | `AVŚ 5.4.1`: कुष्ठेहि तक्मनाशन तक्मानं नाशयन्न् इतः |
| `AVP 16.28.1` | `AVŚ 19.39` | exact pada | 0.793 | `AVŚ 19.39.4`: उत्तमो अस्य् ओषधीनाम् अनड्वान् जगताम् इव व्याघ्रः श्वपदाम् इव |
| `AVP 20.61.8` | `AVŚ 5.4`, `AVŚ 19.39` | exact pada | 0.682–0.760 | `AVŚ 5.4.3` / `19.39.6`: अश्वत्थो देवसदनस् तृतीयस्याम् इतो दिवि |
| `AVP 15.15.4` | `AVŚ 5.4`, `AVŚ 19.39` | exact span | 0.691–0.755 | `AVŚ 5.4.3` / `19.39.6`: तृतीयस्याम् इतो दिवि तत्रामृतस्य |
| `AVP 20.10.7` | `RV 7.96` | exact pada | 0.696 | `RV 7.096.05`: ऊर्मयो मधुमन्तो घृतश्चुतः (5/5 stems) |
| `MS 4.10.1` | `RV 7.96` | exact pada | 0.914 | `RV 7.096.05`: ये ते सरस्व ऊर्मयो मधुमन्तो घृतश्चुतः |
| `MS 4.12.5` | `RV 8.19` | exact pada | 0.892 | `RV 8.019.19`: भद्रा रातिः सुभग भद्रो अध्वरः |
| `MS 4.13.5` | `ŚB 1.8.1` | exact span | 0.937 | `ŚB 1.8.1`: उपहूते द्यावापृथिवी पूर्वजे ऋतावरी देवी देवपुत्रे |
| `MS 1.4.1` | `ŚB 1.8.1` | orth/sandhi quote | 0.899 | `ŚB 1.8.1.42`: अस्मास्व् इन्द्र इन्द्रियं दधात्व् अस्मान् रायो मघवानः सचन्ताम् अस्माकं सन्त्व् आशिषः |
| `MS 2.4.3` | `ŚB 1.8.1` | orth/sandhi quote | 0.861 | `ŚB 1.8.1.42`: अस्मास्व् इन्द्र इन्द्रियं दधात्व् अस्मान् रायो मघवानः सचन्ताम् अस्माकं सन्त्व् आशिषः |

---

## 2. Reviewed — Formulaic (Not Added to `parallel_units`)

Owner ruling (2026-11-23): all entries below were reviewed and classified as **reviewed — formulaic** (generic refrains, short healing/ritual formulas, or deity/meter lists) and intentionally NOT added to `parallel_units`.

| Candidate | Excluded Unit | Disposition | Cosine (info) | Sample Overlap |
|---|---|---|---:|---|
| `AVP 20.46.9` | `AVŚ 5.4` | **reviewed — formulaic** | 0.558 | तम् उ मे अगदं कृधि (generic healing formula) |
| `AVP 19.11.2` | `AVŚ 5.4` | **reviewed — formulaic** | 0.693 | देवेभ्यो अधि जातो सि (generic formula) |
| `MS 4.11.3` | `RV 1.174` | **reviewed — formulaic** | 0.918 | `RV 1.174.10`: विद्यामेषं वृजनं जीरदानुम् (stock Agastya refrain across RV 1.165–191) |
| `MS 4.14.7` | `RV 1.174` | **reviewed — formulaic** | 0.838 | `RV 1.174.10`: विद्यामेषं वृजनं जीरदानुम् (stock Agastya refrain) |
| `MS 4.14.13` | `RV 1.174` | **reviewed — formulaic** | 0.904 | `RV 1.174.10`: विद्यामेषं वृजनं जीरदानुम् (stock Agastya refrain) |
| `GB 2.1.25` | `ŚB 1.8.1` | **reviewed — formulaic** | 0.770 | प्राश्नन्ति पशवो वा इडा (generic Brāhmaṇa ritual phrase) |
| `MS 1.6.2` | `RV 8.19` | **reviewed — formulaic** | 0.844 | यस्मिन्न् इन्द्रो वरुणो मित्रो अर्यमा देवा (deity list) |
| `AVP 5.39.5` | `RV 8.19` | **reviewed — formulaic** | 0.861 | स्रिधो वरुणो मित्रो अर्यमा… इन्द्रम् अग्निं (deity list) |
| `KB 21.2.9` | `RV 8.19` | **reviewed — formulaic** | 0.853 | अग्निर् इन्द्रो वरुणो मित्रो अर्यमा इति (deity list) |
| `KB 24.8.7` | `RV 8.19` | **reviewed — formulaic** | 0.710 | अग्निर् इन्द्रो वरुणो मित्रो अर्यमा इति (deity list) |
| `MS 2.13.20` | `RV 8.19` | **reviewed — formulaic** | 0.832 | नक्षत्रम् अर्यमा देवता हस्तो नक्षत्रं सविता… (deity/nakṣatra list) |
| `MS 3.16.1` | `RV 8.19` | **reviewed — formulaic** | 0.869 | नो मित्रो वरुणो अर्यमायुर् इन्द्र ऋभुक्षा (deity list) |
| `AVP 2.57.2` | `RV 8.19` | **reviewed — formulaic** | 0.880 | यम् इन्द्रम् आहुर् वरुणं यम् आहुर् यं मित्रम्… (deity list) |
| `Nir 9.3` | `RV 8.19` | **reviewed — formulaic** | 0.820 | त्वम् मित्रश् च वरुणश् च अर्यमन् च… (deity list) |
| `MS 1.6.8` | `PB 13.3` | **reviewed — formulaic** | 0.781 | गायत्रो ह्य् अग्निर् गायत्रछन्दाः… (generic meter prose) |
| `MS 2.13.10` | `PB 13.3` | **reviewed — formulaic** | 0.623 | गायत्रीं त्रिष्टुभं जगतीं विराजम्… (meter list) |
| `MS 3.4.4` | `PB 13.3` | **reviewed — formulaic** | 0.784 | अष्टाक्षरा गायत्री ब्रह्म गायत्री… (generic meter prose) |
| `MS 3.4.5` | `PB 13.3` | **reviewed — formulaic** | 0.564 | आहुतीनां प्रतिष्ठित्यै… (generic ritual prose) |
| `MS 1.6.13` | `PB 13.3` | **reviewed — formulaic** | 0.812 | इति सो ब्रवीद् अहं (1× 4-gram formula) |

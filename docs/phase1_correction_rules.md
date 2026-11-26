# Phase-1 correction — frozen rule specifications

Status: **FROZEN by the commit that introduces this file** (spec + code land together,
before any dev-set (G1–G19) result has been generated or viewed). Any change to a rule
after dev results exist must be listed in the "Post-freeze changes" section of the
report with the new commit hash. None is expected.

Context: the three entries seeded by hand from gold verses (RV 1.112.19 *sudevyam* = G15,
RV 1.63.7 *aṃhoḥ* = G3, devávant-@RV 7.18.22 = G11) violated the contamination rule and
have been **deleted**. They are replaced by corpus-wide rules below. A rule that does not
fire on a gold case is a TRUE result and is reported as such.

## Disclosed before any dev result: rule substitution (devávant)

The roadmap named a "gid signal" for the devávant-/Devavat case. Exploration of the
morphology sidecar (corpus-wide statistics only) shows **gid is 1:1 with the lemma string**:
10,031 lemma strings, **0** with two gids. A gid therefore cannot separate a name sense
from an adjective sense, so that rule cannot work. It is replaced by rules **L3** (lexicon
proper-name flag) and **L1** (dual-sense lexicon alternative), both driven by the Zurich
glossary's explicit name markers. This substitution was decided from data structure alone.

## Common conventions

* Corpus: `morphology_rv.json` (164,758 tokens, 10,552 verses), `padapatha_rv.json`,
  `lemma_index_rv.json` (`lemma_gloss_de`, `forms_to_lemmas`). RV only.
* **Exclusions.** Every builder calls `src/utils/exclusions.py`: it loads `excluded_units`
  from the G2 manifest at runtime (raises if unavailable/empty), **skips excluded verses at
  input**, and **asserts at output** that no entry lies in an excluded unit
  (`ExclusionViolation` otherwise). Lemma-level entries are emitted only for lemmas that
  occur in ≥1 non-excluded verse; occurrence counts ignore excluded verses.
* Gold (G-series) hymns are NOT excluded from the builders — a systematic rule applies to
  every verse alike. They are excluded only from the false-positive samples.
* Determinism: no randomness in the builders. FP samples use `random.Random(20261121)`.
* Lemma key: `_lemkey()` = accent-stripped, lower-case, stem-marker-free (same as
  `padapatha._lemkey`).
* The German glosses themselves are **not injected into prompts** (existing design); only
  the derived flags are.

## Rule L3 — lexicon proper-name flag (replaces the gid rule)

Source: `lemma_gloss_de` (Zurich glossary). Sense split: the gloss is cut at top-level `;`
(not inside `()`/`[]`).

Sense classes:
* **NAME**: matches `N. pr.` | `Eigenname` | `Personenname` | `Frauenname` | `Stammesname` |
  `Volksname` | `Flussname` | `Name (eines|einer|des|der) [≤2 words] HEAD` with
  HEAD ∈ {Königs, Fürsten, Mannes, Sängers, Dichters, Weisen, Sehers, Priesters,
  Opferpriesters, Opferers, Opferherrn, Spenders, Schenkers, Schützlings, Günstlings,
  Patrons, Vaters, Gottes, Gottheit, Göttin, Dämons, Feindes, Wesens, Frau, Flusses,
  Volkes, Volksstammes, Stammes, Stammeshelden, Familie, Priestergeschlechts,
  Bharatiden, Aṅgiras, Örtlichkeit, Berges, Landes, Indra-Freunden, R̥ṣi/Ṛṣi}.
  (HEAD list chosen from the frequency distribution of words after "Name eines/…";
  deliberately excludes Metrums, Milchkuh, Rosses, Hündin, Gestalt, Schar.)
* **hedged NAME**: a NAME sense containing `unklar|unsicher|vielleicht|wohl|mögl|
  möglicherweise|evtl|eventuell|fraglich|vermutlich|angeblich` or `?`.
* **IGNORE**: not NAME and starting with `(`, `[`, `<`, `*`, `unklar`, `unsicher`, `wohl`,
  `vielleicht`, `etwa`, `entweder`, `Br.`, `vgl.`, `cf.`, `s.` (etymology / hedge / pointer).
* **APPELLATIVE**: everything else.

**v2 sense classes (pre-dev revision, see the revision log):** a NAME sense that contains a
verse locator (`\d+.\d+(.\d+)?`, e.g. "in 5.30.14 … Name eines Sängers", "N. pr. in 8.1.34?")
is **NAME_LOCAL** (verse-localised — it must not be applied to every token of the lemma; it
neither sets the primary sense nor triggers a rule). Hedged names never trigger a rule.

**v2 trigger (first-sense primacy):** let *first* = the first sense that is neither IGNORE
nor NAME_LOCAL. **L3 fires iff *first* is a firm NAME** (later senses — plural class,
family, epithet — elaborate the name). Output: every token of that lemma in a non-excluded
verse is rendered `«PROPER NAME: <Title>»`, Title = lemma without accents/stem-hyphen,
first letter capitalised (lemma-based: an inflected/feminine token shows the lemma's title).
Lemmas already flagged by the GAZETTEER (`build_name_flags.py`) are skipped and counted
separately.

## Rule L1 — dual-sense lexicon alternative (multi-sense dictionary entries)

**v2 trigger: *first* is APPELLATIVE and a LATER sense is a firm, unlocalised NAME.**
Output: every token of that lemma in a non-excluded verse is rendered
`«ALT READING (lexicon, context decides): …also a proper name (<Title>)…»`: the stored tag
reads the word as a common word; the lexicon lists a name sense too; present both and mark
the choice disputed. No gold verse is consulted. Lemmas with only hedged / verse-localised
name senses are counted (DROP_HEDGED / DROP_LOCAL) and never rendered.

## Rule R2 — pada–saṃhitā visarga divergence (ambiguous tags)

Source: `padapatha_rv.json` (`p` = Lubotsky saṃhitā pāda lines) × `morphology_rv.json`
(padapāṭha forms `f`).

1. Normalise (NFD, strip accents, NFC, lower-case, `ṁ→ṃ`, drop `+ = * ? ! |‖ -`).
2. Saṃhitā words = whitespace split of the pāda lines. **v2 pāda-boundary semantics:** sandhi
   applies ACROSS pāda boundaries (a pāda-final word's next initial = the next pāda's first
   word); the next initial is None (pausa / no sandhi) only before a half-verse/verse marker
   `|` / `‖`, and after a word ending in `-` (sandhi suspended: hiatus, visarga kept).
3. Align padapāṭha tokens to saṃhitā words with a ±1-lookahead greedy matcher
   (match = common prefix covers all but the last 2 characters, length difference ≤3;
   words of <3 characters need equal first character). Alignment coverage is reported.
4. Evaluate only pairs with padapāṭha form P ending in `ḥ`, |P| ≥ 5, and a *core match*:
   `P[1:-3]` is a prefix of `S[1:]` (the first character is skipped because the previous
   word's sandhi may alter it).
5. Regular external visarga sandhi before next initial N, with V = vowel before `ḥ`:
   N None → `ḥ` kept · `k,p` → `ḥ` **or `s`** (v2: the RV text writes `-s` before k/p, e.g.
   *brahmaṇas pate*) · `c` → `ś` · `ṭ` → `ṣ` · `t` → `s` · sibilant → that sibilant
   or `ḥ` · N voiced/vowel: V=`a` → `o` (N consonant or `a`) / `a` (N another vowel);
   V=`ā` → `ā`; any other V → V+`r` (before `r`: ḥ dropped, short V lengthened).
   Exception: `saḥ`/`eṣaḥ` may drop `ḥ` before a consonant.
6. **Divergence** = the saṃhitā final segment is not among the regular surfaces of P.
7. **Implied alternative**: replace P's final `Vḥ` by each of {aḥ, āḥ, iḥ, īḥ, uḥ, ūḥ,
   eḥ, oḥ, aiḥ, auḥ} (≠ P) and keep candidates P′ whose regular surfaces before N contain
   S's final segment AND whose accent-less Devanāgarī form is **attested** as an inflected
   form in `forms_to_lemmas`.
8. Entry emitted only if ≥1 attested alternative exists (precision over recall). Keyed
   `verse|token_n`; rendered `«ALT READING (pada vs saṃhitā, disputed): …»`.

Limitations (stated, not hidden): visarga only; no vowel/consonant sandhi; alignment can
fail on compounds/vowel-merging — coverage and FP rate are reported.

## Rule K — kinship audit of `proper_noun_variants.json` (whole file)

Scope: every string value except `variants` arrays and `_*` metadata. A field is a
*kinship claim* if it matches the kinship lexicon (grand-*, son/father/mother/daughter/
brother/sister, ancestor, descendant, progenitor, lineage, dynasty, …).

* **Generation-count claim**: matches `grandson|grandfather|grandmother|granddaughter|
  great-grand*|son of|X's son|father of|mother of|daughter of|brother of|sister of|
  (grandson)`.
* **Backing**: a generation-count claim is BACKED only if the same field carries a
  citation to an *admissible* unit — admissible = not in the G2 excluded units and not in
  a gold hymn — and the cited RV verse contains a kinship lemma in the morphology
  sidecar. Anything else is UNBACKED.
* Action on UNBACKED Vedic claims: relabel the count to **`descendant (patronymic)`**
  (grandson/son → "descendant (patronymic)"; "X's son" → "descendant (patronymic) of X").
  Citations into **excluded** units are removed (and any parenthetical describing their
  content). Citations into **gold** hymns are kept as bare citations but the quoted claim is
  relabelled.
* Epic (Rāmāyaṇa-context) kinship claims are not Vedic-corpus claims and cannot be
  "patronymic"; they are annotated `(itihāsa tradition, not attested in the Vedic corpus)`
  rather than relabelled. **This is a judgment call flagged for the owner.**
* Lineage-generic claims (ancestor/lineage/dynasty/progenitor without a count) are
  listed, not changed.
* **K2 — whole-file scrub (manifest rule).** Independently of kinship, NO citation into a
  G2 excluded unit may remain anywhere in a data file: every string field is scrubbed
  (a field that is only such a citation is removed; an embedded one is stripped together
  with the parenthetical describing its content). The audit verifies the result with the
  citation regex AND an independent loose substring scan over all 15 units.
* **K3 — citation correction (owner-directed 2026-11-21).** Two key_references pointed at the
  wrong hymn (RV 10.60.4 / 10.60.9, both gold). The correct loci are RV 4.15.4 (*sṛñjaye …
  daivavāte*) and RV 4.15.7–9 (*kumāraḥ sāhadevyaḥ … somakaḥ*); the script VERIFIES each cited
  verse against `local_store` (required Devanāgarī needles present, verse admissible) before
  applying. The verses attest *patronymics* (Daivavāta, Sāhadevya), not a kin lemma, so the
  claim stays "descendant (patronymic)"; the quote marks (a Griffith rendering) are dropped.
* **K4 — owner-directed removal (2026-11-21).** The Kuruśravaṇa–Trasadasyu lineage claim has
  a G2-held-out unit (RV 10.33) as its only source: **removed entirely, not relabelled**, from
  the three places it appears (Kurus/early_references, Kurusravana/lineage,
  Trasadasyu/descendants). Fields that still *imply* a Trasadasyu→Kuru link without naming
  Kuruśravaṇa (Kurus/note chain, Trasadasyu/context, /dynasty_role, /note, /fame,
  Pakasthaman/related_figures) are left for the owner's call.
* The audit is corpus-wide and driven by the rule only; no gold or G2 case is targeted.
  The edited file is shown as a diff to the owner **before** it is committed.

## False-positive check protocol (per rule L1, L3, R2)

15 hits sampled at random (`Random(20261121)`) from verses **outside** the gold hymns
(RV 1.63, 1.112, 1.184, 3.53, 4.42, 6.61, 7.18, 10.60) and the G2 excluded units; each
judged TRUE/FALSE positive by reading the lemma, form and context; reported with the
count of corpus-wide entries added.

## Re-run protocol

* The bake-off used temperature 0.1 **without a seed**: decoding is NOT deterministic, so
  *all* grounded dev cases are re-generated (not only those whose fixture changed), for
  gemma4-26b-a4b and gemma4-e4b. The new run sets `seed=0` so it is reproducible.
* All 19 dev cases are reported: G1–G9, G12, G13, G15, G17, G18, G19 (15 programmatic);
  G10, G11, G14 (judge — answers regenerated; grades proposed, owner confirms); G16
  (retrieval-only; not model-dependent, not re-run — its query expansion needs Gemini).
* The G2 test set is **not run**.

---

## Revision log (pre-dev) — v1 → v2

**Timeline.** v1 spec+code frozen in commit `199fb02` (2026-11-21 05:33 UTC). Each rule was
then run once corpus-wide and the mandated false-positive check was applied. **No dev-set
(G1–G19) answer or score existed or was viewed at any point in this revision.** Every
diagnosis below used glosses and verses *outside* the gold hymns and the G2 excluded units.
The v1 outputs were overwritten by v2; the v1 numbers are preserved here.

### v1 results (as frozen, run once)
| rule | corpus-wide output | false-positive check (15 hits, non-gold) |
|---|---|---|
| L3 | 200 lemmas → 821 tokens (+11 already in GAZETTEER) | 15/15 true proper names, but frequency-weighted (7 distinct lemmas: pūṣán- ×6, átri- ×4, tváṣṭar- ×2…); one title imprecision (feminine token of a *-vant-* lemma shows the lemma's title) |
| L1 | 192 lemmas → 2,803 tokens | **≈2–3 of 15 appropriate** (≈15–20% precision) |
| R2 | alignment coverage 93.8%; 34,763 visarga tokens evaluated; 30,471 regular; 4,292 irregular; **3 entries** with an attested alternative | 3 hits: 1 alignment error, 2 genuine pada/saṃhitā reading differences (-aḥ vs -āḥ) |

### Why v1 was rejected (all diagnosed on non-gold data)
* **L1 had three systematic failure classes**: (a) *verse-localised* name senses applied to
  every token of the lemma ("in 5.44.11 vielleicht Name…", "N. pr. in 8.1.34?" — 6/15);
  (b) *misclassified second sense*: pure-name lemmas whose later sense is descriptive
  (rudrá- "Pl. einer Götterklasse", váruṇa- "oft als Götterkönig bezeichnet", priyámedha-
  "eine Sängerfamilie") were typed dual-sense, so the prompt told the model *Varuṇa may be a
  common word* — harmful (5/15); (c) hedged-only name senses ("vielleicht auch N. pr.") for
  plainly common words (1/15).
* **R2's "4,292 irregular" was an artefact of my sandhi model**, not data: (1) I treated
  every pāda end without a hyphen as a pause, but Lubotsky's text applies sandhi across pāda
  boundaries (`ŕ̥ṣibhiḥ → ŕ̥ṣibhir`, `-taḥ → -to`) and a trailing `-` marks the *opposite* (sandhi
  suspended: visarga kept); (2) the RV text writes `-s` before k/p (`brahmaṇas pate`). The
  attestation lookup itself was verified sound (indraḥ, agniḥ, devāḥ … all resolve).

### v2 changes (committed before re-running; each rule is then run exactly once more)
* **L3/L1:** first-sense primacy (L3 iff the first substantive sense is a firm name; L1 iff
  it is appellative and a later sense is a firm name); verse-localised name senses
  (`NAME_LOCAL`) and hedged names never trigger; supplementary *distinct-lemma* FP sample
  added because the hit sample is frequency-weighted.
* **R2:** pāda-boundary semantics and `-s` before k/p as specified above.
* Unit tests updated to v2 semantics (10/10 pass, synthetic inputs only).

### Other pre-dev changes (not to the L1/L3/R2 rules)
* **Exclusion-guard bug (found while reviewing the kinship diff, before any dev result).**
  `exclusions._CIT` only recognised a citation after whitespace/`(`/`[`, so a citation directly
  after a JSON quote (`"hymn_reference": "RV 10.33.4"`) was invisible to `text_hits_excluded`,
  and the audit's own "no excluded citation remains" check passed wrongly. Fixed with a
  negative-lookbehind boundary + a regression test (11/11 tests). Builders that check verse
  *keys* (`assert_none_excluded`, `rv_verse_is_excluded`) were never affected.
* **K2 added** to rule K (whole-file excluded-citation scrub), as a consequence.

### Post-freeze changes after dev results exist
None so far. (Any later change must be appended here with its commit hash.)

---

## v3 — owner decisions of 2026-11-21 (frozen BEFORE the corrected-layer run)

These follow the Phase-1 report (`docs/phase1_correction_report.md`). Spec + code are committed
before any builder is run and before any dev answer for this layer exists.

### L3b — localised-sense name flag (amendment to L3)
> **LABEL (mandatory wherever G11 or any dev result is reported):** *rule added after seeing it
> fire on a dev verse.* The owner adopted it after I reported that the glossary gives
> `devávant-` a name sense localised to RV 7.18.22 (a gold/dev verse, G11) and that the frozen v2
> rule discarded it. Its merit must therefore be argued on **non-gold** hits (below) and on the
> G2 test set only — never on G11.

* **Trigger.** A lemma that is NOT a global L3 name, whose glossary has ≥1 **firm** (unhedged)
  name sense carrying a verse locator. Hedged localised senses are still dropped (`DROP_LOCAL`).
* **Locus.** Every full `M.SSS.VV` locator in that sense (`5.30.14 und 8.22.10`, `5. 44.11`,
  `RV 07.018.22` → `5.030.14`, `8.022.10`, `5.044.11`, `7.018.22`). Hymn-level (2-part) and
  malformed locators are **counted, never applied**.
* **Application.** `«PROPER NAME: <Title>»` on tokens of that lemma **only in the cited verse(s)**.
  Lemmas already flagged by the GAZETTEER are skipped. Loci inside G2 excluded units are
  dropped (counted) and the output is asserted clean. Sidecar field: `localised_name_lemmas`.
* **Report:** entries added (lemmas, loci, tokens), bookkeeping (loci without a matching token,
  excluded loci), a 15-hit FP sample outside gold hymns / G2 units, and the hits that fall in
  gold hymns listed separately and **not** counted as the FP sample.

### L1 — disabled
0/15 hits fit their context. `ENABLE_L1 = False`: still classified and counted, nothing written
to `dual_sense_lemmas`, nothing rendered. **No frequency guard** (owner decision).

### GAZETTEER name flags — context-dependent (`rohita`)
`NAME_FLAG_CONTEXTS = {"rohita": {"RV": False, "AVŚ": {"books": [13]}}}`. The entry is kept
(Rohita is a deity in AVŚ book 13); the RV renderer skips an entry whose `contexts["RV"]` is
false. A future AVŚ renderer (Phase 2) must flag it in book 13. Not deleted globally. A
report-only audit lists any other flagged GAZETTEER name whose glossary does not begin with a
name sense; nothing else is changed.

### KG — held-out relations tagged, loaders filter, nothing deleted
`tag_kg_held_out.py` writes `knowledge_store/kg_held_out_relations.json` (a new sidecar; the
mirror and Qdrant are not written). `src/utils/vedic_kg.py` filters at load time by recomputing
from the manifest: `fact_is_held_out`, `iter_relations(exclude_held_out=True)` (default, for any
training loader), and `KG_EXCLUDE_HELD_OUT=1` for the eval pipeline (used for the corrected layer
only). The production app is unchanged.

### Evals are greedy
Temperature 0 and a fixed seed (0) from now on (`colab_run export --temperature` default 0.0;
`run_bakeoff` configs 0.0). Greedy decoding removes the sampling noise that made the earlier
before/after unreadable.

### Pre- vs post-correction layers (clean before/after)
* **pre** = the data layer exactly as committed in `02ffb72` (hand-seeded alternatives and the
  contextual flag included), reproduced by `llm_lab.domains.vedic.legacy_layer` from git — kept
  OUT of the repos' data and never used for training.
* **post** = this v3 layer + the KG filter.
* Each layer is generated once per model, greedy, on G1–G19 (18 model cases); G16 carried.

### Judge cases
Not self-graded. The three judge cases (G10, G11, G14) are regenerated and laid out for
**qwen3.6-27b or the owner**. My earlier *proposed* grades are withdrawn from the report.

# Phase-1 correction — report (2026-11-21)

Specs: `docs/phase1_correction_rules.md` (frozen rules, revision log, v3 owner decisions).
Dev set = G1–G19, fixed denominators. **The G2 test set was never run.**

## TL;DR

* **Greedy before/after (the clean measurement, Part 2).** Programmatic, 15 cases:
  **gemma4-26b-a4b 8 → 5, gemma4-e4b 5 → 5.** Greedy decoding is deterministic here (6/6
  byte-identical prompts gave byte-identical answers), so every flip is caused by a prompt
  difference — no sampling noise.
* **Two of the gold passes were contamination, not skill:** G15 (both models) and **G3**
  (26b). Both pre-correction prompts carried the hand-seeded alternative, and the answers echoed
  it. With the seeds gone both fail. Contamination-free, the layers are indistinguishable:
  26b 6 → 5, e4b 4 → 5.
* The data layer cannot supply what the glossary lacks (*sudevyam* = Sudevī, *aṃhóḥ/aṃhaḥ*).
* **My correction introduced a small regression** (display names lost their macrons, §8) and
  the KG puts **800+ mostly-inferred lines into the 7.18 prompts** (§8). Neither is fixed here.
* Judge cases are **not graded by me**; a blind pack is ready (§7). The first report's proposed
  grades are **withdrawn**.
* CU: first re-run **2.50**, greedy pre/post run **3.73**.

---

# Part 1 — Phase-1 correction (rules, disclosures)

## 1. Protocol and timeline (UTC, 2026-11-21)

| step | commit | time |
|---|---|---|
| v1 rules frozen, before any run | `199fb02` | 05:33 |
| v1 run once + FP check → rejected (L1, R2) | – | 05:35 |
| v2 revision committed before re-running | `ffad052` | 05:37 |
| v2 sidecars | `b646807` | 05:38 |
| exclusion-guard fix + kinship script | `eb358a0` | 05:41 |
| first dev re-run (sampled, T=0.1) | – | 05:46–06:09 |
| kinship edits (owner-approved with changes) | `e79a388` | 06:18 |
| v3 owner decisions frozen **before** any v3 builder ran | `9323706` | 06:21 |
| v3 sidecars + KG tags (each builder once) | `8ed857e` | 06:23 |
| greedy pre/post run | – | 06:25–07:00 |

No G1–G19 answer existed before the v2 freeze, and none was used to tune a rule. The one
rule change that **was** informed by a gold outcome is L3b (§3), adopted by the owner and
labelled as such.

## 2. Rules and false-positive checks

| rule | corpus-wide output | false-positive check (outside gold hymns / G2 units; my reading) |
|---|---|---|
| **L3** lexicon proper-name flag | 271 lemmas / 1,208 tokens (+20 in GAZETTEER) | hits 13/15 true (2 uncertain); distinct lemmas 14/15 true |
| **L3b** localised name (v3) | **14 lemmas / 15 verse loci / 15 tokens**; 0 loci in G2 units; 0 loci without a token | only 12 non-gold hits, **all shown**: 10 correct per the glossary, **2 false positives** (`daivavātá-` at 3.23.3 is an epithet of Agni there; `pā́nta-` at 7.33.2 is only "considered" a name by Geldner) |
| **L1** dual-sense (v2) | **disabled** (would have been 41 / 949; nothing written) | 0/15 hits fit their context — owner decision, no frequency guard |
| **R2** pada–saṃhitā visarga | 3 entries (99.4% of 34,763 visarga tokens regular) | 2 genuine reading differences, 1 alignment error |

v1 → v2 (pre-dev) revisions and their reasons are in the spec's revision log.

## 3. The three formerly gold-seeded entries

| entry | frozen rule | result |
|---|---|---|
| `sudevyà-` (G15) | glossary: *"Schar der guten Götter"* — no name sense | no rule fires |
| `aṃhóḥ` (G3) | R2 | no entry in any gold hymn |
| `devávant-` (G11) | glossary: *"(N. pr.) in RV 07.018.22 Name des Grossvaters von Sudās"* | v2 `DROP_LOCAL`; **L3b (v3) now fires** |

> **LABEL — G11:** *the L3b rule was added after seeing it fire on a dev verse.* Its merit
> must be argued on non-gold hits and judged on the G2 test set, never on G11. L3b's gold-hymn
> hits: Matsya (7.18.6), Parāśara (7.18.21), `devávant-` (7.18.22 = G11).

## 4. Exclusion guard and the KG

* **Bug in my own guard (disclosed):** `exclusions._CIT` missed a citation directly after a JSON
  quote; found by reading a diff; fixed with a regression test. The KG tagger's own loose
  self-check then failed once on `AVS 4.38.6` — *Atharvaveda*, not the excluded RV 4.38; the
  filter was right, the check was not corpus-aware; fixed. Builders that check verse keys were
  never affected.
* **KG held-out relations (decision 4):** **101 of 4,106** relations (2.46%; 97 `inferred`,
  4 `authoritative`; 18 entities) cite a G2 unit. Tagged in
  `knowledge_store/kg_held_out_relations.json`. **Nothing deleted; no Qdrant writes; the mirror
  is untouched.** `vedic_kg.py` filters at load time by recomputing from the manifest
  (`fact_is_held_out`, `iter_relations(exclude_held_out=True)` by default, `KG_EXCLUDE_HELD_OUT=1`
  for the eval pipeline); the production app is unchanged. Self-check: the filtered iterator
  yields exactly 4,005 = 4,106 − 101 relations, none mentioning an excluded unit.

## 5. Kinship audit — committed `e79a388` (owner-approved with changes)

11 edits to `proper_noun_variants.json`: (K3) the two wrong citations corrected to **RV 4.15.4**
(*sṛñjaye … daivavāte*) and **RV 4.15.7–9** (*kumāraḥ sāhadevyaḥ … somakaḥ*), each verified
against `local_store` before applying, claim kept as "descendant (patronymic)" (the verses
attest patronymics, no kin lemma); (K4) the Kuruśravaṇa–Trasadasyu lineage claim **removed
entirely** from the three places it appears (sole source: a G2 unit); (K2) both
`hymn_reference: RV 10.33.4` fields removed; 4 Rāmāyaṇa claims annotated. 0 held-out citations
remain (regex + independent loose scan). **Still implying a Trasadasyu→Kuru link without naming
Kuruśravaṇa, left for your call:** `Kurus/note`, `Trasadasyu/context`, `/dynasty_role`, `/note`,
`/fame`, `Pakasthaman/related_figures`.

## 6. GAZETTEER `rohita` (decision 5) and a wider audit

`rohita` is now context-dependent: **off in RV (14 tokens no longer flagged), on in AVŚ
book 13**; the entry is kept with `contexts` for a future AVŚ renderer. A report-only audit of
all 39 GAZETTEER names against the glossary (my name-sense pattern tolerates only two words
between "Name des" and its head noun, so e.g. Indra is mis-read as "not name-first"; the
substantive picture is smaller than the raw count):

* **clearly not names in the RV — 64 tokens:** `aṅgá` the particle (40), `áṅga-` "limb" (11),
  `sūyávasa-` (5), `bhedá-` (5), `parikṣít-` (3);
* **genuinely ambiguous, deity vs common word — ~1,300 tokens:** `sóma-` (975), `mitrá-` (325);
* all other entries (Indra, Agni, Marut, Uṣas, Vṛtra, Sindhu, …) are real names.
Not changed — your instruction covered `rohita` only.

---

# Part 2 — greedy before/after (decision 6)

Both layers generated once per model, **temperature 0, seed 0**, 8192 tokens, thinking off:
**pre** = the data layer exactly as committed in `02ffb72`, rebuilt from git by
`llm_lab.domains.vedic.legacy_layer` (contaminated; never used for training; its files are
git-ignored); **post** = the v3 layer + the KG filter. No prompt truncation, no output caps,
no empties. G16 is retrieval-only (its query expansion needs Gemini) and is **carried as a
fail**, not re-run.

## 7. Dev set G1–G19

Programmatic (15) — `pre → post`; `*` = flipped; unchanged gold checks:

| case | 26b | e4b | what differs between the two prompts |
|---|---|---|---|
| G1 | ✗ → ✗ | ✗ → ✗ | identical |
| G2 | ✗ → ✗ | ✓ → ✓ | 1 token row + rule text |
| **G3** | **✓ → ✗ ***| ✗ → ✗ | 3 token rows (incl. the seeded `aṃhóḥ` alternative) + rule text |
| G4 | ✓ → ✓ | ✗ → ✓ * | **rule text only** |
| G5 | ✓ → ✓ | ✓ → ✓ | rule text only |
| G6 | ✓ → ✓ | ✗ → ✗ | rule text only |
| **G7** | **✓ → ✗ ***| ✓ → ✓ | 2 token rows (display names) + **KG filter** + rule text |
| G8 | ✗ → ✗ | ✗ → ✗ | 2 token rows + KG filter + rule text |
| G9 | ✓ → ✓ | ✗ → ✗ | rule text only |
| G12 | ✓ → ✓ | ✓ → ✓ | 2 token rows + rule text |
| G13 | ✗ → ✗ | ✗ → ✗ | rule text only |
| **G15** | **✓ → ✗ ***| **✓ → ✗ ***| 3 token rows (incl. the seeded Sudevī alternative) + rule text |
| G17 | ✗ → ✗ | ✗ → ✗ | identical |
| G18 | ✗ → ✗ | ✗ → ✗ | identical |
| G19 | ✗ → ✗ | ✗ → ✗ | 2 token rows + rule text |
| **programmatic** | **8/15 → 5/15** | **5/15 → 5/15** | |

**Judge cases (G10, G11, G14): not graded by me.** The three are regenerated for both models
and both layers, and laid out as a **blind pack** — pre/post order randomised per
(case, model), arm hidden, key in a separate file — for qwen3.6-27b or the owner:
`llm_lab/review/judge_blind_phase1_v3.md` (key: `judge_blind_key_phase1_v3.json`; local,
git-ignored because the answers reproduce corpus text). For G11 only an *objective* excerpt
note, not a grade: in all four answers (2 models × 2 layers) the name "Devavat/Devavant"
appears, echoed from the flag, and a regex probe finds no answer that states Sudās is Devavat's
descendant.

Fixed denominator: 15 programmatic + 3 judge (pending) + G16 (carried: fail) = 19.

## 8. What the flips mean (every one is now caused by a prompt difference)

* **Clean, intended — contamination removed:** G15 (both) and **G3 (26b)**. The pre prompts
  carried the hand-seeded alternatives; the 26b pre answer for G3 mentions both `aṃhaḥ` and the
  pada/saṃhitā divergence, the post answer neither. **Two gold passes were contamination.**
* **Confounded — G7 (26b):** three simultaneous changes (see below), so the loss cannot be
  assigned without an ablation (~2 CU).
* **Wording sensitivity — G4 (e4b, +1):** the prompt differs only in the rule paragraph (the
  gold-derived example removed, wording tightened), yet the case flipped. Of the 10
  rule-text-only case×model pairs (G4, G5, G6, G9, G13 × 2 models), **1 flipped** — that is the
  floor to read ±1 results against.
* **Contamination-free reading:** removing the contaminated passes from *before*, 26b goes
  6 → 5 and e4b 4 → 5: **indistinguishable** within that floor.

**Two findings I did not act on:**

1. **A regression of mine.** G7's two token-row changes are `Divodāsa → Divodasa` and
   `Sudās → Sudas`: the deleted hand-seeds carried correct diacritic display names; the
   GAZETTEER fallback is `capitalize()`, which loses macrons. Fix: derive display names from
   the lemma title (as L3 does). It would be a post-dev-result change, so it needs your
   approval and another run.
2. **800 KG lines in the 7.18 prompts.** G7, G8 and G11 carry **802** KG lines, mostly
   `inferred` (model-generated); **72 cited held-out units** and are removed by the filter
   (802 → 695, incl. second-hop neighbours). Those inferred relations are the likely route for
   genealogy errors in real answers. The roadmap's "KG: authoritative tier only" is not
   implemented in the prompt path.

## 9. Cost

| run | CU | notes |
|---|---|---|
| first re-run (sampled, T=0.1, 36 generations) | **2.50** | 125.13 → 122.63; superseded by Part 2 |
| greedy pre + post (72 generations) | **3.73** | 122.63 → **118.90**; A100 06:25–07:00 UTC |

## 10. Decisions for the owner

1. **Display names** (§8.1): approve deriving them from the lemma title, then re-run.
2. **KG in prompts** (§8.2): restrict to the authoritative tier (and cap the hop-2 fan-out)?
3. **GAZETTEER** (§6): drop the 64-token clear false positives (`aṅgá`, `áṅga-`, `sūyávasa-`,
   `bhedá-`, `parikṣít-`) via contexts like `rohita`? Policy for `sóma-`/`mitrá-`?
4. **Ablation for G7** (~2 CU): post layer with the KG filter off, and with macrons restored.
5. **Judge cases**: grade the blind pack (qwen3.6-27b or you).
6. **Remaining Trasadasyu→Kuru fields** (§5).
7. **Reading of the result:** the data layer supplies what a lexicon *contains*; *sudevyam* and
   *aṃhóḥ/aṃhaḥ* are SFT / teacher-knowledge problems. Phase 2 has **not** been started.

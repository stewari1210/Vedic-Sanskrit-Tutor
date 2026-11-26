# Roadmap — Phase 2 (non-RV segmentation), Phase 3 (commentary labels), SFT data generation

Status: plan only (no execution beyond this doc). Supersedes the ad-hoc notes; this is
the reference for the data + training work that follows the model bake-off.

## Why these phases (data, not training)
The bake-off chose **gemma4-26b-a4b** as the SFT/GRPO base and **gemma4-e4b** as the
same-family phone/distillation student (logit distillation). But four gold cases —
**G1 (ŚB), G13 (RV+commentary), G17 (AB), G18 (ŚB)** — fail for *every* model,
including Gemini. These are not behavioural/format failures (which SFT fixes); they
fail because the **grounding data does not exist for non-RV texts**, and because
commentary (Sāyaṇa) identifications are unlabeled. Phase 2/3 build that data. SFT
comes after, on top of the completed data layer.

---

## Standing rules (apply to all phases)

1. **Contamination rule (non-negotiable).** No data-layer entry — proper-name flags,
   tag alternatives, commentary labels, glosses — may be *seeded from a gold verse or
   its hymn*. Data must come from corpus-wide, systematic sources (lexica, ambiguous
   tags, digitised commentaries), so that any gold-case improvement is a side effect
   of a general rule, not a hardcoded answer.
   - **Immediate correction (Phase-1 debt).** The current `tag_alternatives_rv.json`
     seeds (RV 1.112.19 *sudevyam* = G15; RV 1.63.7 *aṃhoḥ* = G3) and the
     `devávant-@7.018.22` (= G11) contextual name flag were hand-picked from gold
     verses. They are flagged in-file as CONTAMINATED and the G15 "pass" is
     provisional. Re-source before trusting any score:
       - *sudevyam*: from a **multi-sense lexicon** — a lemma that carries both a
         common-noun sense and a proper-name sense (homonymy) is flagged corpus-wide;
         *sudevyà-* benefits only if the lexicon lists Sudevī (Vedic Index), applied
         to every occurrence, not to RV 1.112.19 specifically.
       - *aṃhoḥ*: from a **systematic pada-vs-saṃhitā divergence detector** — compare
         each token's padapāṭha form against the saṃhitā surface; where they imply
         different morphology (beyond regular sandhi), emit an alternative. Corpus-wide.
       - *devávant-/Devavat*: from the **`gid` signal** (gid=`devavat_*`) applied to
         every occurrence, never by naming the gold verse. If `gid` does not separate
         the name reading from the adjective, leave it unflagged and accept the miss.
     Then re-report G15 (and G3/G11) on the systematic basis; if the systematic source
     does not cover a case, report it unchanged — do not reach for the gold answer.
   - **Kinship-claim audit of `proper_noun_variants.json` (corpus-wide).** Audit the
     WHOLE file, not individual entries: every kinship/generation claim (e.g.
     "grandson", "son of", "father of") must be **backed by a text citation**. Any
     generation-count claim that is not textually attested is **relabelled
     `descendant (patronymic)`** — a patronymic (Paijavana "son of Pijavana", naptṛ
     "descendant") attests descent, not a specific generation. This is the data-side
     fix for the genealogy errors observed in the wild (e.g. a model calling Sudās the
     "father of Divodāsa", or merging Sudās into the Purukutsa–Trasadasyu line). The
     audit is systematic and corpus-wide; it must not be driven by any gold or
     G2-series case.
   - **Status (2026-11-21): EXECUTED incl. the v3 owner decisions — see
     `docs/phase1_correction_report.md`.** The gold-seeded entries are deleted and re-sourced by
     frozen corpus-wide rules; none of the three is reproduced by a systematic source (L3b, added
     after seeing it fire on a dev verse, flags `devávant-` at its glossary-cited verse). Greedy
     before/after on G1–G19 (programmatic /15): 26b 8→5, e4b 5→5; **G15 and G3 were contamination
     passes**. L1 disabled; `rohita` context-gated; KG held-out relations tagged (101/4,106) with a
     loader filter; evals are now greedy. Open: display-name regression (macrons), 800-line KG
     context in the 7.18 prompts, GAZETTEER clear FPs, G7 ablation, judge grading (blind pack
     ready), remaining Trasadasyu→Kuru fields. Phase 2 has NOT been started.

2. **Dev vs test split.**
   - The **gold G-series (G1–G19) is now a DEVELOPMENT set** — used to build and tune
     the data layer and checks.
   - The **frozen "G2-series" test set** is **authored & frozen 2026-11-20, 20 cases**
     (manifest: `llm_lab/llm_lab/domains/vedic/eval/g2_test_manifest.json`, in the
     llm_lab repo; the case file itself is kept outside the repos by the owner and is
     not available to data/training agents). Never inspect or reconstruct the cases.
     Its excluded units join the training exclusion list (below).
   - **Never use the test set to iterate.** It is read once, at evaluation time.

3. **Fixed case sets, fixed denominators.** Always report on the whole fixed set
   (G1–G19 for dev; the full G2-series for test). Never quote a score whose
   denominator changed because cases were added/removed mid-stream. When the set
   grows, re-baseline every model on the new full set.

4. **KG trust tier.** The self-built KG (`vedic_relations.json`) contains
   model-generated errors; it may be used **only at its `authoritative` provenance
   tier**. `inferred`/`itihasa` tiers are not a data source for flags or labels.

---

## Phase 2 — Non-RV segmentation (coverage report FIRST)

**Goal:** give AB/ŚB/TS/VS/AVŚ the same per-token padapāṭha + morphology grounding the
RV has (from VedaWeb), so G1/G17/G18-type cases become answerable.

**Source:** the Digital Corpus of Sanskrit (DCS) — sandhi-split, lemmatised,
morphologically tagged.

### 2a. Licence (gate before any download)
- **Verify the DCS licence explicitly** (CC-BY vs CC-BY-SA — they differ materially;
  share-alike propagates to derivatives). Record the exact licence + version + URL in
  `NOTICE` and in the data folder's own `LICENSE`.
- Keep all DCS-derived sidecars in a **separate data folder** (e.g.
  `knowledge_store/dcs/`) carrying that licence, so the share-alike obligation (if
  any) is isolated and auditable, and not conflated with the MIT-code / CC-BY-RV data.

### 2b. Coverage report (decision gate — build nothing yet)
For each indexed non-RV text, produce a table:
`text → DCS sections available / our corpus sections → % coverage, tag density`.
Only build sidecars for texts above a coverage threshold; **list the gaps explicitly**
(e.g. ŚB Book 12 is absent from our corpus regardless; where does DCS stop?).

### 2c. Citation alignment
DCS citations ≠ our scheme (`॥ ŚB K.A.B.V ॥`, `॥ AB P.A.S ॥`, `॥ TS K.P.A.V ॥`). Build
a per-text citation mapper and **report the match rate**; never silently drop a verse
(same discipline as the RV 10,552/10,552 VedaWeb alignment).

### 2d. Build non-RV sidecars
Same shape as `morphology_rv.json` / `padapatha_rv.json` →
`knowledge_store/dcs/morphology_{avs,ts,vs,ab,pb,sb}.json`. `padapatha.py` generalises:
a `verse_key()` per corpus, one loader, the same prompt block. **Sidecar JSON only —
no Qdrant writes.**

### 2e. Fallback for texts DCS lacks
Where DCS has no segmentation: generate **deterministic sandhi-splitter candidates**
(rule-based) + a **model choice** among them, and emit the result **labelled
"segmentation not verified"** so the synthesis prompt (and any reward) treats it as
provisional, never as annotated ground truth.

### 2f. Validate
Re-freeze + re-run G1/G17/G18 grounded; measure the delta exactly as the RV name/alt
layer was measured. Report on the fixed set.

---

## Phase 3 — Tier-2 commentary labels

**Goal:** let the model attribute a reading to a commentator and distinguish it from
what the saṃhitā attests (G13: "Purukutsa = Sāyaṇa's identification, Tier-2; ŚB reads
the horse").

- **Source: Sāyaṇa's bhāṣya text where digitised** (e.g. GRETIL/DCS Sāyaṇa), parsed
  for the identification claims — **not** reverse-engineered from gold-case needs
  (contamination rule). The KG may contribute only at its `authoritative` tier.
- Add a `knowledge_store/commentary_rv.json` keyed `verse → [{source: "Sāyaṇa", claim,
  tier: 2, citation}]`, mirroring the KG provenance tiers (`authoritative > itihasa >
  inferred`; commentary = Tier-2, never allowed to overwrite Tier-1 attestation).
- **Prompt rule** (like the name/alternatives rules): "A claim marked «Tier-2
  (Sāyaṇa)» is a commentator's identification, not the saṃhitā — attribute it
  explicitly and separate it from what the text attests."
- **Validate** on G13 (grounded re-freeze + re-run), fixed-set reporting.

---

## SFT data-generation design

**Goal:** teach format discipline + attest/infer/commentary calibration (what context
cannot fix), without ever touching the gold *or* G2-series test verses.

### Sources
- **Prompts:** the *grounded* synthesis prompts (padapāṭha + name flags + systematic
  alternatives + Phase-2 non-RV sidecars + Phase-3 commentary labels) over the corpus.
- **Teacher (candidates, not gold):** the strongest available grounded model
  (Gemini when credits allow, else gemma4-26b-a4b grounded) produces candidate
  analyses. These are **filtered** (below), never used raw.

### Held-out split (hymn-level, auditable)
- **Exclude entire hymns/sections, not single verses** — the pipeline expands to full
  hymns, so a held-out verse would leak via its neighbours.
- **Permanently exclude every gold (G-series) AND G2-series case's whole hymn** from
  training. G-series hymns: RV 7.18, 3.53, 1.112, 1.63, 10.60, 1.184, 6.61, ŚB
  13.5.4 / 1.4.1, AB 7.13. **G2-series excluded units (15, from the frozen manifest):**
  RV 1.131, RV 1.174, RV 4.38, RV 5.27, RV 6.20, RV 7.96, RV 8.19, RV 10.33, RV 10.75,
  AVŚ 5.4, AVŚ 19.39, PB 13.3, ŚB 1.8.1, ŚB 11.5.1, AB 8.21.
- **Fail-loud exclusion loader (mandatory).** Every SFT/DPO/GRPO data builder AND
  every data-layer seed script (name flags, alternatives, commentary labels, glosses,
  KG writes) **must load `excluded_units` from the G2 manifest at runtime and raise a
  loud error (not a warning, not a skip) if any excluded text — by citation or hymn
  unit — appears in its inputs or outputs.** The exclusion list is read from the
  manifest, never hardcoded, so freezing a new test set updates every builder at once.
- ~80/10/10 train/val/dev-test on the **remaining** hymns, stratified by chronology
  layer and corpus (so non-RV is not starved).

### Reward / judge filtering of teacher outputs
- **Reward filter = the same check functions** (gold checks generalised to arbitrary
  verses via the sidecars), run as a quality gate: keep a teacher output only if it
  uses the stored tags, honours the proper-name flags, presents alternatives as
  disputed, avoids the `forbidden` over-assertions, and separates
  attest/infer/commentary. One source of truth for eval, SFT-filtering, and the later
  GRPO reward.
- **Judge = a model NOT being trained.** When filtering gemma outputs, the judge is
  e.g. **qwen3.6-27b** (a different family, not in the SFT loop), scoring calibration
  on a rubric; keep only outputs above threshold. Never let a model judge data it will
  be trained on.
- **Contrastive pairs:** keep a model's *wrong* reading (e.g. "possessing gods")
  paired with the corrected one, for preference tuning (DPO/GRPO) — targets the
  catalogued failure modes directly.
- **Dedup + balance:** cap per-lemma / per-hymn frequency so Indra/Agni don't dominate.

### Train
SFT on the filtered set → GRPO with the check-function reward (the MoE smoke test
confirmed load → LoRA(frozen router) → SFT → GRPO all run on gemma4-26b-a4b) →
distil to gemma4-e4b (same tokenizer → logit distillation). Evaluate **once** on the
G2-series test set, fixed denominator.

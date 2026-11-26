# GEMINI.md — Vedic Sanskrit Tutor / Resource

RAG system over the Vedas in **original Devanāgarī Sanskrit** (not colonial-era
English translations). Ask in English, Devanāgarī, or IAST; get answers grounded in
retrieved verses, with exact citations.
- Live web app: `vedic-sanskrit-resource.streamlit.app`
- Repo: `github.com/stewari1210/Vedic-Sanskrit-Tutor` · Owner: Shiv Tewari

**Project root = this directory (`/Users/shivendratewari/claude/vedic_rag`).**
Ignore the untracked nested `Vedic-Sanskrit-Tutor/` copy (stale/partial), plus
`archive/`, `library/`, and `legacy_local_store_pdf_extracts/` (local-only, gitignored).

## Session Memory & Reference Docs

- **Read [memory.md](./memory.md) before any non-trivial change** (private, gitignored —
  contains durable decisions, rationale, gotchas, bug history, owner preferences, and open threads).
  Never copy private details from `memory.md` or `PROJECT_STATUS.md` into public docs or commits.
- **iOS port docs:** architecture, benchmarks, locked decisions, and the
  pre-distribution licensing checklist live in `ios/docs/` inside the private,
  separate `ios/` git repo (nested, gitignored here) — not in this public repo.

## Security — Non-Negotiable

NEVER commit secrets in any form: `secrets.toml*`, `*.toml.bak`, and `.streamlit/secrets*`
are all gitignored. Always use `.env` locally and the Streamlit Cloud secrets panel for
deployment. Never print, paste, or read `.env` / `secrets.toml` contents into chat or
commits. Do not put cluster IDs or API keys in `GEMINI.md`, `CLAUDE.md`, or `README.md`.

## Run

### Web App (Python 3.11)
```bash
streamlit run src/sanskrit_tutor_frontend.py       # main app (Python 3.11)
./run_sanskrit_tutor_web.sh                        # conda env `vedic-tutor`, port 8502
```

Config goes through `get_config_value()` in [src/config.py](./src/config.py)
(env → `.env` → Streamlit secrets). Needed: `GEMINI_API_KEY`, `QDRANT_URL`,
`QDRANT_API_KEY`, `COLLECTION_NAME=ancient_history`, `LLM_PROVIDER=gemini`, and
`EMBEDDING_PROVIDER=local-multilingual` — **the embedding model must match what the
collection was indexed with, or retrieval silently returns nothing.** Template:
[env.template](./env.template). System packages ([packages.txt](./packages.txt)):
`git-lfs`, `pandoc`, `espeak-ng`. Dependency pins in [requirements.txt](./requirements.txt)
are deliberate (`langchain 1.2.0` / `langgraph 1.0.5`) — don't float them.

### iOS App (SwiftUI + CoreML + LiteRT-LM)
- Project: [ios/VedicResource/VedicResource.xcodeproj](./ios/VedicResource/VedicResource.xcodeproj)
- Build check:
  ```bash
  xcodebuild -project ios/VedicResource/VedicResource.xcodeproj -scheme VedicResource -destination generic/platform=iOS CODE_SIGNING_ALLOWED=NO build
  ```
- On-device retrieval uses bundled SQLite (`corpus.sqlite`, `lexicon.sqlite`, `mw.sqlite`,
  `padapatha.sqlite`), fp16 vectors, and CoreML `QueryEncoder.mlpackage` (XLM-R int8).
- On-device Writer uses **LiteRT-LM** (`0.19.1`, GPU Float32) with user-supplied
  `gemma-4-E4B-it.litertlm` (not bundled, loaded from Files/Documents), followed by
  visible §12 citation validation (`CitationValidator.swift`).

## Build the Corpus (run on the owner's Mac, not in a sandbox)

Each script fetches the real source, converts to Devanāgarī, uploads to Qdrant
**and re-syncs the BM25 pickle**. Always `--dry-run` first where supported.

```bash
python rebuild_mandala_clean.py all        # RV (sanskritdocuments .itx)
python ingest_{atharvaveda_shaunaka,taittiriya_samhita,vajasaneyi_samhita,
               shatapatha_brahmana,aitareya_brahmana,pancavimsa_brahmana}.py
python ingest_rv_anukramani.py             # → knowledge_store/anukramani_rv.json
python build_corpus_lexicon.py             # after ANY corpus change
python seed_kg.py && python migrate_kg_to_qdrant.py   # both support --dry-run
```

Never hand-type corpus text; scripts must fetch from the real source. These hit
cloud Qdrant (delete+upload) — don't run them without the user asking.

## Architecture (Where to Look)

### Python Web App
- [src/sanskrit_tutor_frontend.py](./src/sanskrit_tutor_frontend.py) — Streamlit UI;
  modes: conversation (Home chat), grammar, vocabulary, translation (Verse Translation tab),
  pronunciation, quiz. Per-answer export to `.md` and `.docx` (pandoc, degrades gracefully).
- [src/utils/agentic_rag.py](./src/utils/agentic_rag.py) — LangGraph:
  `classify_and_plan → execute_tools → synthesize → evaluate → refine`. Query types:
  `factual` / `construction` / `grammar`. A pinned verse always forces `factual`.
  `SYNTHESIS_DOC_BUDGET = 12`.
- [src/utils/retriever.py](./src/utils/retriever.py) — `HybridRetriever`: semantic
  (Qdrant, 0.7) + BM25 (0.3, local pickle) + Devanāgarī lexical rescue + Monier-Williams
  expansion. `_detect_source_text_filter` / `_filter_docs_by_source` restrict retrieval
  to a named corpus via the `veda` payload field; `_expand_hymn_context` expands hits to
  the full hymn.
- [src/utils/devanagari_lexical.py](./src/utils/devanagari_lexical.py) — `GAZETTEER`
  (names) + `THEME_GAZETTEER` (English themes → corpus-verified Devanāgarī). Extend these
  for new vocabulary.
- [src/utils/vedic_kg.py](./src/utils/vedic_kg.py) — self-building KG; **source of truth
  is the Qdrant collection `vedic_kg`**, local `knowledge_store/vedic_relations.json` is
  only a mirror. Provenance tiers: `authoritative` > `itihasa` > `inferred` (inferred can
  never overwrite the others). `anukramani.py` injects ṛṣi/devatā/meter/legend for pinned hymns.
- [src/utils/pronunciation.py](./src/utils/pronunciation.py) — engines: `espeak` (default;
  Kannada-routed), `vagdhenu` (remote HF Space, classical chant only), `gtts` (legacy).
  Accent marks must survive the pipeline (`assert_accents_preserved`).
- [src/settings.py](./src/settings.py) — `Settings.invoke_llm`, and
  `Settings.extract_llm_text()`: **always use it instead of `response.content`** (newer
  Gemini returns a list of blocks).
- Paths (`local_store`, `vector_store`) are anchored to project root in
  [src/config.py](./src/config.py) — never cwd-relative.

### iOS App (`ios/VedicResource/VedicResource/`)
- `UI/` — `ConversationView.swift`, `ConversationModel.swift`, `TurnView.swift`,
  `GlossView.swift`, `WriterSettingsView.swift`, `CreditsView.swift`, `Theme.swift`
  (forced light Parchment palette: `#F7F1E4` page, `#FDFAF1` card, `#B95113` saffron).
- `Retrieval/` — Swift parity port of `HybridRetriever` (`Retriever.swift`, `BM25.swift`,
  `VectorIndex.swift`, `TextEncoder.swift`, `QueryEnhancer.swift`, `LemmaIndex.swift`,
  `CorpusStore.swift`, `BundleVerifier.swift`).
- `Writer/` — `WriterModel.swift` (LiteRT-LM engine + sampling settings),
  `ModelLocator.swift`, `PromptBuilder.swift` (token-budgeted prompt assembly),
  `GemmaTokens.swift`, `CitationValidator.swift` (§12 visible citation checks),
  `Padapatha.swift`, `WriterTemplates.swift`.

## Corpus & Citation Formats

Chronology layers: `1` = RV 2–7 · `2` = RV 1/8/9/10 · `3` = AVŚ, AVP, VS, TS, MS ·
`4` = AB, PB, ŚB, KB, GB (`chronology_note="late Brāhmaṇa"`), BĀU, ChU · `5` = Nirukta (`source_type="commentary"`).
Chunks are verse-per-line (or ~120-token word-boundary sliding windows with ~20-token overlap
and native citations for long Tranche 1+ prose); payload fields: `veda`, `chronology_layer`,
`chronology_name`, `filename`, `source_type` (`"vedic_text"` or `"commentary"`).

`॥ RV M.SSS.VV ॥` · `॥ AVŚ K.H.V ॥` · `॥ AVP K.H.V ॥` · `॥ VS A.V ॥` · `॥ TS K.P.A.V ॥` ·
`॥ MS K.P.A ॥` · `॥ AB P.A.S ॥` · `॥ PB K.A.V ॥` · `॥ SB K.A.B.V ॥` · `॥ KB A.K.S ॥` ·
`॥ GB B.P.K ॥` · `॥ BĀU A.B.K ॥` · `॥ ChU P.K.V ॥` · `॥ Nir A.K ॥`
(In `local_store/rNN.md` the RV danda markers are `॥ M.SSS.VV ॥` without the `RV`; the
prefix is in the `## RV M.SSS` header.)

Not indexed: Kāṭhaka Saṃhitā, Kapiṣṭhala-Kaṭha Saṃhitā, Jaiminīya Brāhmaṇa, Jaiminīya Upaniṣad Brāhmaṇa, Taittirīya Brāhmaṇa, Taittirīya Āraṇyaka, Baudhāyana Śrauta Sūtra; SB Book 12 (GRETIL 404).

## Rules for Changes

- **Answers must come from the Sanskrit corpus, never from borrowed English translations.**
  Griffith/Eggeling/Caland are an internal cross-check layer only. Interpretation claims
  must be justified from the words and grammar.
- Keep keyword routing conservative: substring keywords misfire (e.g. `"construct"`
  matched "constructing" and sent research queries to the English→Sanskrit translator;
  `"vs"` collides with English "versus"). Use whole-word/phrase matching.
- Any script that writes to Qdrant must re-sync the BM25 pickle ("two indexes, one truth").
- Don't strip Devanāgarī diacritics/accents in any text path; don't silently swallow
  failures (log loudly).
- UI theme is forced light parchment (`.streamlit/config.toml` + CSS overrides on web;
  `Parchment` + `.preferredColorScheme(.light)` on iOS) — don't remove it.
- Be cost-aware: public web app bills the owner's Gemini/Qdrant quota. Synthesis stays on
  Gemini flash; prefer gated extra LLM calls over upgrading the always-on model.
- Public docs: [README.md](./README.md), [LICENSE](./LICENSE) (MIT, code only),
  [NOTICE](./NOTICE) (data provenance). Keep corpus licensing out of the MIT grant.
  `PROJECT_STATUS.md` and [memory.md](./memory.md) are private (gitignored).

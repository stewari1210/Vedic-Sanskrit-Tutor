# Tranche 1 (GRETIL) — Dry-Run Report (Sliding-Window Re-Estimate & Qdrant Headroom)

**Branch:** `corpus-expansion`  
**Script:** `ingest_tranche1_gretil.py --dry-run`  
**Qdrant calls made for upload:** **0** (upload held pending owner sign-off; read-only `/telemetry` check only).  
**Unit tests:** `pytest tests/test_corpus_expansion_infra.py` — **64/64 passed**.

---

## 1. Per-Text Summary & Sliding-Window Re-Estimate (~120 Encoder Tokens, ~20 Overlap)

Every native unit exceeding 128 encoder tokens (`paraphrase-multilingual-mpnet-base-v2`) is split
by `src/utils/windowing.py` (`make_sliding_windows`) into ~120-token windows with ~20 tokens of
overlap, cut strictly at whitespace word boundaries (never inside a Devanāgarī grapheme cluster).
Every window retains the **exact native citation** (e.g. `MS 1.6.3`, never `MS 1.6.3a`), adds
`part` (`0..n_parts-1`), `n_parts`, and window-level `text_search`, stores full native unit text
once (`metadata["text"]` on `part == 0` + sidecar `local_store/<dir>/<dir>_units.json`), and
writes exact 1-to-1 windows to `local_store/<dir>/<dir>_windows.jsonl` for `rebuild_bm25_pickle.py`.
At retrieval, `HybridRetriever._deduplicate_windowed_docs()` keeps each unit's best-scoring
window, reconstructs the full native unit, and `CitationFormatter` centers excerpts around the
matching window within budget.

| Text | `veda` | Layer | `source_type` | Native units | Units split | Window pts (Qdrant & BM25) | Windows >128 tok | Max tok | Visarga bugs (`ह्`) | Vec+HNSW MB | Payload MB | Est. Total MB |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Maitrāyaṇī Saṃhitā (`MS`) | `maitrayani_samhita` | 3 | `vedic_text` | 653 | 543 | **3,606** | **0** | 128 | **0 (PASS)** | 14.79 | 10.04 | **24.83 MB** |
| Atharvaveda Paippalāda (`AVP`) | `atharvaveda_paippalada` | 3 | `vedic_text` | 7,673 | 21 | **7,698** | **0** | 128 | **0 (PASS)** | 31.56 | 12.76 | **44.32 MB** |
| Kauṣītaki Brāhmaṇa (`KB`) | `kausitaki_brahmana` | 4 | `vedic_text` | 6,914 | 1 | **6,915** | **0** | 123 | **0 (PASS)** | 28.35 | 7.43 | **35.78 MB** |
| Gopatha Brāhmaṇa (`GB`) | `gopatha_brahmana` | 4 | `vedic_text` | 256 | 230 | **970** | **0** | 128 | **0 (PASS)** | 3.98 | 2.68 | **6.66 MB** |
| Bṛhadāraṇyaka Upaniṣad, Kāṇva (`BĀU`) | `brihadaranyaka_upanisad` | 4 | `vedic_text` | 432 | 83 | **566** | **0** | 128 | **0 (PASS)** | 2.32 | 1.37 | **3.69 MB** |
| Chāndogya Upaniṣad (`ChU`) | `chandogya_upanisad` | 4 | `vedic_text` | 622 | 14 | **637** | **0** | 128 | **0 (PASS)** | 2.61 | 1.28 | **3.89 MB** |
| Nirukta (`Nir`) | `nirukta` | 5 | `commentary` | 450 | 319 | **1,008** | **0** | 128 | **0 (PASS)** | 4.13 | 2.54 | **6.67 MB** |
| **TOTAL** | **7 texts** | **L3–L5** | **6 primary + 1 comm.** | **17,000** | **1,211** | **21,400** | **0 (0.00%)** | **128** | **0 (PASS)** | **87.74** | **38.10** | **~125.8 MB** |

> **Existing prose truncation note (intentionally unchanged):** The existing `ŚB`, `AB`, `PB`, and `TS` prose chunks already in Qdrant suffer from the same 128-token `mpnet` encoder truncation. Per owner instruction, we are **not** modifying or re-chunking any existing corpus points in this task; only new Tranche 1+ texts use sliding-window splitting.

*Accent note:* Neither GRETIL's `maitrs_pu.htm` nor the verse `<l>` body of `sa_paippalAdasaMhitA.xml` carries udātta/anudātta svaras (combining marks in `avp.xml` were candrabindu `m̐` → `ँ`, `ṝ` → `ṝ`, and accents inside stripped `<note>` tags). Our accent-preservation pipeline (`text` vs `text_search` + `assert_accents_preserved`) is verified by unit tests (`tests/test_corpus_expansion_infra.py`) and active for accented Tranche 2/3 sources.

---

## 2. Qdrant Cloud Cluster Tier, Current RAM / Disk Usage & Headroom

Read-only telemetry collected from Qdrant Cloud (`v1.17.1`, 1-node Leader cluster on GCP `us-east4`):

- **Cluster tier & limits:** Single-node Qdrant Cloud cluster (`number_of_peers = 1`, Qdrant `v1.17.1`). Qdrant's REST `/telemetry` and `/metrics` endpoints do not expose the billing plan name directly, so confirm in the Qdrant Cloud dashboard whether this is the **Free Forever tier (1 GB RAM / 4 GB disk / 0.5 vCPU)** or a paid tier — below headroom is calculated conservatively against the **1 GB RAM / 4 GB disk** free-tier floor.
- **Current cluster usage across all 3 collections:**

| Collection | Points | Indexed vectors | Raw vectors (disk/mmap) | Payloads (mmap) | Total data | Vector storage | Payload storage |
|---|---:|---:|---:|---:|---:|---|---|
| `ancient_history` | 15,003 | 14,452 | 43.95 MB | 19.18 MB | **63.13 MB** | `InRamChunkedMmap` | `mmap` |
| `vedic_kg` | 4,116 | 0 | 0.02 MB | 1.02 MB | **1.04 MB** | `InRamChunkedMmap` | `mmap` |
| `site_stats` | 1 | 0 | 0.00 MB | 0.00 MB | **0.00 MB** | `InRamChunkedMmap` | `mmap` |
| **Cluster total (now)** | **19,120** | **14,452** | **43.97 MB** | **20.20 MB** | **64.17 MB** | — | — |

- **Current jemalloc RAM:** `resident = 25.12 MB`, `allocated = 16.12 MB`, `retained = 57.93 MB` (segments use `InRamChunkedMmap` for vectors and `mmap` for payloads, so idle RSS stays very small and OS page cache backs hot pages).
- **Projected cluster usage AFTER Tranche 1 (+21,400 sliding-window points):**
  - `ancient_history` points: `15,003 → 36,403` (`+142.6%`)
  - Raw vectors (768d fp32): `43.95 MB + 62.70 MB ≈ 106.7 MB`
  - HNSW graph + vectors (~1.4× fp32): `~61.5 MB + ~87.8 MB ≈ 149.3 MB`
  - Payloads (`mmap`): `19.18 MB + 38.10 MB ≈ 57.3 MB`
  - **Total on-disk/mmap footprint (all collections):** `~64.2 MB + ~125.8 MB ≈ ~190 MB` (+ temporary indexing/snapshot overhead ~250–300 MB peak).
  - **Headroom against 1 GB RAM / 4 GB disk free-tier floor:**
    - **RAM headroom:** ~150–210 MB active working set (vectors + HNSW + jemalloc) out of **1,024 MB** (**~80% RAM free** — comfortably fits Tranche 1 AND leaves room for Tranche 2, especially since payloads are `mmap` and `on_disk=True` or scalar int8 quantization can be enabled later if Tranche 2 grows large).
    - **Disk headroom:** ~190–250 MB out of **4,096 MB** (**~94% disk free**).

---

## 3. Source Decisions & Licences (Recorded in `NOTICE` & `docs/ios_data_licensing.md`)

- **Gopatha Brāhmaṇa version choice (GRETIL has two entries):**
  - **Chosen:** `sa_gopathabrAhmaNa.xml` (input by Arlo Griffiths, 2005–06, based on Dieuke Gaastra, Leiden: Brill 1919; CC BY-NC-SA 4.0) — **complete text** (256 kaṇḍikās across Pūrva 1 and Uttara 2), actively hosted, clean TEI markup.
  - **Rejected:** `sa_gopathabrAhmaNa-1.xml` (input by Oliver Hellwig) — covers **only `1,1.1–1,3.6`** (partial fragment of Pūrva Book 1) and returns **HTTP 404** on GRETIL.
- **BĀU & ChU mūla vs commentary:**
  - GRETIL's `corpustei` files (`sa_bRhadAraNyakopaniSadkANva-recension-comm.xml` and `sa_chAndogyopaniSad-comm.xml`) are dominated by 8th-century CE Śaṅkarabhāṣya (out of scope: composed after c. 0 BCE).
  - We used GRETIL's standalone **mūla-only** files (`brup___u.htm` Kāṇva recension and `chup___u.htm`, both checked against Limaye & Vadekar 1958 and TITUS) so 100% of indexed text is original pre-0 BCE Upaniṣad text.
- **Maitrāyaṇī Saṃhitā editorial footnotes:** `<span class="red">` (German/English FN) and `<span class="blue">` (Schroeder page numbers) stripped before transliteration.
- **Nirukta ASCII-visarga normalization:** Tokunaga's `sa_yAska-nirukta.xml` typed ASCII word-final `h` instead of `ḥ` in quoted RV verses (1,118 cases); `fix_iast_ascii_visarga()` normalized them cleanly while preserving real Sanskrit bare roots (`वह्`, `रोह्`, etc.), reducing visarga bugs to **0**.
- **Provenance JSONs written:** `knowledge_store/sources/{maitrayani_samhita,atharvaveda_paippalada,kausitaki_brahmana,gopatha_brahmana,brihadaranyaka_upanisad,chandogya_upanisad,nirukta}.json`.
- **Licensing note:** All 7 texts are CC BY-NC-SA 4.0 or GRETIL/TITUS non-commercial scholarly use; recorded in both `NOTICE` and `docs/ios_data_licensing.md` as ineligible for any paid/monetised app.

---

## 4. Proper Noun & Gazetteer Summary (`knowledge_store/gazetteer_additions.json`)

- **Priority names found (14/19):** `kuru` (125), `pancala` (5), `kuru_pancala` (3, `GB 1.2.10` / `BĀU`), `videha` (21), `kosala` (3, `ChU 4.10.1`), `kasi` (18), `matsya` (13), `vasa` (525), `gandhari` (5, `AVP 12.2.2` / `ChU`), `parsu` (41), `ayu` (531), `janaka` (21, `GB 2.6.12` + 15× `BĀU`), `pravahana_jaivali` (11), `asvapati_kaikeya` (2, `ChU 5.11.4`).
- **Priority names NOT found in Tranche 1 (5/19):** `usinara`, `aratta`, `amavasu` *(expected in Tranche 2 `BŚS 18.44`)*, `bhagiratha` *(expected in Tranche 2 `JUB`)*, `mandhatr`.
- **Existing `GAZETTEER` entries gaining Tranche 1 attestations:** 93 / 112.
---

## 5. Pre-Upload Qdrant Backup Record (Archived in Gitignored `archive/qdrant_backups/`)

Both backup artifacts are stored locally under `archive/qdrant_backups/` (confirmed gitignored by `.gitignore:39:archive/`). Repeat this exact snapshot + point-export + SHA-256 archive procedure before Tranche 2 upload.

| Artifact | Path | Bytes | SHA-256 |
|---|---|---:|---|
| Pre-Tranche-1 point export (15,003 pts) | `archive/qdrant_backups/pre_tranche1_ancient_history_points_20261124T032711Z.jsonl` | 2,532,883 | `3a0d24080b73d426569278ccb6b706e9e758d83280106ab8f49b7520befc1118` |
| Pre-Tranche-1 Qdrant Cloud snapshot | `archive/qdrant_backups/ancient_history-566175271228458-2026-11-24-03-27-07.snapshot` | 113,152,512 | `a15f799bb29b5c013072dad645bc42854feaebb79d43c20c004dac61b326b765` |


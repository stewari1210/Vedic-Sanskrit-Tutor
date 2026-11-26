#!/usr/bin/env python3
"""
Regenerate vector_store/ancient_history/docs_chunks.pkl from local_store.

Supports:
  - Windowed corpora (`local_store/<dir>/<dir>_windows.jsonl`) — loads the exact
    ~120-token sliding windows uploaded to Qdrant so BM25 and Qdrant describe the
    exact same points 1-to-1 ("two indexes, one truth").
  - Legacy single-file folders (`local_store/avs/avs.md` + `avs_metadata.json`)
  - Legacy multi-file folders (`local_store/sb/sb_01.md..sb_14.md` + `sb_metadata.json`)
  - Accented texts: keeps accented Devanagari in `page_content` / `metadata["text"]`
    and attaches accent-stripped `metadata["text_search"]` for BM25/lexical matching.
  - `--check`: verify that the pickle exists and matches current `local_store` chunk
    counts per `veda` (no write).

Run on Mac after any upload script, then restart Streamlit:
    python rebuild_bm25_pickle.py
    python rebuild_bm25_pickle.py --check
"""
import argparse
import json
import pickle
import shutil
import sys
from collections import Counter
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from langchain_core.documents import Document
from src.utils.index_files import chunk_doc
from src.utils.citations import strip_vedic_accents, has_vedic_accents
from src.config import COLLECTION_NAME, LOCAL_FOLDER

LOCAL_STORE = Path(LOCAL_FOLDER)  # anchored to project root in config
PKL = PROJECT_ROOT / "vector_store" / str(COLLECTION_NAME) / "docs_chunks.pkl"


def load_all_local_chunks() -> list[Document]:
    legacy_docs: list[Document] = []
    windowed_chunks: list[Document] = []

    for folder in sorted(d for d in LOCAL_STORE.iterdir() if d.is_dir()):
        meta_path = folder / f"{folder.name}_metadata.json"
        base_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"filename": folder.name}
        win_jsonl = folder / f"{folder.name}_windows.jsonl"
        if win_jsonl.exists():
            # Windowed corpus (Tranche 1+): exact 1-to-1 points matching Qdrant
            count = 0
            with win_jsonl.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    windowed_chunks.append(Document(page_content=rec["page_content"], metadata=rec["metadata"]))
                    count += 1
            print(f"✅ {folder.name}: {base_meta.get('title', '?')} ({count:,} exact windows)")
            continue

        single_md = folder / f"{folder.name}.md"
        md_files = [single_md] if single_md.exists() else sorted(folder.glob("*.md"))
        if not md_files:
            continue
        for md in md_files:
            m = dict(base_meta)
            if len(md_files) > 1:
                m.setdefault("part_file", md.name)
            legacy_docs.append(Document(page_content=md.read_text(encoding="utf-8"), metadata=m))
        print(f"✅ {folder.name}: {base_meta.get('title', '?')} ({len(md_files)} file{'s' if len(md_files)!=1 else ''})")

    assert legacy_docs or windowed_chunks, f"No documents found in {LOCAL_STORE}"
    chunks = chunk_doc(legacy_docs) if legacy_docs else []
    chunks.extend(windowed_chunks)

    # Ensure accented chunks carry accent-stripped text_search while keeping accented page_content
    for c in chunks:
        if has_vedic_accents(c.page_content):
            c.metadata.setdefault("text", c.page_content)
            c.metadata.setdefault("text_search", strip_vedic_accents(c.page_content))
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="Verify existing BM25 pickle matches local_store without writing.")
    args = ap.parse_args()

    chunks = load_all_local_chunks()
    local_counts = Counter(c.metadata.get("veda", c.metadata.get("filename", "?")) for c in chunks)
    print(f"✂️  {len(chunks):,} chunks across {len(local_counts)} corpora")

    if args.check:
        if not PKL.exists():
            print(f"❌ BM25 pickle missing: {PKL}")
            sys.exit(1)
        with open(PKL, "rb") as f:
            pkl_chunks = pickle.load(f)
        pkl_counts = Counter(c.metadata.get("veda", c.metadata.get("filename", "?")) for c in pkl_chunks)
        if pkl_counts != local_counts:
            print("❌ BM25 pickle OUT OF SYNC with local_store:")
            for k in sorted(set(local_counts) | set(pkl_counts)):
                lc, pc = local_counts.get(k, 0), pkl_counts.get(k, 0)
                if lc != pc:
                    print(f"   {k}: local_store={lc:,} vs pickle={pc:,}")
            sys.exit(1)
        print(f"✅ BM25 pickle IN SYNC ({len(pkl_chunks):,} chunks across {len(pkl_counts)} corpora)")
        for k, v in sorted(pkl_counts.items()):
            print(f"   {k:28s}: {v:,}")
        return

    # Sanity: key proper nouns must be searchable (accent-stripped)
    joined = " ".join(c.metadata.get("text_search") or c.page_content for c in chunks)
    for w in ("सुदास", "दाशराज्ञ"):
        print(f"🔎 '{w}' in chunks: {joined.count(w)}")

    PKL.parent.mkdir(parents=True, exist_ok=True)
    if PKL.exists():
        shutil.copy(PKL, PKL.with_suffix(".pkl.bak"))
    with open(PKL, "wb") as f:
        pickle.dump(chunks, f)
    print(f"💾 Wrote {PKL} ({PKL.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()

"""Simple CLI to process a hardcoded PDF, build the index and ask questions.

Usage:
  - Edit HARDCODED_PDF below to point to your PDF, OR
  - Run with --pdf /full/path/to/file.pdf to override the hardcoded path.

This script will:
  1. Copy the PDF into the project's LOCAL_FOLDER/COLLECTION_NAME directory.
  2. Call `process_uploaded_pdfs` to convert it to markdown and extract metadata.
  3. Create the Qdrant vector store and retriever.
  4. Start a simple REPL to ask questions against the indexed document.

Note: the processing function deletes the copied PDF after processing (same behavior
as the Streamlit frontend). If you want to keep the original, point to a different
source location when overriding with --pdf.
"""
import argparse
import os
import shutil
import json

from helper import project_root, logger
from config import LOCAL_FOLDER, COLLECTION_NAME, VECTORDB_FOLDER
from utils.process_files import process_uploaded_pdfs
from utils.index_files import create_qdrant_vector_store
from utils.retriever import create_retriever
from utils.final_block_rag import create_langgraph_app, run_rag_with_langgraph


# Change this to your preferred default PDF (absolute or relative to project root).
# Example relative path: os.path.join(project_root, "examples", "my_doc.pdf")
HARDCODED_PDF = os.path.join(project_root, "sample.pdf")


def prepare_and_process(pdf_path: str):
    """Copy PDF into LOCAL_FOLDER/COLLECTION_NAME and call processing."""
    target_folder = os.path.join(project_root, LOCAL_FOLDER, COLLECTION_NAME)
    os.makedirs(target_folder, exist_ok=True)

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    dest_path = os.path.join(target_folder, os.path.basename(pdf_path))
    # copy the file so process_uploaded_pdfs behaves like the frontend
    shutil.copy2(pdf_path, dest_path)
    logger.info(f"Copied PDF to {dest_path}")

    # process the copied file (this removes the file after processing)
    process_uploaded_pdfs([dest_path], extract_metadata=True)


def build_index_and_retriever(force: bool = False):
    """Create Qdrant vector store and retriever from processed docs.

    If `force` is True, remove any existing vector store directory and
    the chunks file so indexing starts from a clean state.
    """
    # Remove previous vector store and chunks file if forcing a clean index
    if force:
        vec_store_path = os.path.join(project_root, VECTORDB_FOLDER, COLLECTION_NAME)
        chunks_file = os.path.join(vec_store_path, "docs_chunks.pkl")
        try:
            if os.path.isdir(vec_store_path):
                shutil.rmtree(vec_store_path)
                logger.info("Removed existing vector store at %s", vec_store_path)
        except Exception:
            logger.exception("Failed to remove existing vector store %s", vec_store_path)

        try:
            # If chunks file existed elsewhere, attempt deletion as well
            if os.path.isfile(chunks_file):
                os.remove(chunks_file)
                logger.info("Removed existing chunks file %s", chunks_file)
        except Exception:
            logger.exception("Failed to remove chunks file %s", chunks_file)

    vec_db, docs = create_qdrant_vector_store(force_recreate=True)
    retriever = create_retriever(vec_db, docs)
    return vec_db, docs, retriever


def run_repl(retriever):
    app = create_langgraph_app(retriever)
    print("\nReady. Enter questions (type 'exit' or 'quit' to stop).\n")
    while True:
        try:
            question = input("Q> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        graph_state = {
            "question": question,
            "chat_history": [],
            "documents": [],
            "answer": "",
            "enhanced_question": "",
            "is_follow_up": False,
            "reset_history": False,
        }

        result = run_rag_with_langgraph(graph_state, app)
        if isinstance(result, str):
            # sometimes returns serialized JSON
            try:
                parsed = json.loads(result)
            except Exception:
                print(result)
                continue
            result = parsed

        # result expected to be a dict with "answer"
        if isinstance(result, dict):
            answer = result.get("answer")
            # If the answer is a structured object with 'answer' text inside
            if isinstance(answer, dict):
                print(answer.get("answer", "(no answer returned)"))
            else:
                print(answer)
        else:
            print(result)


def main():
    parser = argparse.ArgumentParser(description="Process a hardcoded PDF and query it via CLI")
    parser.add_argument("--pdf", type=str, help="Path to PDF (overrides hardcoded path)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force clean reindex: delete any existing vector store and chunks before indexing",
    )
    args = parser.parse_args()

    pdf = args.pdf or HARDCODED_PDF
    if not os.path.isabs(pdf):
        # make relative paths relative to project root
        pdf = os.path.join(project_root, pdf)

    try:
        prepare_and_process(pdf)
    except Exception as e:
        logger.error(f"Failed to prepare/process PDF: {e}")
        print(f"Error: {e}")
        return

    try:
        vec_db, docs, retriever = build_index_and_retriever(force=args.force)
    except Exception as e:
        # Log full traceback to help debug where the error originates
        logger.exception("Failed to build index/retriever")
        import traceback

        traceback.print_exc()
        print(f"Indexing error: {e}")
        return

    run_repl(retriever)


if __name__ == "__main__":
    main()

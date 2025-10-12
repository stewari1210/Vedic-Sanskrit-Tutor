import os
import json
import pickle
from pathlib import Path
from langchain_community.vectorstores import Qdrant
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from typing import List

from helper import logger
from config import LOCAL_FOLDER, COLLECTION_NAME, VECTORDB_FOLDER
from settings import Settings


# load all processed markdown files
def load_documents_with_metadata(main_folder: str):
    """
    Loads markdown files and their metadata from the specified folder structure.
    """
    logger.info(f"Loading documents from {main_folder}")
    all_documents = []
    # Loop through each subdirectory, which corresponds to a document
    for filename in os.listdir(main_folder):
        file_path = os.path.join(main_folder, filename)
        logger.info(f"File path {file_path}")
        if os.path.isdir(file_path):
            md_file = os.path.join(file_path, f"{filename}.md")
            json_file = os.path.join(file_path, f"{filename}_metadata.json")

            if os.path.exists(md_file) and os.path.exists(json_file):
                # Load the markdown content
                with open(md_file, "r", encoding="utf-8") as f:
                    md_content = f.read()

                # Load the metadata
                with open(json_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                # Create a LangChain Document object
                doc = Document(page_content=md_content, metadata=metadata)
                all_documents.append(doc)
            else:
                logger.error(f"File does not exists {md_file} and {json_file}")

    logger.info(f"Loaded {len(all_documents)} documents stored in {LOCAL_FOLDER}")
    return all_documents


def chunk_doc(doc: List[Document], chunk_size: int = 512, chunk_overlap: int = 64):
    """
    Chunk the markdown documents
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "# ", "## "],  # Common markdown separators
    )

    # Use the text splitter to create nodes from the single original document.
    # LlamaIndex ensures metadata propagates to the generated nodes.
    chunks = text_splitter.split_documents(doc)

    return chunks


def create_qdrant_vector_store(force_recreate: bool = True) -> Qdrant:
    """
    Creates and populates a local Qdrant vector store.

    Args:
        force_recreate (bool): If True, forces recreation of the collection.

    Returns:
        Qdrant: An initialized LangChain Qdrant vector store object.
    """
    # Initialize Qdrant client to a local path
    vec_store = os.path.join(VECTORDB_FOLDER, COLLECTION_NAME)
    os.makedirs(vec_store, exist_ok=True)
    CHUNKS_FILE = os.path.join(vec_store, "docs_chunks.pkl")

    if force_recreate and not Path(CHUNKS_FILE).is_file():
        logger.info(f"Document Chunks file: {CHUNKS_FILE} does not exist. Re-Indexing")
        # chunk documents
        documents = load_documents_with_metadata(
            os.path.join(LOCAL_FOLDER, COLLECTION_NAME)
        )
        chunks = chunk_doc(documents)

        # save chunks for retrieval
        with open(CHUNKS_FILE, "wb") as f:
            pickle.dump(chunks, f)
        # Create the Qdrant vector store from the documents
        vector_store = Qdrant.from_documents(
            documents=chunks,
            embedding=Settings.embed_model,
            path=VECTORDB_FOLDER,
            collection_name=COLLECTION_NAME,
            force_recreate_collection=force_recreate,
        )
        logger.info(
            f"Successfully created vector store at {VECTORDB_FOLDER}/{COLLECTION_NAME}"
        )
    else:
        logger.info(
            f"Document Chunks file: {CHUNKS_FILE} Present. Returning existing Index"
        )
        with open(CHUNKS_FILE, "rb") as f:
            chunks = pickle.load(f)

        vector_store = Qdrant.from_documents(
            documents=chunks,
            embedding=Settings.embed_model,
            path=VECTORDB_FOLDER,
            collection_name=COLLECTION_NAME,
            force_recreate_collection=False,
        )

        logger.info(f"Returning existing vector store at {VECTORDB_FOLDER}")
    return vector_store, chunks

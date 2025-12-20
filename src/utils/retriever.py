from langchain_community.retrievers import BM25Retriever


def create_retriever(vec_db, documents, top_n=5):
    qdrant_retriever = vec_db.as_retriever()
    bm25_retriever = BM25Retriever.from_documents(documents=documents)
    # Return both retrievers or just one, depending on your use case
    return qdrant_retriever  # or bm25_retriever

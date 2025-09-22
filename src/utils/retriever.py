from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder  # for reranking
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain.retrievers import ContextualCompressionRetriever


def create_retriever(vec_db, documents, top_n=5):
    qdrant_retriever = vec_db.as_retriever()  # vec_db is from index_files

    # --- Create the BM25 Retriever from the same documents ---
    bm25_retriever = BM25Retriever.from_documents(documents=documents)

    # --- Combine the two retrievers into an EnsembleRetriever ---
    ensemble_retriever = EnsembleRetriever(
        retrievers=[qdrant_retriever, bm25_retriever],
        weights=[0.5, 0.5],  # You can adjust these weights
    )

    model_name = "cross-encoder/ms-marco-MiniLM-L6-v2"
    cross_encoder = HuggingFaceCrossEncoder(model_name=model_name)

    # Define the reranker, specifying the number of top documents to keep after reranking
    reranker_compressor = CrossEncoderReranker(model=cross_encoder, top_n=top_n)

    # Combine the hybrid retriever with the reranker
    # The ContextualCompressionRetriever takes a base retriever and a compressor (the reranker)
    # It first retrieves documents and then compresses/reranks them.
    # The ContextualCompressionRetriever takes a base retriever and a compressor (the reranker)
    reranking_retriever = ContextualCompressionRetriever(
        base_retriever=ensemble_retriever,
        base_compressor=reranker_compressor,  # New, correct parameter name
    )

    return reranking_retriever

import asyncio

# This needs to be done once at the top of your script
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from langchain_groq import ChatGroq
from langchain_google_genai import GoogleGenerativeAIEmbeddings


from config import (
    GROQ_API_KEY,
    GEMINI_API_KEY,
    EMBED_MODEL,
    EVAL_MODEL,
    MODEL_SPECS,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)


class Settings:
    embed_model = GoogleGenerativeAIEmbeddings(
        model=EMBED_MODEL,
        google_api_key=GEMINI_API_KEY,
    )

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=MODEL_SPECS["model"],
        max_tokens=MODEL_SPECS["max_tokens"],
        timeout=MODEL_SPECS["timeout"],
        max_retries=MODEL_SPECS["max_retries"],
    )

    evaluator_llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=EVAL_MODEL,
        max_tokens=MODEL_SPECS["max_tokens"],
        timeout=MODEL_SPECS["timeout"],
        max_retries=MODEL_SPECS["max_retries"],
    )
    chunk_size = CHUNK_SIZE
    chunk_overlap = CHUNK_OVERLAP

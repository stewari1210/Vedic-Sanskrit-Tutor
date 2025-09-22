import os
import helper

from keyvault import keyvault  # type: ignore
from dotenv import load_dotenv

load_dotenv()

logger = helper.logger
MODEL_SPECS = {
    "model": os.getenv("MODEL"),
    "temperature": float(os.getenv("TEMPERATURE")),
    "top_p": float(os.getenv("TOP_P")),
    "max_tokens": int(os.getenv("MAX_TOKENS", 2048)),
    "timeout": int(os.getenv("TIMEOUT", 600)),
    "max_retries": int(os.getenv("MAX_RETRIES", 2)),
    "response_format": os.getenv("RESPONSE_FORMAT", None),
    # "seed": int(os.getenv("SEED", 42)),
}

EVAL_MODEL = os.getenv("EVAL_MODEL", "llama-3.2-70b")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ancient_history")
LOCAL_FOLDER = os.getenv("LOCAL_FOLDER", "local_store")
VECTORDB_FOLDER = os.getenv("VECTORDB_FOLDER", "vector_store")
EMBED_MODEL = os.getenv("EMBED_MODEL")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))

CHAT_MEMORY_WINDOW = (
    int(os.getenv("CHAT_MEMORY_WINDOW", "5")) * 2
)  # to account for human and ai messages
TOPIC_CHANGE_WINDOW = (
    int(os.getenv("TOPIC_CHANGE_WINDOW", "3")) * 2
)  # to account for human and ai messages

GEMINI_API_KEY = keyvault.GEMINI_API_KEY

if GEMINI_API_KEY:
    logger.info("GEMINI API Key loaded successfully.")
else:
    logger.warning("GEMINI API Key not found. Please check your keyvault setup.")

GROQ_API_KEY = keyvault.GROQ_API_KEY
if GROQ_API_KEY:
    logger.info("GROQ API Key loaded successfully.")
else:
    logger.warning("GROQ API Key not found. Please check your keyvault setup.")

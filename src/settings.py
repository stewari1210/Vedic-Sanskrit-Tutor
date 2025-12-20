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
    # Only pass `model` if EMBED_MODEL is set. Some deployments don't set this
    # environment variable and the embeddings class will choose a sensible
    # default. Passing None causes pydantic validation errors (Input should be a
    # valid string), so guard the argument.
    # The embeddings class requires a model string. Provide a sensible
    # default if EMBED_MODEL isn't set in the environment.
    # Respect an explicit embedding model configured via EMBED_MODEL. If
    # EMBED_MODEL is not set, omit the model kwarg so the embeddings client
    # can decide a sensible default for the environment (or raise a clearer
    # error). Also prefer ADC over API key authentication when possible; we
    # only pass google_api_key if GEMINI_API_KEY is explicitly provided.
    embed_kwargs = {}
    if EMBED_MODEL:
        embed_kwargs["model"] = EMBED_MODEL
    if GEMINI_API_KEY:
        embed_kwargs["google_api_key"] = GEMINI_API_KEY

    embed_model = GoogleGenerativeAIEmbeddings(**embed_kwargs)

    # Validate Groq model configuration. ChatGroq requires a `model` string
    # during initialization; passing no model causes a pydantic ValidationError
    # that is hard to debug. If a GROQ API key is present but no model is
    # configured, raise a clear error prompting the user to set the MODEL
    # or GROQ_MODEL environment variable.
    groq_model = MODEL_SPECS.get("model")
    if GROQ_API_KEY and not groq_model:
        raise RuntimeError(
            "GROQ_API_KEY is set but no model is configured. Please set the MODEL or GROQ_MODEL environment variable to a valid Groq model name."
        )

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=groq_model,
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

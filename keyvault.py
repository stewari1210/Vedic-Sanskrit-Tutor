"""Simple local keyvault shim.

This module exposes a `keyvault` object with attributes expected by
`src/config.py` (e.g., `GEMINI_API_KEY`, `GROQ_API_KEY`). It reads values
from environment variables (and from a `.env` file when present).

Create a `.env` file in the project root containing lines like:

GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_groq_key_here

Or export the variables in your shell before running the app.
"""
from dotenv import load_dotenv
from pathlib import Path
import os
import logging

# Try a best-effort load of a .env file. Calling load_dotenv() with no
# arguments can fail in some non-standard invocation contexts (see
# AssertionError in find_dotenv). Prefer an explicit path to the project's
# .env in those cases.
logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent
env_path = project_root / ".env"
try:
    # First try the default call which is simplest and works in normal cases
    load_dotenv()
except AssertionError:
    # Fall back to an explicit path (safe in all execution contexts)
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
        logger.info(f"Loaded .env from {env_path}")
    else:
        logger.debug("No .env file found at project root; continuing without it")
except Exception as exc:  # pragma: no cover - defensive
    logger.warning(f"Unexpected error loading .env: {exc}")


class _KeyVault:
    def __init__(self):
        # Read keys from environment variables. Keep names stable for config.py
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY")


keyvault = _KeyVault()

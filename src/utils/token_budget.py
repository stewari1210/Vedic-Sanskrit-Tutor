"""Mobile-parity helpers: Gemma-token counting, token-budgeted document selection, prompt-token logging.

All of this is OPT-IN and OFF by default; with the flags unset the web app behaves exactly as before.

  MOBILE_PARITY=1                 retriever: ignore translation-derived proper-noun data (proper_noun_variants.json:
                                  variants, disambiguation, confederation expansion, the x2.0 primary-source boost);
                                  agentic_rag: no llm_expand_query, and token-budgeted synthesis context (below).
  MOBILE_PARITY_TOKEN_BUDGET=2500 prompt budget in Gemma tokens (docs plan section 5; PROVISIONAL until the
                                  on-device fp16/fp32 repro sets it).
  GEMMA_TOKENIZER_PATH            default ios/.gemma-tokenizer/tokenizer.json (google/gemma-4-E4B-it, see plan 5).
  PROMPT_TOKEN_LOG=1              log the Gemma token count of every synthesis prompt; with PARITY_RUN_CONTEXT=<n>
                                  also WARN when it exceeds the context length configured for that run (for the
                                  Ollama/Gemma parity run, where an over-long prompt is silently truncated).

Budget rule (identical on the phone): rank-ordered fill, at most 12 docs, a pinned verse and its hymn context are part
of the fixed prompt so they always go in first and count against the budget; at least 1 retrieved doc is kept.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from src.helper import logger

MAX_DOCS = 12
DEFAULT_BUDGET = 2500   # provisional, see module docstring


def _flag(name: str) -> bool:
    from src.config import get_config_value
    return str(get_config_value(name, "0") or "0").strip().lower() in ("1", "true", "yes", "on")


def mobile_parity_enabled() -> bool:
    return _flag("MOBILE_PARITY")


def prompt_token_log_enabled() -> bool:
    return _flag("PROMPT_TOKEN_LOG")


def token_budget() -> int:
    from src.config import get_config_value
    return int(get_config_value("MOBILE_PARITY_TOKEN_BUDGET", DEFAULT_BUDGET) or DEFAULT_BUDGET)


@lru_cache(maxsize=1)
def _tokenizer():
    from tokenizers import Tokenizer
    from src.config import get_config_value
    default = Path(__file__).resolve().parents[2] / "ios" / ".gemma-tokenizer" / "tokenizer.json"
    path = Path(str(get_config_value("GEMMA_TOKENIZER_PATH", str(default))))
    if not path.exists():       # fail loudly: a silent fallback would make both sides pick different docs
        raise FileNotFoundError(f"Gemma tokenizer not found at {path} (see docs/ios_port_plan.md section 5)")
    return Tokenizer.from_file(str(path))


def count_tokens(text: str) -> int:
    return len(_tokenizer().encode(text).ids)


def select_doc_count(n_available: int, prompt_tokens_for, budget: int | None = None) -> int:
    """Largest k <= min(n_available, MAX_DOCS) with prompt_tokens_for(k) <= budget; at least 1 if any doc exists.

    prompt_tokens_for(k) must return the Gemma token count of the REAL prompt built with the top-k ranked docs
    (so the instruction block, KG block, pinned verse/hymn and question are charged first)."""
    budget = budget or token_budget()
    cap = min(n_available, MAX_DOCS)
    if cap == 0:
        return 0
    best = 0
    for k in range(1, cap + 1):
        if prompt_tokens_for(k) <= budget:
            best = k
        else:
            break
    if best == 0:
        logger.warning(f"[PARITY] even 1 doc exceeds the {budget}-token budget (fixed prompt parts too large); keeping 1")
        best = 1
    return best


def log_prompt_tokens(prompt: str, label: str = "") -> int:
    n = count_tokens(prompt)
    ctx = os.environ.get("PARITY_RUN_CONTEXT")
    over = bool(ctx and ctx.isdigit() and n > int(ctx))
    msg = f"[PROMPT-TOKENS] {label} gemma_tokens={n}" + (f" context={ctx}" if ctx else "") + (" EXCEEDS-CONTEXT" if over else "")
    (logger.warning if over else logger.info)(msg)
    return n

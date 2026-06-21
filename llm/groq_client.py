"""
llm/groq_client.py
------------------
Thin wrapper around the Groq chat completions API.

Responsibilities
----------------
- Load GROQ_API_KEY from the environment (or a .env file via python-dotenv).
- Expose a single ``chat_json()`` function that sends a messages list and
  returns the raw text content of the model's reply.
- Enforce JSON-object mode via ``response_format={"type": "json_object"}``.
- Rely on the Groq SDK's built-in retry (``max_retries=2``, the default)
  for transient network errors and HTTP 429/5xx responses.

This module does NOT parse or validate the returned JSON — callers are
responsible for that (see pipeline/intent.py for the validate+repair loop).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from dotenv import load_dotenv

# Load .env before importing Groq so the key is visible immediately.
load_dotenv()

from groq import Groq  # noqa: E402  (import after load_dotenv)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level client (created lazily so tests that don't need a key can
# still import this module without raising at import time).
# ---------------------------------------------------------------------------

_client: Optional[Groq] = None


def _get_client() -> Groq:
    """Return (or lazily create) the module-level Groq client."""
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. "
                "Add it to your shell environment or to a .env file in the project root."
            )
        # max_retries=2 is the SDK default; stated explicitly for clarity.
        # The SDK retries on 429, 408, 409, and >=500 with exponential backoff.
        _client = Groq(api_key=api_key, max_retries=2)
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat_json(
    messages: list[dict[str, str]],
    *,
    model: str,
    temperature: float = 0.0,
) -> str:
    """
    Call the Groq chat completions endpoint and return the raw text content.

    Parameters
    ----------
    messages : list[dict]
        OpenAI-style messages list, e.g.
        ``[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]``
    model : str
        Groq model identifier (e.g. ``"llama-3.1-8b-instant"``).
    temperature : float
        Sampling temperature. Use 0 for deterministic extraction tasks.

    Returns
    -------
    str
        The raw text content from ``choices[0].message.content``.
        The caller is responsible for JSON-parsing and validation.

    Raises
    ------
    groq.APIConnectionError / groq.RateLimitError / groq.APIStatusError
        Re-raised after the SDK's built-in retries are exhausted.
    """
    client = _get_client()
    t0 = time.perf_counter()

    completion = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    latency_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "Groq call completed | model=%s temperature=%s latency=%.0fms",
        model,
        temperature,
        latency_ms,
    )

    content = completion.choices[0].message.content
    if content is None:
        raise ValueError("Groq returned an empty content field.")
    return content

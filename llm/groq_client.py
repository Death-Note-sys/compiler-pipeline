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
import re
import time
from typing import Any, Optional

from dotenv import load_dotenv

# Load .env before importing Groq so the key is visible immediately.
load_dotenv()

from groq import Groq  # noqa: E402  (import after load_dotenv)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level clients (created lazily so tests that don't need a key can
# still import this module without raising at import time).
# ---------------------------------------------------------------------------

_groq_client: Optional[Groq] = None
_cerebras_client: Optional[Any] = None


def _get_groq_client() -> Groq:
    """Return (or lazily create) the module-level Groq client."""
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. "
                "Add it to your shell environment or to a .env file in the project root."
            )
        # max_retries=2 is the SDK default; stated explicitly for clarity.
        # The SDK retries on 429, 408, 409, and >=500 with exponential backoff.
        _groq_client = Groq(api_key=api_key, max_retries=2)
    return _groq_client


def _get_cerebras_client() -> Any | None:
    """Return (or lazily create) the Cerebras client if key is set, else None."""
    global _cerebras_client
    if _cerebras_client is None:
        cerebras_key = os.environ.get("CEREBRAS_API_KEY")
        if cerebras_key:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("openai package is required for Cerebras support. Run: pip install openai")
            _cerebras_client = OpenAI(
                api_key=cerebras_key,
                base_url="https://api.cerebras.ai/v1",
                max_retries=2
            )
    return _cerebras_client


def _is_daily_limit_error(exc: Exception) -> bool:
    """Return True if the exception indicates a daily token limit (TPD)."""
    msg = str(exc).lower()
    return "tokens per day" in msg or "tpd" in msg


def _is_tpm_error(exc: Exception) -> bool:
    """Return True if the exception indicates a per-minute token limit (TPM)."""
    msg = str(exc).lower()
    return (
        "tokens per minute" in msg
        or "token_quota_exceeded" in msg
        or "too_many_tokens" in msg
    )


def _parse_retry_after(exc: Exception) -> float:
    """Parse 'try again in Xs' or 'try again in Xm Ys' from the error message.

    Returns the number of seconds to wait, or 60.0 as a safe default.
    """
    msg = str(exc)
    # Match patterns like "try again in 30s", "try again in 1m 30s", "try again in 0.5s"
    match = re.search(r"try again in\s+(?:(\d+(?:\.\d+)?)m\s+)?(\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
    if match:
        minutes = float(match.group(1)) if match.group(1) else 0.0
        seconds = float(match.group(2))
        return minutes * 60 + seconds
    return 60.0


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
    Falls back to Cerebras on daily rate limit exhaustion if CEREBRAS_API_KEY is set.

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
    provider = "groq"
    client = _get_groq_client()
    t0 = time.perf_counter()

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        need_cerebras_fallback = False

        if _is_tpm_error(exc):
            # Groq TPM — SDK retries exhausted but cooldown hasn't elapsed.
            # Sleep the exact duration the API tells us, then retry once.
            wait_secs = _parse_retry_after(exc)
            logger.warning(
                "groq_tpm_limit | sleeping %.1fs before retry | model=%s",
                wait_secs,
                model,
            )
            time.sleep(wait_secs)
            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
            except Exception:
                # Groq retry failed — try Cerebras as last resort
                need_cerebras_fallback = True
        elif _is_daily_limit_error(exc):
            need_cerebras_fallback = True
        else:
            raise

        if need_cerebras_fallback:
            cerebras_client = _get_cerebras_client()
            if cerebras_client is None:
                logger.error(
                    "Groq rate limit reached. Please add CEREBRAS_API_KEY to your environment "
                    "for fallback support."
                )
                raise
            logger.warning(
                "provider_fallback: groq->cerebras | model=%s reason=%s",
                model,
                "daily_token_limit" if _is_daily_limit_error(exc) else "tpm_retry_failed",
            )
            provider = "cerebras"
            t0 = time.perf_counter()
            _CEREBRAS_MODEL_MAP = {
                "llama-3.3-70b-versatile": "gpt-oss-120b",
                "llama-3.1-8b-instant": "gpt-oss-120b",
            }
            cerebras_model = _CEREBRAS_MODEL_MAP.get(model, model)
            try:
                completion = cerebras_client.chat.completions.create(
                    model=cerebras_model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
            except Exception as cerebras_exc:
                if _is_tpm_error(cerebras_exc):
                    wait_secs = _parse_retry_after(cerebras_exc)
                    logger.warning(
                        "cerebras_tpm_limit | sleeping %.1fs before retry",
                        wait_secs,
                    )
                    time.sleep(wait_secs)
                    try:
                        completion = cerebras_client.chat.completions.create(
                            model=cerebras_model,
                            messages=messages,
                            temperature=temperature,
                            response_format={"type": "json_object"},
                        )
                    except Exception:
                        raise RuntimeError(
                            "Cerebras TPM limit hit twice — prompt may be too large "
                            "for free-tier token budgets"
                        ) from cerebras_exc
                else:
                    raise

    latency_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "LLM call completed | provider=%s model=%s temperature=%s latency=%.0fms",
        provider,
        model,
        temperature,
        latency_ms,
    )

    content = completion.choices[0].message.content
    if content is None:
        raise ValueError(f"{provider} returned an empty content field.")
    return content
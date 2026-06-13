"""Cohere Rerank 3.5 wrapper.

Used as a second-stage reranker over Ed's keyword-search hits so the posts most
relevant to the user's actual question float to the top. Degrades gracefully: if
no COHERE_API_KEY is set or the API call fails, the threads are returned in Ed's
original order so search never breaks.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .formatting import document_to_markdown

logger = logging.getLogger("edstem_mcp.rerank")

RERANK_MODEL = "rerank-v3.5"

_client: Any = None
_client_initialized = False


def _get_client() -> Any:
    """Lazily build a shared Cohere client; returns None if unavailable."""
    global _client, _client_initialized
    if _client_initialized:
        return _client
    _client_initialized = True

    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        logger.warning("COHERE_API_KEY not set — skipping rerank, using Ed order.")
        _client = None
        return None
    try:
        import cohere

        _client = cohere.ClientV2(api_key=api_key)
    except Exception as exc:  # import or auth construction error
        logger.warning("Could not initialize Cohere client (%s) — skipping rerank.", exc)
        _client = None
    return _client


def _thread_to_document(thread: dict[str, Any]) -> str:
    """Build a compact text representation of a thread for reranking."""
    title = thread.get("title") or ""
    body = document_to_markdown(thread.get("document") or thread.get("content"))
    text = f"{title}\n\n{body}".strip()
    # Keep documents reasonably sized; rerank only needs enough signal.
    return text[:4000] if text else title or "(empty)"


def rerank_threads(
    query: str,
    threads: list[dict[str, Any]],
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Reorder ``threads`` by relevance to ``query`` using Cohere Rerank 3.5.

    Returns a new list (highest relevance first) with ``relevance_score`` attached
    to each thread. Falls back to the input order on any failure.
    """
    if not threads or not query:
        return threads

    client = _get_client()
    if client is None:
        return threads

    n = min(top_n or len(threads), len(threads))
    documents = [_thread_to_document(t) for t in threads]

    try:
        result = client.rerank(
            model=RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=n,
        )
    except Exception as exc:
        logger.warning("Cohere rerank failed (%s) — using Ed order.", exc)
        return threads[:n] if top_n else threads

    reranked: list[dict[str, Any]] = []
    for item in result.results:
        thread = dict(threads[item.index])
        thread["relevance_score"] = item.relevance_score
        reranked.append(thread)
    return reranked

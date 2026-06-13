"""EdStem MCP server.

Exposes tools that let an MCP client (e.g. Claude Code) search your Ed Discussion
posts and read full threads, so it can answer questions grounded in real Ed
content. Ed's keyword hits are reranked with Cohere Rerank 3.5 for relevance.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .ed_client import EdClient, EdError
from .formatting import render_thread, summarize_thread
from .rerank import rerank_threads

# Load .env from the project root (two levels above this package), so the server
# works no matter which directory the MCP client launches it from. Existing env
# vars are not overridden, so `-e` flags on `claude mcp add` still take priority.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()  # also honor a .env in the current working directory, if any

mcp = FastMCP("EdStem")


@lru_cache(maxsize=1)
def _client() -> EdClient:
    """Lazily build a single shared Ed client from the environment."""
    return EdClient(
        token=os.environ.get("ED_API_TOKEN"),
        base_url=os.environ.get("ED_API_BASE", "https://us.edstem.org/api/"),
    )


@mcp.tool()
def list_courses() -> list[dict[str, Any]]:
    """List the Ed courses you have access to.

    Call this first to discover the ``course_id`` values needed by the other
    tools. Returns each course's id, code, name, term, and your role.
    """
    return _client().list_courses()


@mcp.tool()
def search_ed(course_id: int, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search an Ed course for posts relevant to a question.

    Runs Ed's keyword search, then reranks the hits with Cohere Rerank 3.5 so the
    most relevant threads come first. Returns compact thread summaries (id, number,
    title, snippet, url, and relevance_score). Use the returned ``id`` with
    ``get_ed_thread`` to read the full discussion and quote the answer.

    Args:
        course_id: The course to search (from ``list_courses``).
        query: A natural-language question or keywords.
        limit: Max number of results to return (default 20).
    """
    # Fetch a wider candidate set from Ed, then narrow via rerank.
    candidates = _client().search_threads(course_id, query, limit=max(limit * 2, limit))
    ranked = rerank_threads(query, candidates, top_n=limit)
    return [summarize_thread(t) for t in ranked]


@mcp.tool()
def get_ed_thread(thread_id: int) -> str:
    """Read a full Ed thread, including all answers and comments.

    Returns the question and every answer/comment rendered as readable markdown
    (Ed's XML is flattened), with endorsement/resolution flags and a link, so you
    can quote and cite the actual content. Get ``thread_id`` from ``search_ed``.
    """
    thread = _client().get_thread(thread_id)
    return render_thread(thread)


@mcp.tool()
def recent_ed_threads(course_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """List the most recent threads in an Ed course (no keyword filter).

    Useful for "what's been discussed lately?" questions. Returns compact thread
    summaries; use ``get_ed_thread`` to read any of them in full.
    """
    threads = _client().list_threads(course_id, limit=limit, sort="new")
    return [summarize_thread(t) for t in threads]


@mcp.prompt()
def answer_from_ed(question: str) -> str:
    """Guidance for answering a question from Ed Discussion posts."""
    return (
        f"Answer this question using my Ed Discussion posts: {question}\n\n"
        "Steps:\n"
        "1. Call list_courses to find the relevant course_id (ask me if ambiguous).\n"
        "2. Call search_ed with focused keywords from the question.\n"
        "3. Open the most relevant results with get_ed_thread.\n"
        "4. Answer concisely, quoting and citing the specific thread(s) with their "
        "links. Prefer endorsed/staff answers.\n"
        "5. If Ed has no relevant post, say so clearly rather than guessing."
    )


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    try:
        mcp.run()
    except EdError as exc:  # surface config errors clearly on startup paths
        raise SystemExit(f"EdStem MCP error: {exc}")


if __name__ == "__main__":
    main()

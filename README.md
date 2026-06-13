# EdStem MCP

An [MCP](https://modelcontextprotocol.io) server that lets you ask Claude any
question and have it pull the answer from your **Ed Discussion** (edstem.org)
posts. It searches Ed's live API, reranks the hits with **Cohere Rerank 3.5** for
relevance, and hands the most relevant threads to Claude, which reads them and
writes a cited answer.

## How it works

```
you ask Claude  ─▶  list_courses ─▶ search_ed (Ed keyword search ─▶ Cohere rerank)
                                          │
                                          ▼
                                    get_ed_thread (full thread, markdown)
                                          │
                                          ▼
                              Claude synthesizes a cited answer
```

Cohere is used **only** as a second-stage reranker — not for embeddings or answer
generation. If `COHERE_API_KEY` is unset, search still works using Ed's native
ordering.

## Tools

| Tool | What it does |
| --- | --- |
| `list_courses()` | List your Ed courses and their `course_id`s. |
| `search_ed(course_id, query, limit=20)` | Keyword search + Cohere rerank; returns thread summaries with relevance scores. |
| `get_ed_thread(thread_id)` | Full thread (question + answers + comments) as markdown. |
| `recent_ed_threads(course_id, limit=20)` | Most recent threads in a course. |

There's also an `answer_from_ed` prompt that scripts the search→read→cite flow.

## Setup

### 1. Get your keys

- **Ed API token:** https://edstem.org/us/settings/api-tokens
- **Cohere API key (optional but recommended):** https://dashboard.cohere.com/api-keys

### 2. Install

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 3. Configure credentials

Copy `.env.example` to `.env` and fill it in:

```bash
cp .env.example .env
```

```
ED_API_TOKEN=your-ed-token
COHERE_API_KEY=your-cohere-key
# EU users: ED_API_BASE=https://eu.edstem.org/api/
```

## Connect to Claude Code

Pass the credentials inline (no `.env` needed):

```bash
claude mcp add edstem \
  -e ED_API_TOKEN=your-ed-token \
  -e COHERE_API_KEY=your-cohere-key \
  -- uv run edstem-mcp
```

If you installed with pip into a venv, replace `uv run edstem-mcp` with the path
to the installed `edstem-mcp` executable (e.g. `.venv/bin/edstem-mcp`).

Then just ask, e.g. *"What did the staff say about the HW3 deadline on Ed?"*

## Develop / debug

Exercise the tools in the MCP inspector:

```bash
uv run mcp dev src/edstem_mcp/server.py
```

## Notes

- The Ed API is unofficial and in beta; endpoints may change.
- Keep `.env` out of version control (already in `.gitignore`).

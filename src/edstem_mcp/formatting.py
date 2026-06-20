"""Turn Ed's XML thread documents into readable markdown, and render summaries.

Ed post bodies are stored in a custom XML ``<document>`` format. We flatten the
common tags (paragraph, heading, code, list, link, bold/italic) into markdown so
Claude receives clean, quotable text instead of raw XML.
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

ED_WEB_BASE = "https://edstem.org/us/courses"


def document_to_markdown(xml: str | None) -> str:
    """Convert an Ed ``<document>`` XML string to markdown plain text."""
    if not xml:
        return ""
    text = xml.strip()
    if not text:
        return ""
    # If it doesn't look like Ed XML, return as-is (some fields are plain text).
    if "<" not in text:
        return text

    # Parse as XML: Ed's document format is XML, and several Ed tags (link, break,
    # image) collide with HTML void elements, which html.parser would mis-handle.
    soup = BeautifulSoup(text, "xml")
    root = soup.find("document") or soup
    rendered = _render_children(root).strip()
    return rendered or text


def _render_children(node: Tag) -> str:
    """Render every child of ``node`` and concatenate the results."""
    parts: list[str] = []
    for child in node.children:
        parts.append(_render_node(child))
    return "".join(parts)


def _render_node(node: Any) -> str:
    """Render a single Ed XML node (text or tag) as markdown."""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()

    if name == "paragraph":
        return _render_children(node).strip() + "\n\n"
    if name == "heading":
        level = node.get("level", "1")
        try:
            hashes = "#" * max(1, min(6, int(level)))
        except (TypeError, ValueError):
            hashes = "#"
        return f"{hashes} {_render_children(node).strip()}\n\n"
    if name in ("bold", "b", "strong"):
        return f"**{_render_children(node).strip()}**"
    if name in ("italic", "i", "em"):
        return f"*{_render_children(node).strip()}*"
    if name in ("underline", "u"):
        return _render_children(node)
    if name in ("link", "a"):
        href = node.get("href", "")
        label = _render_children(node).strip() or href
        return f"[{label}]({href})" if href else label
    if name == "code":
        # Inline code element.
        return f"`{_render_children(node).strip()}`"
    if name in ("pre", "snippet", "code-block"):
        lang = node.get("language", "") or ""
        body = node.get_text()
        return f"\n```{lang}\n{body.rstrip()}\n```\n\n"
    if name == "list":
        ordered = node.get("style") == "ordered" or node.get("ordered") == "true"
        lines = []
        for i, item in enumerate(node.find_all("list-item", recursive=False), start=1):
            marker = f"{i}." if ordered else "-"
            lines.append(f"{marker} {_render_children(item).strip()}")
        return "\n".join(lines) + "\n\n"
    if name == "list-item":
        return _render_children(node)
    if name == "break":
        return "\n"
    if name in ("image", "img"):
        src = node.get("src", "")
        return f"![image]({src})\n\n" if src else ""
    if name in ("math", "inline-math"):
        return f"${node.get_text().strip()}$"

    # Unknown/wrapper tag: just render its children.
    return _render_children(node)


def _snippet(text: str, length: int = 280) -> str:
    """Collapse whitespace and truncate ``text`` to ``length`` characters."""
    flat = " ".join(text.split())
    return flat if len(flat) <= length else flat[:length].rstrip() + "…"


def thread_url(thread: dict[str, Any]) -> str:
    """Best-effort canonical Ed URL for a thread."""
    course_id = thread.get("course_id")
    number = thread.get("number")
    tid = thread.get("id")
    if course_id and number:
        return f"{ED_WEB_BASE}/{course_id}/discussion/{number}"
    if tid:
        return f"https://edstem.org/us/discussion/{tid}"
    return ""


def summarize_thread(thread: dict[str, Any]) -> dict[str, Any]:
    """Compact dict for search results — easy for the model to scan and cite."""
    body_md = document_to_markdown(thread.get("document") or thread.get("content"))
    summary = {
        "id": thread.get("id"),
        "number": thread.get("number"),
        "title": thread.get("title"),
        "category": thread.get("category"),
        "type": thread.get("type"),
        "is_answered": thread.get("is_answered"),
        "reply_count": thread.get("reply_count") or thread.get("comment_count"),
        "snippet": _snippet(body_md),
        "url": thread_url(thread),
    }
    if "relevance_score" in thread:
        summary["relevance_score"] = thread["relevance_score"]
    return summary


def _render_comment(comment: dict[str, Any], depth: int = 0) -> str:
    """Recursively render a comment (and its replies) as indented markdown."""
    indent = "  " * depth
    author = "anonymous" if comment.get("is_anonymous") else _author_name(comment)
    kind = comment.get("type", "comment")
    flags = []
    if comment.get("is_endorsed"):
        flags.append("endorsed")
    if comment.get("is_resolved"):
        flags.append("resolved")
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    body = document_to_markdown(comment.get("document") or comment.get("content"))
    header = f"{indent}**{kind} by {author}{flag_str}:**"
    body_indented = "\n".join(f"{indent}{line}" for line in body.splitlines())
    out = f"{header}\n{body_indented}\n"
    for reply in comment.get("comments", []) or []:
        out += "\n" + _render_comment(reply, depth + 1)
    return out


def _author_name(obj: dict[str, Any]) -> str:
    """Extract a display name for the author of a thread or comment."""
    user = obj.get("user") or {}
    return user.get("name") or obj.get("user_name") or "unknown"


def render_thread(thread: dict[str, Any]) -> str:
    """Full, readable markdown rendering of a thread with its answers/comments."""
    lines: list[str] = []
    title = thread.get("title", "(untitled)")
    number = thread.get("number")
    lines.append(f"# {title}" + (f" (#{number})" if number else ""))
    meta_bits = [
        f"type: {thread.get('type')}",
        f"category: {thread.get('category')}",
        f"answered: {thread.get('is_answered')}",
    ]
    lines.append("_" + " · ".join(str(b) for b in meta_bits if b) + "_")
    url = thread_url(thread)
    if url:
        lines.append(f"Link: {url}")
    lines.append("")

    author = "anonymous" if thread.get("is_anonymous") else _author_name(thread)
    lines.append(f"**Question by {author}:**")
    lines.append(document_to_markdown(thread.get("document") or thread.get("content")))

    answers = thread.get("answers") or []
    comments = thread.get("comments") or []
    if answers:
        lines.append("\n## Answers")
        for ans in answers:
            lines.append(_render_comment(ans))
    if comments:
        lines.append("\n## Comments")
        for com in comments:
            lines.append(_render_comment(com))

    return "\n".join(lines).strip()

from edstem_mcp.formatting import (
    document_to_markdown,
    render_thread,
    summarize_thread,
    thread_url,
)


def test_document_to_markdown_empty():
    assert document_to_markdown(None) == ""
    assert document_to_markdown("") == ""


def test_document_to_markdown_plain_text_passthrough():
    assert document_to_markdown("just text") == "just text"


def test_document_to_markdown_paragraph_and_heading():
    xml = "<document><heading level='2'>Hi</heading><paragraph>Hello world</paragraph></document>"
    md = document_to_markdown(xml)
    assert "## Hi" in md
    assert "Hello world" in md


def test_document_to_markdown_inline_styles_and_link():
    xml = (
        "<document><paragraph>"
        "<bold>a</bold> <italic>b</italic> "
        "<link href='https://x'>x</link> <code>c</code>"
        "</paragraph></document>"
    )
    md = document_to_markdown(xml)
    assert "**a**" in md
    assert "*b*" in md
    assert "[x](https://x)" in md
    assert "`c`" in md


def test_document_to_markdown_lists():
    xml = (
        "<document><list style='ordered'>"
        "<list-item>one</list-item><list-item>two</list-item>"
        "</list></document>"
    )
    md = document_to_markdown(xml)
    assert "1. one" in md
    assert "2. two" in md


def test_document_to_markdown_code_block():
    xml = "<document><pre language='python'>print(1)</pre></document>"
    md = document_to_markdown(xml)
    assert "```python" in md
    assert "print(1)" in md


def test_thread_url_with_course_and_number():
    url = thread_url({"course_id": 1, "number": 42})
    assert url == "https://edstem.org/us/courses/1/discussion/42"


def test_thread_url_fallback_to_id():
    assert thread_url({"id": 99}) == "https://edstem.org/us/discussion/99"


def test_thread_url_empty():
    assert thread_url({}) == ""


def test_summarize_thread_fields_and_snippet():
    thread = {
        "id": 1,
        "number": 5,
        "title": "T",
        "category": "Q",
        "type": "question",
        "is_answered": True,
        "reply_count": 3,
        "course_id": 7,
        "document": "<document><paragraph>hello there</paragraph></document>",
        "relevance_score": 0.9,
    }
    s = summarize_thread(thread)
    assert s["title"] == "T"
    assert s["url"].endswith("/courses/7/discussion/5")
    assert "hello there" in s["snippet"]
    assert s["relevance_score"] == 0.9


def test_render_thread_includes_question_and_answers():
    thread = {
        "title": "Title",
        "number": 1,
        "type": "question",
        "category": "HW",
        "is_answered": True,
        "course_id": 10,
        "document": "<document><paragraph>Question body</paragraph></document>",
        "user": {"name": "Alice"},
        "answers": [
            {
                "type": "answer",
                "user": {"name": "Bob"},
                "is_endorsed": True,
                "document": "<document><paragraph>An answer</paragraph></document>",
            }
        ],
        "comments": [
            {
                "type": "comment",
                "is_anonymous": True,
                "document": "<document><paragraph>nice</paragraph></document>",
            }
        ],
    }
    out = render_thread(thread)
    assert "# Title (#1)" in out
    assert "Question by Alice" in out
    assert "## Answers" in out
    assert "answer by Bob" in out
    assert "endorsed" in out
    assert "comment by anonymous" in out

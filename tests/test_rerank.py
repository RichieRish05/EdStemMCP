from edstem_mcp import rerank


def _reset_client():
    rerank._client = None
    rerank._client_initialized = False


def test_rerank_no_threads_returns_input():
    assert rerank.rerank_threads("q", []) == []


def test_rerank_no_query_returns_input():
    threads = [{"id": 1}]
    assert rerank.rerank_threads("", threads) is threads


def test_rerank_no_api_key_falls_back(monkeypatch):
    _reset_client()
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    threads = [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]
    assert rerank.rerank_threads("q", threads) is threads


def test_rerank_uses_client_and_attaches_scores(monkeypatch):
    _reset_client()

    class FakeItem:
        def __init__(self, index, score):
            self.index = index
            self.relevance_score = score

    class FakeResult:
        def __init__(self):
            self.results = [FakeItem(1, 0.9), FakeItem(0, 0.1)]

    class FakeClient:
        def rerank(self, **kwargs):
            assert kwargs["model"] == rerank.RERANK_MODEL
            assert kwargs["query"] == "q"
            assert len(kwargs["documents"]) == 2
            return FakeResult()

    monkeypatch.setattr(rerank, "_get_client", lambda: FakeClient())
    threads = [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]
    out = rerank.rerank_threads("q", threads)
    assert [t["id"] for t in out] == [2, 1]
    assert out[0]["relevance_score"] == 0.9
    # input not mutated
    assert "relevance_score" not in threads[0]


def test_rerank_falls_back_on_exception(monkeypatch):
    _reset_client()

    class BoomClient:
        def rerank(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(rerank, "_get_client", lambda: BoomClient())
    threads = [{"id": 1}, {"id": 2}, {"id": 3}]
    assert rerank.rerank_threads("q", threads) == threads
    assert rerank.rerank_threads("q", threads, top_n=2) == threads[:2]

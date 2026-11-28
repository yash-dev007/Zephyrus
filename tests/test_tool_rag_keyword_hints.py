"""Regression for issue #1707 — the agent tool-RAG force-included a whole
domain toolset on any "tell me ..." query, crowding out the relevant tools.

Root cause: `_KEYWORD_HINTS` in src/tool_index.py listed "tell" under a domain
intent, and `get_tools_for_query` force-includes a hint's tools whenever any of
its keywords appears (word-boundary match). "tell" appears in a huge fraction of
requests (the reporter's was "visit <url> and tell me the title"), so unrelated
tools were force-included.

These hints are deterministic string matching — no embeddings — so we can test
`get_tools_for_query` directly with retrieval stubbed out (no ChromaDB needed).
"""

from src.tool_index import ToolIndex, ALWAYS_AVAILABLE


def _index_without_embeddings():
    """A ToolIndex whose retrieval returns nothing, so get_tools_for_query
    exercises only the deterministic base + keyword-hint logic."""
    ti = ToolIndex.__new__(ToolIndex)        # skip __init__ (no ChromaDB/fastembed)
    ti.retrieve = lambda query, k=8: []
    return ti




def test_explicit_web_search_query_gets_web_tools_without_retrieval():
    """Explicit web-search phrasing must surface web tools even if embeddings
    return nothing."""
    ti = _index_without_embeddings()
    tools = ti.get_tools_for_query("use web search and find a recipe for chocolate chip cookies")
    assert "web_search" in tools and "web_fetch" in tools




def test_plain_tell_request_stays_minimal():
    """A bare 'tell me a joke' must not pull in unrelated domain tools."""
    ti = _index_without_embeddings()
    tools = ti.get_tools_for_query("tell me a joke")
    assert "manage_calendar" not in tools
    assert "manage_notes" not in tools
    # Always-available baseline is still there.
    assert set(ALWAYS_AVAILABLE) <= tools

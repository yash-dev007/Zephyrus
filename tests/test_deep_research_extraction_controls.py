import asyncio
import json
import sys
import time
import types

import pytest

from src.deep_research import DeepResearcher


class _ControlledResearcher(DeepResearcher):
    def __init__(self, *args, **kwargs):
        super().__init__(
            llm_endpoint="http://local.test/v1/chat/completions",
            llm_model="local-model",
            *args,
            **kwargs,
        )
        self.active = 0
        self.max_active = 0

    async def _search(self, query):
        return [
            {"url": f"https://example.test/{query}/{i}", "title": f"{query}-{i}"}
            for i in range(4)
        ]

    async def _fetch_and_extract(self, url, question, title):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return {"url": url, "title": title, "summary": "ok"}


@pytest.mark.asyncio
async def test_search_and_extract_respects_extraction_concurrency():
    researcher = _ControlledResearcher(extraction_concurrency=2, max_urls_per_round=4)
    researcher._start_time = time.time()

    findings = await researcher._search_and_extract(["a", "b"], "question")

    # P1-02: the cap is TOTAL unique URLs per round, not per query.
    assert len(findings) == 4
    assert researcher.max_active == 2


@pytest.mark.asyncio
async def test_search_and_extract_tracks_all_urls_selected_for_analysis():
    researcher = _ControlledResearcher(extraction_concurrency=2, max_urls_per_round=2)
    researcher._start_time = time.time()

    findings = await researcher._search_and_extract(["a"], "question")

    assert len(findings) == 2
    assert researcher.analyzed_urls == [
        {"url": "https://example.test/a/0", "title": "a-0"},
        {"url": "https://example.test/a/1", "title": "a-1"},
    ]


@pytest.mark.asyncio
async def test_fetch_and_extract_uses_configured_timeout(monkeypatch):
    captured = {}
    search_mod = types.ModuleType("src.search")

    def fake_fetch_webpage_content(url, timeout):
        return {
            "success": True,
            "content": "useful page content",
            "title": "Page",
            "og_image": "",
        }

    search_mod.fetch_webpage_content = fake_fetch_webpage_content
    monkeypatch.setitem(sys.modules, "src.search", search_mod)

    async def immediate_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)

    researcher = DeepResearcher(
        llm_endpoint="http://local.test/v1/chat/completions",
        llm_model="local-model",
        extraction_timeout=123,
    )

    async def fake_llm(messages, temperature=0.3, max_tokens=4096, timeout=60, **kwargs):
        captured["timeout"] = timeout
        return json.dumps({
            "rational": "relevant",
            "evidence": "evidence",
            "summary": "useful page content",
        })

    researcher._llm = fake_llm

    result = await researcher._fetch_and_extract("https://example.test", "question", "Title")

    assert result["summary"] == "useful page content"
    assert captured["timeout"] == 123


def test_extraction_timeout_allows_long_local_model_runs():
    researcher = DeepResearcher(
        llm_endpoint="http://local.test/v1/chat/completions",
        llm_model="local-model",
        extraction_timeout=1800,
    )

    assert researcher.extraction_timeout == 1800


@pytest.mark.asyncio
async def test_planning_and_query_generation_use_configured_timeouts():
    researcher = DeepResearcher(
        llm_endpoint="http://local.test/v1/chat/completions",
        llm_model="local-model",
        planning_timeout=234,
        query_timeout=345,
    )
    captured = []

    async def fake_llm(messages, temperature=0.3, max_tokens=4096, timeout=60, **kwargs):
        captured.append(timeout)
        if max_tokens == 1024:
            return json.dumps({
                "sub_questions": ["one"],
                "key_topics": ["topic"],
                "success_criteria": "complete",
            })
        return json.dumps(["query one", "query two"])

    researcher._llm = fake_llm

    plan = await researcher._create_plan("question")
    queries = await researcher._generate_queries("question", "", 1)

    assert "Sub-questions: one" in plan
    assert queries == ["query one", "query two"]
    assert captured == [234, 345]


def test_citation_verification_preserves_images():
    from src.research_utils import verify_citations
    report = (
        "Here is an image: ![A diagram](https://cdn.test/chart.png)\n\n"
        "And here is a link: [Good Source](https://allowed.test/page) and "
        "[Bad Source](https://hallucinated.test/page)"
    )
    cleaned, stats = verify_citations(report, {"https://allowed.test/page"})
    assert "![A diagram](https://cdn.test/chart.png)" in cleaned
    assert "[Good Source](https://allowed.test/page)" in cleaned
    assert "[Bad Source] (unverified source removed)" in cleaned
    assert stats["citations_verified"] == 1
    assert stats["citations_stripped"] == 1


def test_delete_owner_data_guard_against_empty():
    from src.research_handler import ResearchHandler
    handler = ResearchHandler()
    assert handler.delete_owner_data("") == 0
    assert handler.delete_owner_data("   ") == 0
    assert handler.delete_owner_data(None) == 0


def test_delete_owner_data_cancels_active_and_purges_files(tmp_path, monkeypatch):
    from src.research_handler import ResearchHandler
    monkeypatch.setattr("src.research_handler.RESEARCH_DATA_DIR", tmp_path)
    handler = ResearchHandler()

    cancelled = []
    handler.cancel_research = lambda sid: cancelled.append(sid)
    handler._active_tasks = {
        "s1": {"owner": "alice", "status": "running"},
        "s2": {"owner": "bob", "status": "running"},
    }

    (tmp_path / "r1.json").write_text(json.dumps({"owner": "alice"}), encoding="utf-8")
    (tmp_path / "r2.json").write_text(json.dumps({"owner": "bob"}), encoding="utf-8")
    (tmp_path / "r1.checkpoint").write_text(json.dumps({"owner": "alice"}), encoding="utf-8")

    removed = handler.delete_owner_data("alice")

    assert removed == 1
    assert cancelled == ["s1"]
    assert "s1" not in handler._active_tasks
    assert "s2" in handler._active_tasks
    assert not (tmp_path / "r1.json").exists()
    assert not (tmp_path / "r1.checkpoint").exists()
    assert (tmp_path / "r2.json").exists()


def test_collect_research_reports_owner_matching(tmp_path, monkeypatch):
    from routes.backup_routes import _collect_research_reports
    monkeypatch.setattr("routes.backup_routes.DEEP_RESEARCH_DIR", str(tmp_path))
    (tmp_path / "r1.json").write_text(json.dumps({"query": "q1", "owner": "alice"}), encoding="utf-8")
    (tmp_path / "r2.json").write_text(json.dumps({"query": "q2", "owner": ""}), encoding="utf-8")
    (tmp_path / "r3.json").write_text(json.dumps({"query": "q3"}), encoding="utf-8")

    alice_reports = _collect_research_reports("alice")
    assert len(alice_reports) == 1
    assert alice_reports[0]["id"] == "r1"

    unowned_reports = _collect_research_reports(None)
    assert len(unowned_reports) == 2
    ids = {r["id"] for r in unowned_reports}
    assert ids == {"r2", "r3"}


@pytest.mark.asyncio
async def test_scheduled_research_error_raises_runtime_error():
    from src.task_scheduler import TaskScheduler

    class _FakeTask:
        id = "t1"
        name = "test task"
        prompt = "test prompt"
        endpoint_url = "http://localhost:11434"
        model = "test-model"
        endpoint_id = "ep1"
        session_id = "sess-123"
        owner = "alice"

    class _FakeHandler:
        def __init__(self):
            self._active_tasks = {
                "sess-123": {"status": "error", "result": "Search backend offline"}
            }

        def start_research(self, **kwargs):
            return {"task": None}

        def get_result(self, session_id):
            return "Search backend offline"

    scheduler = TaskScheduler(session_manager=None, research_handler=_FakeHandler())
    with pytest.raises(RuntimeError, match="Search backend offline"):
        await scheduler._execute_research_task(_FakeTask(), db=None)


@pytest.mark.asyncio
async def test_search_and_extract_skips_recording_when_time_exceeded():
    researcher = _ControlledResearcher(extraction_concurrency=2, max_urls_per_round=2)
    researcher._start_time = time.time() - 1000  # time spent
    findings = await researcher._search_and_extract(["a"], "question")
    assert findings == []
    assert researcher.analyzed_urls == []
    assert researcher.urls_fetched == set()


def test_research_handler_shutdown_cancels_reaper():
    from src.research_handler import ResearchHandler
    handler = ResearchHandler()

    class _MockTask:
        def __init__(self):
            self.cancelled = False
        def done(self):
            return False
        def cancel(self):
            self.cancelled = True

    mock_task = _MockTask()
    handler._reaper_task = mock_task
    handler.shutdown()
    assert mock_task.cancelled is True
    assert handler._reaper_task is None


def test_ephemeral_checkpoint_no_op(tmp_path, monkeypatch):
    from src.research_handler import ResearchHandler
    import src.research_handler as rh
    handler = ResearchHandler()
    handler.RESEARCH_DATA_DIR = tmp_path
    monkeypatch.setattr(rh, "RESEARCH_DATA_DIR", tmp_path)
    entry = {
        "query": "q",
        "owner": "u",
        "status": "running",
        "ephemeral": True,
        "task": None,
        "progress_event": None,
    }
    handler._active_tasks["sess-1"] = entry
    handler._write_checkpoint("sess-1", {"a": 1})
    assert not (tmp_path / "sess-1.checkpoint.json").exists()


def test_cancel_deletes_checkpoint(tmp_path, monkeypatch):
    from src.research_handler import ResearchHandler
    import src.research_handler as rh
    handler = ResearchHandler()
    handler.RESEARCH_DATA_DIR = tmp_path
    monkeypatch.setattr(rh, "RESEARCH_DATA_DIR", tmp_path)
    entry = {
        "query": "q",
        "owner": "u",
        "status": "running",
        "ephemeral": False,
        "task": None,
        "progress_event": None,
    }
    handler._active_tasks["sess-1"] = entry
    handler.cancel_research("sess-1")
    assert not (tmp_path / "sess-1.checkpoint.json").exists()
    assert handler._active_tasks["sess-1"]["status"] == "cancelled"


def test_release_finished_deletes_checkpoint(tmp_path, monkeypatch):
    from src.research_handler import ResearchHandler
    import src.research_handler as rh
    handler = ResearchHandler()
    handler.RESEARCH_DATA_DIR = tmp_path
    monkeypatch.setattr(rh, "RESEARCH_DATA_DIR", tmp_path)
    entry = {
        "query": "q",
        "owner": "u",
        "status": "done",
        "ephemeral": False,
        "task": None,
        "progress_event": None,
        "completed_at": time.time() - 4000,
    }
    handler._active_tasks["sess-1"] = entry
    (tmp_path / "sess-1.json").write_text("{}", encoding="utf-8")
    (tmp_path / "sess-1.checkpoint.json").write_text("{}", encoding="utf-8")
    handler._release_finished_tasks()
    assert "sess-1" not in handler._active_tasks
    assert not (tmp_path / "sess-1.checkpoint.json").exists()


@pytest.mark.asyncio
async def test_final_report_verifies_citations_end_to_end():
    from src.deep_research import DeepResearcher
    researcher = DeepResearcher.__new__(DeepResearcher)
    researcher.category = ""
    researcher.max_report_tokens = 500
    researcher.urls_fetched = ["https://allowed.test/source"]
    researcher.analyzed_urls = []
    researcher.findings = []
    researcher._final_citation_stats = {}
    researcher._emit = lambda **kwargs: None

    async def fake_llm(messages, **kwargs):
        # Return a report >= 400 words so it does not trigger expansion prompt
        content = (
            "Here is the final report with [Valid](https://allowed.test/source) "
            "and [Hallucinated](https://hallucinated.test/fake). "
        )
        return content + ("word " * 450)

    researcher._llm = fake_llm
    out = await researcher._final_report("query", "evolving report")
    assert "[Valid](https://allowed.test/source)" in out
    assert "[Hallucinated] (unverified source removed)" in out
    assert researcher._final_citation_stats["citations_verified"] == 1
    assert researcher._final_citation_stats["citations_stripped"] == 1

def test_purge_expired_ephemeral_deletes_checkpoint(tmp_path, monkeypatch):
    from src.research_handler import ResearchHandler
    import src.research_handler as rh
    handler = ResearchHandler()
    handler.RESEARCH_DATA_DIR = tmp_path
    monkeypatch.setattr(rh, "RESEARCH_DATA_DIR", tmp_path)
    entry = {
        "query": "q",
        "owner": "u",
        "status": "done",
        "ephemeral": True,
        "task": None,
        "progress_event": None,
        "completed_at": time.time() - 1000,
    }
    handler._active_tasks["sess-1"] = entry
    handler._purge_expired_ephemeral()
    assert "sess-1" not in handler._active_tasks
    assert not (tmp_path / "sess-1.checkpoint.json").exists()

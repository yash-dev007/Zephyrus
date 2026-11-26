"""Automatic tool-support detection: probe classification + caching."""

import json

import pytest

import src.model_capabilities as mc


class _Resp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": dict(json or {})})
        return self._responses.pop(0)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_cache", {})
    monkeypatch.setattr(mc, "MODEL_CAPABILITIES_FILE", str(tmp_path / "caps.json"))
    return mc


def _patch_client(monkeypatch, responses):
    client = _FakeClient(responses)
    monkeypatch.setattr(mc.httpx, "AsyncClient", lambda **kw: client)
    return client


@pytest.mark.asyncio
async def test_tool_calls_means_supported_and_is_cached(cache, monkeypatch):
    client = _patch_client(monkeypatch, [
        _Resp(200, {"choices": [{"message": {"tool_calls": [{"id": "1"}]}}]}),
    ])
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is True
    assert mc.cached_support("https://x/v1/chat/completions", "m") is True
    # Second call is served from cache — no new HTTP request.
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is True
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_rejected_tools_payload_means_unsupported(cache, monkeypatch):
    _patch_client(monkeypatch, [
        _Resp(400, {"error": "tools unsupported"}),
        _Resp(400, {"error": "tools unsupported"}),
    ])
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is False
    assert mc.cached_support("https://x/v1/chat/completions", "m") is False


@pytest.mark.asyncio
async def test_unrelated_400_is_undecided(cache, monkeypatch):
    # A 400 that has nothing to do with tools must not cache "text-only".
    _patch_client(monkeypatch, [
        _Resp(400, {"error": {"message": "max_tokens too large"}}),
        _Resp(400, {"error": {"message": "max_tokens too large"}}),
    ])
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is None
    assert mc.cached_support("https://x/v1/chat/completions", "m") is None


@pytest.mark.asyncio
async def test_base_url_is_normalized_to_chat_completions(cache, monkeypatch):
    client = _patch_client(monkeypatch, [
        _Resp(200, {"choices": [{"message": {"tool_calls": [{"id": "1"}]}}]}),
    ])
    await mc.detect_native_tool_support("https://x/v1", "m")
    assert client.calls[0]["url"].endswith("/chat/completions")


def test_transient_read_error_does_not_wipe_cache(tmp_path, monkeypatch):
    # Point at a directory so open() raises IsADirectoryError (an OSError).
    # _load must return {} without caching it, or the next save would wipe
    # every other model's entry.
    monkeypatch.setattr(mc, "_cache", None)
    monkeypatch.setattr(mc, "MODEL_CAPABILITIES_FILE", str(tmp_path))
    assert mc._load() == {}
    assert mc._cache is None


def test_save_merges_with_existing_disk_entries(cache, monkeypatch):
    # Simulate another worker having written an entry this process never saw.
    with open(mc.MODEL_CAPABILITIES_FILE, "w", encoding="utf-8") as f:
        json.dump({"https://other|m": {"supports_tools": True, "checked_at": 1}}, f)
    mc.remember_support("https://x/v1/chat/completions", "m", True)
    with open(mc.MODEL_CAPABILITIES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    assert data["https://other|m"]["supports_tools"] is True
    assert data["https://x/v1/chat/completions|m"]["supports_tools"] is True


@pytest.mark.asyncio
async def test_forced_tool_choice_falls_back_to_auto(cache, monkeypatch):
    client = _patch_client(monkeypatch, [
        _Resp(400, {"error": "tool_choice object unsupported"}),
        _Resp(200, {"choices": [{"message": {"tool_calls": [{"id": "1"}]}}]}),
    ])
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is True
    assert client.calls[0]["json"]["tool_choice"] == {
        "type": "function", "function": {"name": "zephyrus_probe"},
    }
    assert client.calls[1]["json"]["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_ignored_tool_call_means_unsupported(cache, monkeypatch):
    _patch_client(monkeypatch, [_Resp(200, {"choices": [{"message": {"content": "hi"}}]})])
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is False


@pytest.mark.asyncio
async def test_truncated_reasoning_probe_is_undecided(cache, monkeypatch):
    # A reasoning model cut off at the token cap never got to emit the call;
    # that must not be cached as "no tools".
    _patch_client(monkeypatch, [_Resp(200, {
        "choices": [{"message": {"content": "", "reasoning_content": "thinking..."},
                     "finish_reason": "length"}],
    })])
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is None
    assert mc.cached_support("https://x/v1/chat/completions", "m") is None


@pytest.mark.asyncio
async def test_server_error_is_undecided_and_not_cached(cache, monkeypatch):
    _patch_client(monkeypatch, [_Resp(503, {})])
    assert await mc.detect_native_tool_support("https://x/v1/chat/completions", "m") is None
    assert mc.cached_support("https://x/v1/chat/completions", "m") is None


@pytest.mark.asyncio
async def test_cache_persists_to_disk(cache, monkeypatch):
    _patch_client(monkeypatch, [
        _Resp(200, {"choices": [{"message": {"tool_calls": [{"id": "1"}]}}]}),
    ])
    await mc.detect_native_tool_support("https://x/v1/chat/completions", "m")
    with open(mc.MODEL_CAPABILITIES_FILE, encoding="utf-8") as f:
        assert json.load(f)["https://x/v1/chat/completions|m"]["supports_tools"] is True

"""Automatic detection of native tool-calling support per endpoint + model.

Providers differ: some accept an OpenAI `tools` array and return structured
`tool_calls`, others reject it or silently ignore it. Hardcoding model-name
prefixes misses third-party gateways, so this module probes once with a forced
tool call and caches the answer on disk.

The manual `ModelEndpoint.supports_tools` flag always wins; this is only the
fallback for endpoints/models that don't declare it.
"""

import json
import logging
import os
import time
from typing import Optional

import httpx

from src.constants import MODEL_CAPABILITIES_FILE

logger = logging.getLogger(__name__)

# Re-probe weekly so a provider that adds tool support is picked up without
# the user having to clear anything.
_TTL_SECONDS = 7 * 24 * 3600
_PROBE_TIMEOUT = 8.0

_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "zephyrus_probe",
        "description": "Probe tool. Call it with value 1.",
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
    },
}

_cache: Optional[dict] = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(MODEL_CAPABILITIES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        _cache = data if isinstance(data, dict) else {}
    except FileNotFoundError:
        _cache = {}
    except (OSError, json.JSONDecodeError):
        # Transient read failure (permissions, concurrent replace, corrupt
        # write). Do NOT cache an empty dict here: the next remember_support()
        # would then save {} and wipe every other cached model.
        return {}
    return _cache


def _save() -> None:
    try:
        os.makedirs(os.path.dirname(MODEL_CAPABILITIES_FILE), exist_ok=True)
        # Merge with what's on disk first: a transient read failure earlier in
        # this process, or another worker that wrote since, must not be
        # clobbered by our in-memory view.
        disk: dict = {}
        try:
            with open(MODEL_CAPABILITIES_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                disk = loaded
        except (OSError, json.JSONDecodeError):
            pass
        disk.update(_cache or {})
        tmp = MODEL_CAPABILITIES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(disk, f, indent=2)
        os.replace(tmp, MODEL_CAPABILITIES_FILE)
    except OSError as e:
        logger.warning("Could not persist model capability cache: %s", e)


def _key(endpoint_url: str, model: str) -> str:
    return f"{endpoint_url}|{model}"


def cached_support(endpoint_url: str, model: str) -> Optional[bool]:
    """Return the cached answer, or None when absent/expired."""
    entry = _load().get(_key(endpoint_url, model))
    if not isinstance(entry, dict):
        return None
    try:
        checked_at = float(entry.get("checked_at", 0))
    except (TypeError, ValueError):
        return None
    if time.time() - checked_at > _TTL_SECONDS:
        return None
    return entry.get("supports_tools") is True


def remember_support(endpoint_url: str, model: str, supported: bool) -> None:
    global _cache
    cache = _load()
    cache[_key(endpoint_url, model)] = {
        "supports_tools": bool(supported),
        "checked_at": time.time(),
    }
    # If _load() returned a throwaway dict after a transient read error, adopt
    # it so _save() writes this entry instead of an empty cache.
    _cache = cache
    _save()


def _error_mentions_tools(body) -> bool:
    """True when a 4xx body is about tools, not some unrelated bad request."""
    try:
        text = json.dumps(body).lower()
    except (TypeError, ValueError):
        text = str(body).lower()
    return any(k in text for k in ("tool", "function", "tool_choice", "tool choice"))


def _classify(status_code: int, body: dict) -> Optional[bool]:
    """Map a probe response to True/False, or None when undecidable."""
    if status_code in (400, 422):
        # Only a tool-related rejection means "no tools". A 400 for an
        # unrelated reason (bad model id, max_tokens too large, malformed
        # request) must stay undecided or it would cache a wrong False for a
        # week.
        return False if _error_mentions_tools(body) else None
    if status_code != 200:
        return None
    try:
        choice = body["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    if not isinstance(message, dict):
        return None
    if message.get("tool_calls"):
        return True
    # Reasoning models can burn the whole probe budget on reasoning and be cut
    # off before they emit the call. That is undecided, not "no tools" — cache
    # nothing so a later turn retries with the full budget.
    if choice.get("finish_reason") == "length":
        return None
    return False


def _probe_url(endpoint_url: str) -> str:
    """Normalize a base URL to the chat-completions endpoint the probe needs.

    The session's endpoint_url is usually already `.../chat/completions`, but
    some providers store only the base (`.../v1`). Posting the probe to a base
    URL 404s and the model is never detected.
    """
    try:
        from src.llm_core import _stream_target_url
        return _stream_target_url(endpoint_url)
    except Exception:
        return endpoint_url


async def detect_native_tool_support(
    endpoint_url: str,
    model: str,
    headers: Optional[dict] = None,
    *,
    timeout: float = _PROBE_TIMEOUT,
) -> Optional[bool]:
    """Probe an OpenAI-compatible endpoint with a forced tool call.

    Returns True when the model answers with structured `tool_calls`, False
    when it rejects or ignores the tools payload, and None when the probe
    couldn't decide (network error, auth failure, 5xx). None is never cached,
    so the next turn retries.
    """
    cached = cached_support(endpoint_url, model)
    if cached is not None:
        return cached

    url = _probe_url(endpoint_url)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Call the zephyrus_probe tool with value 1."}],
        "tools": [_PROBE_TOOL],
        "tool_choice": {"type": "function", "function": {"name": "zephyrus_probe"}},
        # Reasoning models spend tokens thinking before they emit the call;
        # 32 was enough for plain models but cut reasoners off at "length"
        # with no tool_calls, which misclassified them as text-only.
        "max_tokens": 512,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers or {}, json=payload)
            if resp.status_code == 400:
                # Some gateways reject the forced tool_choice object but still
                # accept `auto`; retry once before calling it unsupported.
                payload["tool_choice"] = "auto"
                resp = await client.post(url, headers=headers or {}, json=payload)
    except Exception as e:
        logger.debug("Tool-support probe failed for %s: %s", model, e)
        return None

    try:
        body = resp.json()
    except ValueError:
        return None
    result = _classify(resp.status_code, body)
    if result is not None:
        remember_support(endpoint_url, model, result)
        logger.info(
            "[tool-capability] %s on %s -> %s",
            model, endpoint_url, "native tools" if result else "text-only",
        )
    return result

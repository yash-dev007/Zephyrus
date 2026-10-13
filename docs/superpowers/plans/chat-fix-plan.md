# Chat Fix Plan — specialized teams

## Domains (no file overlap → parallel safe)
- Team A BACKEND: routes/chat_routes.py, routes/chat_helpers.py, src/chat_handler.py, src/chat_processor.py, src/request_models.py, app.py, src/agent_runs.py
- Team B FRONTEND: static/js/chat.js, static/js/chatRenderer.js, static/js/chatStream.js, static/js/compare/stream.js
- Team C TESTS: tests/test_api_chat_security.py, tests/test_chat_route_tool_policy.py, tests/test_chat_tool_screenshot_xss.py, tests/test_research_chat_stream_owner.py, tests/test_chat_stream_scope.py + new behavior tests

## Team A — Backend privilege, concurrency, perf (Critical+Required)
1. /api/rewrite calls _enforce_chat_privileges + cap input lengths + update by _db_id
2. Non-stream /api/chat returns cleaned reply (_clean_reply), normalize model before enforce, re-enforce fallbacks
3. active_email global → request-scoped (contextvar or explicit ctx param)
4. daily-cap fail-closed on auth error (no return-None bypass); note atomicity TODO if needs migration
5. _verify_session_owner: pass session_manager in chat callers (fix ghost 404) OR document fail-closed consistently
6. Batch per-turn DB trips (one SessionLocal per request where trivially safe), exemptions: only chat_stream/resume SSE in app.py timeout exempt
7. Blocking sync I/O → asyncio.to_thread / gather (chat_processor web/rag/memory, try_fallback requests.get); unify stop/resume/status registry + single save-partial helper
8. Swallowed excepts → warning+context log; fix naive utcnow vs aware; JSON vs form parse by content-type; catch (KeyError, SessionNotFoundError) both paths
- TDD: failing test first per fix. Verify: venv/bin/python -m pytest tests/test_api_chat_security.py tests/test_chat_helpers.py tests/test_chat_route_tool_policy.py -q

## Team B — Frontend SSE, XSS, perf
1. Extract SSE dispatcher table (HANDLERS = {type: fn}) — no behavior change, splits handleChatSubmit branches
2. Unify tool/diff renderer into chatRenderer.js single source; chat.js calls it
3. chatStream.js selector allowlist (getElementById only), toast uses esc() for name+preview
4. Coalesce tool timers to 1 ticker, always clear on abort/detach; throttle scrollHistory (rAF / near-bottom only)
5. Cap chat-history DOM (collapse old agent-thread-content or windowing), remove dead aliases/_body4 vars, keep markdown pipeline as sole innerHTML path
- TDD: add jsdom or pytest streaming_segmenter test where applicable. Verify: existing pytest + manual console-clean check

## Team C — Real behavior security tests (replace tautologies)
1. Replace _build_disabled_tools copy with import/call of real route helper; add route-level disabled_tools/tool_policy/forced_tools matrix via mocked stream_agent_loop
2. Replace substring XSS asserts with payload-execution tests (javascript:, data:text/html, svg screenshot, img onerror tool output)
3. Add cross-user 404 / unauth 401 tests for chat,resume,stop,status,inject,rewrite; incognito/compare strip; allowed_models 403 + daily-cap 429 on BOTH endpoints
4. Research cross-user poll isolation; workspace token-owner test; move test_chat_stream_scope.py out of security set
- Verify: venv/bin/python -m pytest tests/test_api_chat_security.py tests/test_chat_route_tool_policy.py tests/test_chat_tool_screenshot_xss.py tests/test_research_chat_stream_owner.py -q

## Integration
- Teams A/B/C touch disjoint files. Controller merges, runs full focused suite, spot-checks diff.

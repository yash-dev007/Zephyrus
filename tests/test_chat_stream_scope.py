"""Frontend structure guard for the chat submit handler — NOT a security test.

Kept in the suite (rather than the security set) because it pins a JS
scoping arrangement in static/js/chat.js: the ``_renderStream`` /
``_cancelThinkingTimer`` / ``_removeThinkingSpinner`` helpers must be
declared in the outer scope so the ``catch`` block can still reference them
if the ``try`` body throws before assignment. This is crash-safety, not an
auth/owner/XSS boundary — it must not be read as security coverage.
"""

from pathlib import Path


def test_stream_render_helpers_structural_not_security_boundary():
    source = Path("static/js/chat.js").read_text(encoding="utf-8")
    try_start = source.index("    try {\n      // Re-enable auto-scroll")
    catch_start = source.index("    } catch (err) {", try_start)

    outer_scope = source[:try_start]
    try_body = source[try_start:catch_start]

    assert "let _renderStream = () => {};" in outer_scope
    assert "let _cancelThinkingTimer = () => {};" in outer_scope
    assert "let _removeThinkingSpinner = () => {};" in outer_scope

    assert "_renderStream = () => {" in try_body
    assert "_cancelThinkingTimer = () => {" in try_body
    assert "_removeThinkingSpinner = () => {" in try_body
    assert "function _renderStream()" not in try_body


def test_sse_handlers_do_not_use_loop_scoped_isbg():
    """Regression: every SSE delta dropped with `ReferenceError: _isBg is
    not defined`, leaving a blank AI bubble (backend saved fine, so reload
    showed the text). Team B extracted the per-line branches into
    SSE_HANDLERS / _handleSseDelta, but `_isBg` is a const declared inside
    the reader loop — out of scope in the extracted functions. Handlers
    must use the closure-scoped `_isBgNow()` helper instead."""
    import re

    source = Path("static/js/chat.js").read_text(encoding="utf-8")
    table_start = source.index("const SSE_HANDLERS = {")
    loop_start = source.index("while (true) {", table_start)
    handler_region = source[table_start:loop_start]

    bare = re.findall(r"(?<![\w$])_isBg(?![\w$])", handler_region.replace("_isBgNow", ""))
    assert not bare, f"{len(bare)} handler references to loop-scoped _isBg remain"
    assert "_isBgNow()" in handler_region


def test_msg_overflow_menus_use_portal_z():
    """Regression: the chat `···` overflow menu used hardcoded CSS
    z-index:100 while every other body-portaled dropdown uses topPortalZ(),
    so it rendered behind covering UI and its items couldn't be clicked."""
    source = Path("static/js/chatRenderer.js").read_text(encoding="utf-8")
    assert "topPortalZ" in source
    assert source.count("_raiseToPortal(menu);") == 2
    assert source.count("_raiseToPortal(detail);") == 1

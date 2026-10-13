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

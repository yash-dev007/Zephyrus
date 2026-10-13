"""Executed-payload XSS tests for chat image/screenshot sinks and the render pipeline.

Every test below EXECUTES the real production JavaScript under node
(``node --input-type=module``, same approach as
tests/test_emoji_shortcodes_js.py) — no grep-for-identifier asserts form
the core. Payloads go in, neutralized (or safely-rendered) HTML comes out.

What runs:
- ``safeToolScreenshotSrc`` / ``safeDisplayImageSrc`` extracted verbatim
  from static/js/chatRenderer.js (pure: String/regex/URL/window only).
- ``esc`` extracted verbatim from static/js/ui.js (with its ``_ESC_MAP``).
- ``mdToHtml`` — the REAL markdown pipeline from static/js/markdown.js
  (imports stripped, real ``splitTableRow``/emoji helpers imported by
  absolute file URL, truncated before the module-level
  ``document.addEventListener`` side effects). Under node ``document`` is
  undefined, so ``sanitizeAllowedHtml`` takes its documented fail-closed
  branch (escape rather than trust). The browser DOM-sanitizer path
  (``_cleanAllowedHtmlOnce``) cannot run without a browser — noted below.

TDD status: all tests PASS on current code. Team B has since unified the
tool renderer (``buildToolNodeInnerHtml`` — executed below) and capped
data URLs at 12MB (``_DATA_URL_MAX_CHARS`` — pinned below).

Two substring checks are kept as smoke only — they pin the call-site
wiring, not the security property.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_HAS_NODE = shutil.which("node") is not None

needs_node = pytest.mark.skipif(not _HAS_NODE, reason="node binary not on PATH")


def _extract(pattern: str, source: str, label: str) -> str:
    match = re.search(pattern, source, re.S)
    assert match, f"could not extract {label} from production JS (prod refactored?)"
    return match.group(0).replace("export function", "function").replace("export const", "const")


def _esc_source() -> str:
    ui = (_REPO / "static" / "js" / "ui.js").read_text(encoding="utf-8")
    esc_map = _extract(r"const _ESC_MAP = \{[^}]*\};", ui, "_ESC_MAP")
    esc_fn = _extract(r"export function esc\(s\) \{.*?\n\}", ui, "esc")
    return f"{esc_map}\n{esc_fn}"


def _screenshot_helpers_source() -> str:
    renderer = (_REPO / "static" / "js" / "chatRenderer.js").read_text(encoding="utf-8")
    cap = _extract(r"var _DATA_URL_MAX_CHARS = [^;]+;", renderer, "_DATA_URL_MAX_CHARS")
    helper = _extract(r"function _safeDataImageUrl\(raw\) \{.*?\n\}", renderer, "_safeDataImageUrl")
    parts = [
        _extract(r"export function %s\(raw\) \{.*?\n\}" % name, renderer, name)
        for name in ("safeToolScreenshotSrc", "safeDisplayImageSrc")
    ]
    return "\n".join([cap, helper, *parts])


def _tool_node_source() -> str:
    """The canonical tool-thread renderer (pure: string in → string out)."""
    renderer = (_REPO / "static" / "js" / "chatRenderer.js").read_text(encoding="utf-8")
    return _extract(
        r"export function buildToolNodeInnerHtml\(ev\) \{.*?\n\}",
        renderer, "buildToolNodeInnerHtml",
    )


def _markdown_source() -> str:
    """Real mdToHtml, import-stripped and cut before DOM side effects."""
    md = (_REPO / "static" / "js" / "markdown.js").read_text(encoding="utf-8")
    md = re.sub(r"^import .*;$", "", md, flags=re.M)
    md = md.replace("export function", "function").replace("export const", "const")
    md = md.replace("export default markdownModule;", "")
    cut = md.find("document.addEventListener")
    assert cut > 0, "markdown.js no longer has module-level DOM wiring (prod refactored?)"
    return md[:cut]


def _run_js(body: str, cases, use_file: bool = False) -> list:
    table_row = (_REPO / "static" / "js" / "markdown" / "tableRow.js").as_posix()
    emoji = (_REPO / "static" / "js" / "emojiShortcodes.js").as_posix()
    if use_file:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(cases, fh)
        case_path = fh.name
        load_expr = f"JSON.parse(fs.readFileSync({json.dumps(case_path)}, 'utf8'))"
        head = "import fs from 'node:fs';\n"
    else:
        load_expr = "JSON.parse(process.env.ZEPHYRUS_CASES)"
        head = ""
    prog = f"""{head}globalThis.window = {{ location: {{ origin: 'http://localhost:8000' }} }};
import {{ splitTableRow }} from 'file://{table_row}';
import {{ replaceEmojiShortcodes, hasEmojiShortcode }} from 'file://{emoji}';
{body}
const cases = {load_expr};
console.log(JSON.stringify(cases.map((c) => APPLY(c))));
"""
    env = dict(os.environ)
    if not use_file:
        env["ZEPHYRUS_CASES"] = json.dumps(cases)
    proc = subprocess.run(
        ["node", "--input-type=module"], input=prog,
        capture_output=True, text=True, cwd=str(_REPO), timeout=30, env=env,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr[:2000]}"
    return json.loads(proc.stdout.strip())


def _shot(run_fn: str, cases, use_file: bool = False) -> list:
    body = f"""const uiModule = {{ esc }};
{_esc_source()}
{_screenshot_helpers_source()}
const APPLY = (c) => {run_fn}(c);
"""
    return _run_js(body, cases, use_file)


def _toolnode(cases) -> list:
    """Execute the REAL buildToolNodeInnerHtml over tool-event dicts."""
    body = f"""const uiModule = {{ esc }};
{_esc_source()}
{_screenshot_helpers_source()}
{_tool_node_source()}
const APPLY = (c) => buildToolNodeInnerHtml(c);
"""
    return _run_js(body, cases)


def _esc(run_arg_cases) -> list:
    body = f"""{_esc_source()}
const APPLY = (c) => esc(c);
"""
    return _run_js(body, run_arg_cases)


def _md(cases) -> list:
    body = f"""const uiModule = {{ esc }};
{_esc_source()}
{_markdown_source()}
const APPLY = (c) => mdToHtml(c);
"""
    return _run_js(body, cases)


# ── Screenshot / display image src payloads (executed) ───────────────

_VALID_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@needs_node
def test_screenshot_src_neutralizes_active_content_schemes():
    """javascript:/data:text/html/svg payloads must not become <img> srcs."""
    payloads = [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "data:image/svg+xml;base64,PHN2Zz48c2NyaXB0PmFsZXJ0KDEpPC9zY3JpcHQ+PC9zdmc+",
        "data:image/svg+xml,<svg onload=alert(1)>",
        "vbscript:msgbox(1)",
        "",
        "not-a-url-at-all",
        "https://example.com/screenshot.png",
        "http://example.com/screenshot.png",
    ]
    outs = _shot("safeToolScreenshotSrc", payloads)
    assert outs == [""] * len(payloads), f"screenshot sink leaked: {list(zip(payloads, outs))}"


@needs_node
def test_screenshot_src_preserves_raster_data_url():
    """A genuine small PNG data URL still renders (control case)."""
    assert _shot("safeToolScreenshotSrc", [_VALID_PNG]) == [_VALID_PNG]


@needs_node
def test_screenshot_src_rejects_malformed_base64():
    """Non-base64 alphabet in the data portion is rejected."""
    outs = _shot("safeToolScreenshotSrc", [
        "data:image/png;base64,!!!not-base64!!!",
        "data:image/png;base64,",
        "data:image/png,iVBORw0KGgo=",
    ])
    assert outs == ["", "", ""]


@needs_node
def test_display_src_allows_http_only_and_raster_data():
    """Generated-image URLs: http(s) + raster data URLs pass, active schemes do not."""
    payloads = [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "data:image/svg+xml;base64,PHN2Zz48c2NyaXB0PmFsZXJ0KDEpPC9zY3JpcHQ+PC9zdmc+",
    ]
    assert _shot("safeDisplayImageSrc", payloads) == ["", "", ""]
    assert _shot("safeDisplayImageSrc", [_VALID_PNG]) == [_VALID_PNG]
    outs = _shot("safeDisplayImageSrc", ["https://cdn.example.com/i.png", "http://cdn.example.com/i.png"])
    assert outs[0] == "https://cdn.example.com/i.png"
    assert outs[1] == "http://cdn.example.com/i.png"


@needs_node
def test_oversized_screenshot_data_url_neutralized():
    """Data URLs past the 12MB cap must not become an <img> src (PASSES —
    Team B capped via _DATA_URL_MAX_CHARS)."""
    big = "data:image/png;base64," + "A" * (13 * 1024 * 1024)
    assert _shot("safeToolScreenshotSrc", [big], use_file=True) == [""]
    assert _shot("safeDisplayImageSrc", [big], use_file=True) == [""]


# ── esc() primitive (executed) ───────────────────────────────────────

@needs_node
def test_esc_neutralizes_tag_breakout_payloads():
    """The canonical escaper kills tag/attribute breakout at the string level."""
    outs = _esc([
        '<img src=x onerror=alert(1)>',
        '<script>alert(1)</script>',
        '"><svg onload=alert(1)>',
        "a&b\"c'd",
    ])
    assert outs[0] == "&lt;img src=x onerror=alert(1)&gt;"
    assert outs[1] == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert "<" not in outs[2] and ">" not in outs[2]
    assert outs[3] == "a&amp;b&quot;c&#39;d"


# ── Markdown body sink (executed, no-DOM fail-closed path) ───────────

@needs_node
def test_markdown_body_neutralizes_img_onerror_and_script():
    """Tool/model output containing live HTML must render inert (executed)."""
    outs = _md([
        '<img src=x onerror="alert(1)">',
        '<script>alert(1)</script>',
        'Tool result: <svg onload=alert(1)>done',
    ])
    for html in outs:
        assert "<img" not in html, html
        assert "<script" not in html, html
        assert "<svg" not in html, html
    assert "&lt;img" in outs[0]
    assert "&lt;script&gt;" in outs[1]


@needs_node
def test_markdown_body_neutralizes_javascript_link_and_image_targets():
    """[text](javascript:…) / ![alt](javascript:…) must not emit href/src."""
    outs = _md([
        "[click me](javascript:alert(1))",
        "[click me](JaVaScRiPt:alert(1))",
        "![alt](javascript:alert(1))",
        "[evil](data:text/html,<script>alert(1)</script>)",
    ])
    for html in outs:
        assert "javascript:" not in html.lower(), html
        assert "data:text/html" not in html, html
    assert "<a " not in outs[0] and "<a " not in outs[1], outs[:2]
    assert "<img" not in outs[2] and "<img" not in outs[3], outs[2:]


@needs_node
def test_markdown_body_still_renders_legit_content():
    """Control: the pipeline is not just escaping everything (executed).

    NOTE: under node ``document`` is undefined, so ``sanitizeAllowedHtml``
    takes its documented fail-closed branch and escapes even legitimate
    anchors. In the browser the DOM sanitizer preserves them. Both paths
    keep the safe href inert-or-linked, never script-capable.
    """
    outs = _md([
        "hello **world**",
        "[docs](https://example.com/guide)",
        "```js\nconsole.log(1)\n```",
    ])
    assert "<strong>world</strong>" in outs[0]
    assert "https://example.com/guide" in outs[1]
    assert "<a " not in outs[1] or "javascript:" not in outs[1].lower()
    assert "<pre><code" in outs[2] and "console.log(1)" in outs[2]


@needs_node
def test_markdown_fenced_code_does_not_execute_html():
    """HTML inside fenced code blocks stays literal code text (executed)."""
    outs = _md(['```html\n<img src=x onerror=alert(1)>\n```'])
    assert "<img" not in outs[0], outs[0]
    assert "&lt;img" in outs[0]


# ── Canonical tool-node renderer (executed end-to-end) ──────────────

@needs_node
def test_tool_node_output_img_onerror_and_script_are_inert():
    """Model-controlled tool output renders as escaped <pre> text (executed)."""
    outs = _toolnode([
        {"tool": "bash", "command": "cat f", "output": '<img src=x onerror="alert(1)">', "exit_code": 0},
        {"tool": "bash", "command": "cat f", "output": "<script>alert(1)</script>", "exit_code": 0},
    ])
    for html in outs:
        assert "<img" not in html, html
        assert "<script" not in html, html
    assert "&lt;img" in outs[0]
    assert "&lt;script&gt;" in outs[1]


@needs_node
def test_tool_node_screenshot_javascript_dropped_valid_png_kept():
    """A javascript: screenshot adds no <img>; a real PNG data URL does (executed)."""
    outs = _toolnode([
        {"tool": "camera", "screenshot": "javascript:alert(1)", "exit_code": 0},
        {"tool": "camera", "screenshot": _VALID_PNG, "exit_code": 0},
    ])
    assert "<img" not in outs[0], outs[0]
    assert f'<img src="{_VALID_PNG}"' in outs[1], outs[1]


@needs_node
def test_tool_node_tool_name_and_command_are_escaped():
    """Tool label / command sinks escape tag breakout (executed)."""
    outs = _toolnode([
        {"tool": '<script>alert(1)</script>', "command": '"><svg onload=alert(1)>', "exit_code": 1},
    ])
    assert "<script" not in outs[0], outs[0]
    assert "<svg" not in outs[0], outs[0]
    assert "&lt;script&gt;" in outs[0]


# ── Smoke: call-site wiring (substring only) ─────────────────────────

def test_live_tool_sink_wired_through_canonical_renderer_smoke():
    chat = (_REPO / "static" / "js" / "chat.js").read_text(encoding="utf-8")
    assert "currentToolBubble.innerHTML = chatRenderer.buildToolNodeInnerHtml(json)" in chat


def test_canonical_renderer_screens_screenshot_and_escapes_output_smoke():
    renderer = (_REPO / "static" / "js" / "chatRenderer.js").read_text(encoding="utf-8")
    assert "var screenshotSrc = safeToolScreenshotSrc(ev.screenshot);" in renderer
    assert '<pre>${esc(ev.output)}</pre>' in renderer
    assert '<span class="agent-thread-tool">${esc(ev.tool)}</span>' in renderer

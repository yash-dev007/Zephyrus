"""Brutal design-token, UI-consistency and responsiveness audit.

Reads static/style.css + static/index.html + static/js and enforces the
project's own design-system contract:

* every var() resolves (no undefined bare tokens, no dangling fallbacks),
* documented contrast floors actually hold (computed, not eyeballed),
* the black-theme pass (tail override block) uses tokens only,
* sidebar / modals / spinners / toggles / bubbles stay consistent,
* responsive + reduced-motion guarantees hold.

No network, no browser, stdlib only. Runs in <1s.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
SPINNER_JS = (ROOT / "static" / "js" / "spinner.js").read_text(encoding="utf-8")
MODELS_JS = (ROOT / "static" / "js" / "models.js").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------

def _first_root_block(css: str) -> str:
    m = re.search(r":root\s*\{", css)
    start = m.start()
    depth = 0
    for i, ch in enumerate(css[start:]):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return css[start:start + i + 1]
    raise AssertionError("unbalanced :root block")


def _strip_block(css: str, start_marker: str) -> str:
    """Return css with the brace-balanced block starting at start_marker removed."""
    out = []
    i = 0
    while True:
        j = css.find(start_marker, i)
        if j < 0:
            out.append(css[i:])
            break
        out.append(css[i:j])
        k = css.find("{", j)
        depth = 0
        p = k
        while p < len(css):
            if css[p] == "{":
                depth += 1
            elif css[p] == "}":
                depth -= 1
                if depth == 0:
                    break
            p += 1
        i = p + 1
    return "".join(out)


FIRST_ROOT = _first_root_block(CSS)
# NOTE: custom-property extraction runs on comment-stripped CSS — prose
# comments name tokens with trailing colons (e.g. "--fg-strong: ..."), which
# a naive regex would mistake for declarations.
_NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.DOTALL)
ROOT_VARS = dict(re.findall(r"(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);", _first_root_block(_NO_COMMENTS)))
# every custom property declared anywhere in the stylesheet counts as defined
DEFINED = set(re.findall(r"(--[a-zA-Z0-9-]+)\s*:", _NO_COMMENTS))
# element/runtime-scoped properties written by JS or inline styles, not :root
ELEMENT_SCOPED = {
    "--font-family",  # written by settings.js font preference
    "--icon-rail-w", "--sidebar-w",  # synced by sidebar-layout.js
    "--composer-clearance",
    "--bg-effect-intensity", "--bg-effect-color",
    "--model-dot",  # per-message provider dot
    "--ctx-stroke", "--ctx-color",  # context ring, set by chatRenderer.js
    "--ev-color",  # calendar bespoke form, set by calendar.js
    "--cookbook-server-color", "--cookbook-server-accent",  # cookbook.js
    "--cat-hue",  # tasks.js
    "--em",  # markdown.js emoji mask
}
TAIL_MARKER = "── 2. Top-center"
assert TAIL_MARKER in CSS, "theme-pass tail block marker missing"
TAIL = CSS.split(TAIL_MARKER, 1)[1]


def _luminance(hexcode: str) -> float:
    h = hexcode.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(a: str, b: str) -> float:
    x, y = _luminance(a), _luminance(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def _resolve_hex(name: str, seen=None) -> str:
    """Follow var() alias chains to a literal hex; raise if unresolvable."""
    seen = seen or set()
    assert name not in seen, f"alias cycle at {name}"
    seen.add(name)
    raw = ROOT_VARS[name].strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
        return raw
    m = re.fullmatch(r"var\(\s*(--[a-zA-Z0-9-]+)\s*\)", raw)
    assert m, f"{name} does not resolve to a hex (got: {raw!r})"
    return _resolve_hex(m.group(1), seen)


def _iter_var_usages(css: str):
    """Yield (name, fallback_text_or_None) for each var() usage (innermost first)."""
    for m in re.finditer(r"var\(\s*(--[a-zA-Z0-9-]+)\s*(,)?", css):
        name = m.group(1)
        fallback = None
        if m.group(2):
            i = m.end()
            depth = 1
            buf = []
            while i < len(css) and depth:
                ch = css[i]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                if depth:
                    buf.append(ch)
                i += 1
            fallback = "".join(buf)
        yield name, fallback


# --------------------------------------------------------------------------
# 1. token integrity
# --------------------------------------------------------------------------

REQUIRED_TOKENS = {
    # core surfaces + text ramp
    "--bg", "--fg", "--fg-strong", "--fg-muted", "--fg-subtle",
    "--surface-1", "--surface-2", "--surface-3", "--surface-4", "--elevated",
    "--panel", "--panel-2",
    # borders: divider vs control affordance
    "--border", "--border-subtle", "--border-control",
    # accents + status
    "--accent", "--accent-ink", "--danger", "--success", "--warn",
    "--red", "--green",
    # type / spacing / radius / elevation / motion scales
    "--text-xs", "--text-sm", "--text-base", "--text-md", "--text-lg",
    "--text-xl", "--text-2xl", "--text-3xl",
    "--tracking-normal", "--tracking-wide",
    "--space-1", "--space-2", "--space-3", "--space-4", "--space-8",
    "--radius-sm", "--radius-md", "--radius-lg", "--radius-full",
    "--shadow-sm", "--shadow-md", "--shadow-lg",
    "--font-mono", "--font-sans", "--font-ui", "--font-content",
    "--ease-out", "--dur-fast", "--dur-base", "--dur-slow",
}


def test_core_tokens_defined_in_root():
    missing = sorted(t for t in REQUIRED_TOKENS if t not in ROOT_VARS)
    assert not missing, f"tokens missing from :root: {missing}"


def test_no_undefined_bare_vars():
    bad = sorted({
        name for name, fb in _iter_var_usages(CSS)
        if fb is None and name not in DEFINED and name not in ELEMENT_SCOPED
    })
    assert not bad, f"var() with no fallback and no definition: {bad}"


def test_fallback_chains_terminate():
    """Every var() fallback must resolve: nested vars defined/scoped, else literal."""
    offenders = []

    def _fb_ok(fb: str, seen) -> bool:
        inners = re.findall(r"var\(\s*(--[a-zA-Z0-9-]+)", fb)
        if not inners:
            return True  # literal / function fallback
        return all(
            n in DEFINED or n in ELEMENT_SCOPED or n in seen for n in inners
        )

    for name, fb in _iter_var_usages(CSS):
        if fb is None:
            continue
        if name in DEFINED or name in ELEMENT_SCOPED:
            continue
        if not _fb_ok(fb, {name}):
            offenders.append(name)
    assert not offenders, f"dangling fallback chains: {sorted(set(offenders))}"


# (text token, bg token, WCAG floor) — computed, not eyeballed
CONTRAST_FLOORS = [
    ("--fg", "--bg", 12.0),
    ("--fg-strong", "--bg", 15.0),
    ("--fg-muted", "--bg", 7.0),
    ("--fg-subtle", "--elevated", 4.5),  # AA on the lightest surface it lands on
    ("--danger", "--bg", 7.0),
    ("--success", "--bg", 10.0),
    ("--warn", "--bg", 10.0),
    ("--border-control", "--elevated", 3.0),  # 1.4.11 worst case
    ("--accent-ink", "--bg", 12.0),  # live accent path must read on black
]


def test_documented_contrast_floors_hold():
    failures = []
    for text, bg, floor in CONTRAST_FLOORS:
        ratio = _contrast(_resolve_hex(text), _resolve_hex(bg))
        if ratio < floor:
            failures.append(f"{text}/{bg} = {ratio:.2f}:1 < {floor}:1")
    assert not failures, "contrast floors broken:\n" + "\n".join(failures)


def test_hex_regression_ceiling():
    """Hard literals outside :root must not grow (new code uses tokens)."""
    rest = CSS.replace(FIRST_ROOT, "", 1)
    count = len(re.findall(r"#[0-9a-fA-F]{3,8}\b", rest))
    assert count <= 477, f"non-token hex literals grew: {count} > 477"


# --------------------------------------------------------------------------
# 2. theme-pass tail block: zero tolerance
# --------------------------------------------------------------------------

def test_tail_has_no_hex_literals():
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", TAIL)
    assert not hexes, f"hardcoded colors in theme pass: {sorted(set(hexes))}"


def test_tail_font_sizes_come_from_scale():
    bad = []
    for m in re.finditer(r"font-size\s*:\s*([^;]+);", TAIL):
        v = m.group(1).strip()
        if not v.startswith("var(--text-"):
            bad.append(v)
    assert not bad, f"off-scale font sizes in theme pass: {bad}"


def test_tail_borders_are_micro():
    bad = re.findall(r"border(?!-radius)[^:;{]*:\s*([2-9]\d*)px", TAIL)
    assert not bad, f"borders >= 2px in theme pass: {bad}"


def test_tail_important_discipline():
    probe = _strip_block(TAIL, "@media (max-width: 768px)")
    # desktop-guard overrides (e.g. the 40px send key that must not beat the
    # mobile 48px touch rule) are the sanctioned counterpart of mobile rules
    probe = _strip_block(probe, "@media (min-width: 769px)")
    # reduced-motion kills need !important to beat every animation — sanctioned
    probe = _strip_block(probe, "@media (prefers-reduced-motion: reduce)")
    probe = re.sub(
        r"#sidebar-toggle-btn\s*\{[^}]*\}", "", probe, flags=re.DOTALL
    )
    probe = re.sub(r"/\*.*?\*/", "", probe, flags=re.DOTALL)
    assert "!important" not in probe, "!important outside mobile/desktop/toggle rules"


def test_tail_shadows_are_two_layer_tokens_or_none():
    bad = []
    for m in re.finditer(r"box-shadow\s*:\s*([^;]+);", TAIL):
        v = m.group(1).strip()
        if v != "none" and not v.startswith("var(--shadow"):
            bad.append(v)
    assert not bad, f"single-layer shadows in theme pass: {bad}"


# --------------------------------------------------------------------------
# 3. UI consistency
# --------------------------------------------------------------------------

def test_sidebar_command_icons_share_one_size():
    assert (
        "#sidebar-new-chat-btn svg,\n#sidebar-search-btn svg" in TAIL
        and "width: 14px;" in TAIL
        and "height: 14px;" in TAIL
    ), "New Chat / Search icons diverged"


def test_no_inline_nudge_hacks_in_markup():
    assert 'style="position:relative;left:' not in HTML, "inline left-nudge hacks back"


def test_all_modal_variants_are_black():
    for sel in (
        ".modal-content", "#cookbook-modal .modal-content",
        ".memory-modal-content", ".tasks-modal-content",
        ".preset-modal-content", ".doclib-modal-content",
        ".gallery-modal-content", ".cal-modal-content",
    ):
        assert sel in TAIL, f"{sel} missing from black-theme override"
    assert ".admin-card {\n  background: var(--bg);" in TAIL


def test_spinners_are_grey_not_red():
    assert "--fg-muted" in SPINNER_JS
    assert "--red" not in SPINNER_JS
    assert "156, 222" not in SPINNER_JS and "9cdef2" not in SPINNER_JS
    assert "loader-dots" in HTML and "loader-wave" not in HTML
    assert ".ai-spinner {\n  color: var(--fg-muted);" in TAIL


def test_single_sidebar_toggle_is_the_lines_icon():
    assert "#sidebar-toggle-btn {\n  display: none !important;" in TAIL
    assert "body:not(.sidebar-collapsed) .hamburger-btn" not in CSS


def test_ready_hint_text_collapses_behind_composer():
    assert ".welcome-sub.is-ready-hint" in TAIL
    assert "is-ready-hint" in APP_JS and "is-ready-hint" in MODELS_JS


def test_response_bubbles_follow_black_theme():
    assert ".msg-ai {\n  background: var(--bg);" in TAIL
    assert ".msg-user {\n  background: var(--bg);" in TAIL
    assert ".msg-footer {\n  border-top: 1px solid var(--border-subtle);" in TAIL


# --------------------------------------------------------------------------
# 4. responsiveness
# --------------------------------------------------------------------------

def test_viewport_meta_covers_notch_and_keyboard():
    assert "viewport-fit=cover" in HTML
    assert "interactive-widget=resizes-content" in HTML


def test_mobile_breakpoint_exists_and_tagline_wraps():
    assert "@media (max-width: 768px)" in CSS
    assert "white-space: normal;" in TAIL  # mobile tagline must not clip


def _mobile_blob() -> str:
    blobs = []
    for m in re.finditer(r"@media\s*\(max-width:\s*768px\)", CSS):
        k = CSS.find("{", m.end())
        depth, p = 0, k
        while p < len(CSS):
            if CSS[p] == "{":
                depth += 1
            elif CSS[p] == "}":
                depth -= 1
                if depth == 0:
                    break
            p += 1
        blobs.append(CSS[k:p])
    return "\n".join(blobs)


def _rule_min_height(blob: str, selector: str) -> int | None:
    m = re.search(
        re.escape(selector) + r"\s*\{([^}]*)\}", blob, flags=re.DOTALL
    )
    if not m:
        return None
    h = re.search(r"min-height\s*:\s*(\d+)px", m.group(1))
    return int(h.group(1)) if h else None


def test_touch_targets_meet_44px_floor():
    """Message-path + modal + sidebar controls hit the 44px touch floor.

    Scoped to interactive controls on purpose: a blanket scan also flags
    non-interactive containers (headers, badges, chips) and the email/memory
    toolbars, which deliberately run dense 30-38px rows (their compactness is
    the design, with the larger compose control beside them).
    """
    blob = _mobile_blob()
    assert "44px" in blob, "no 44px touch targets in mobile rules"
    for sel in (
        ".mode-toggle-btn",
        ".input-icon-btn",
        ".close-btn",
        "#sidebar-new-chat-btn",
    ):
        h = _rule_min_height(blob, sel)
        # selector may share a grouped rule (".close-btn,\n.modal-close {")
        if h is None:
            m = re.search(
                r"([^{}]*" + re.escape(sel) + r"[^{}]*)\{([^}]*)\}",
                blob,
                flags=re.DOTALL,
            )
            assert m, f"{sel} has no mobile rule at all"
            h2 = re.search(r"min-height\s*:\s*(\d+)px", m.group(2))
            h = int(h2.group(1)) if h2 else None
        assert h is not None and h >= 44, f"{sel} touch height is {h}px (< 44)"


def test_reduced_motion_blanket_covers_all_animation():
    gates = re.findall(
        r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{", CSS
    )
    assert gates, "no prefers-reduced-motion gate at all"
    star_rule = re.search(
        r"\*\s*,\s*\*\s*::before\s*,\s*\*\s*::after"
        r"\s*\{[^{}]*animation-duration\s*:\s*0",
        CSS,
    )
    assert star_rule, "no blanket *-selector animation kill anywhere"
    # ...and it must live inside a prefers-reduced-motion gate, not base CSS
    inside_gate = False
    for m in re.finditer(r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{", CSS):
        k = m.end() - 1
        depth, p = 1, k + 1
        while p < len(CSS) and depth:
            if CSS[p] == "{":
                depth += 1
            elif CSS[p] == "}":
                depth -= 1
            p += 1
        if k < star_rule.start() < p:
            inside_gate = True
    assert inside_gate, "blanket kill exists but is NOT inside a reduced-motion gate"


def test_dynamic_viewport_and_safe_areas():
    assert "100dvh" in CSS
    assert "env(safe-area-inset-" in CSS

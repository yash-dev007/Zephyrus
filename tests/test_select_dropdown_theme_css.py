from pathlib import Path


STYLE_CSS = Path(__file__).resolve().parents[1] / "static" / "style.css"
LOGIN_HTML = Path(__file__).resolve().parents[1] / "static" / "login.html"


def _style_text() -> str:
    return STYLE_CSS.read_text(encoding="utf-8")


def _strip_css_comments(css: str) -> str:
    """Blank out /* ... */ comments, preserving offsets and line breaks.

    Brace matching over raw CSS is unsafe: the :root block carries comments
    containing braces (e.g. an example `.hljs-operator { color: var(--hl-fg) }`),
    and an unbalanced brace inside a comment either truncates the block
    silently or raises a false "unterminated" error.
    """
    out = []
    i = 0
    n = len(css)
    while i < n:
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append("".join(ch if ch == "\n" else " " for ch in css[i:end]))
            i = end
        else:
            out.append(css[i])
            i += 1
    return "".join(out)


def _first_root_block(css: str) -> str:
    """Alias used where the source file differs from style.css."""
    return _root_block(css)


def _root_block(css: str) -> str:
    """Return the first :root rule's body, comments stripped.

    Brace-aware because a bare css.index("}") would stop at the first closing
    brace, which may sit inside a comment.
    """
    stripped = _strip_css_comments(css)
    start = stripped.index(":root {")
    depth = 0
    for i in range(start, len(stripped)):
        if stripped[i] == "{":
            depth += 1
        elif stripped[i] == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : i + 1]
    raise AssertionError("unterminated :root block")


def test_native_select_options_use_theme_tokens():
    css = _style_text()

    assert "--select-option-bg:" in css
    assert "--select-option-fg:" in css
    assert "--select-option-active-bg:" in css
    assert "select option,\n    select optgroup" in css
    assert "background-color: var(--select-option-bg);" in css
    assert "color: var(--select-option-fg);" in css
    assert "select option:checked" in css
    assert "background-color: var(--select-option-active-bg);" in css


# Monochrome ramp, luminance-matched to the values it replaced. Each grey is
# the neutral with the same WCAG relative luminance as the old cool-tinted
# token, so every measured contrast figure in the design specs still holds —
# --fg 13.89:1 on --bg (was 13.93), --fg-subtle 4.61:1 on --elevated (was
# 4.67), --border-control 3.07:1 on --elevated (was 3.10, WCAG 1.4.11 floor
# 3.0). Only the hue moved: the old ramp sat at 204-210 deg / 5-27% sat, which
# read as blue-grey against pure black. Pinned here so it cannot drift back.
FG = "#d2d2d2"
FG_MUTED = "#a3a3a3"
FG_SUBTLE = "#939393"
FG_STRONG = "#f1f1f1"
BORDER = "#373737"
BORDER_CONTROL = "#757575"
ACCENT = "#f1f1f1"


def test_ice_arctic_palette_is_the_only_root_definition():
    css = _style_text()

    root_block = _root_block(css)

    # The palette is baked into :root as the single static definition, so the
    # selects it feeds stay dark with no light override to opt out of.
    assert "--bg: #000000;" in root_block
    assert f"--fg: {FG};" in root_block
    assert "--panel: #141c23;" in root_block
    assert "--select-bg: var(--bg);" in root_block
    assert "--select-fg: var(--fg);" in root_block
    assert ":root.light" not in css
    assert ":root.light select" not in css


def test_neutral_ramp_carries_no_blue_hue():
    """The greys must be neutral, not cool-tinted.

    The ramp this replaced ran 204-210 deg at 5-27% saturation, which on a
    pure-black canvas reads as blue rather than grey — the reason the ref
    monochrome look could not be reached by editing `--accent` alone.
    """
    import colorsys

    css = _style_text()
    root_block = _root_block(css)

    for token in (FG, FG_MUTED, FG_SUBTLE, FG_STRONG, BORDER, BORDER_CONTROL, ACCENT):
        assert token in root_block, f"{token} missing from :root"
        r, g, b = (int(token[i : i + 2], 16) / 255 for i in (1, 3, 5))
        hue, sat, _ = colorsys.rgb_to_hsv(r, g, b)
        assert sat < 0.001, f"{token} is tinted: saturation {sat:.4f}"


def test_status_tokens_never_collide_with_the_accent():
    """Danger must not share a value with the accent.

    The old palette declared `--red: #00ff41`, so every selector named
    danger/error/delete painted green. Pin the four roles apart so that
    regression cannot return.
    """
    css = _style_text()

    root_block = _root_block(css)

    assert f"--accent: {ACCENT};" in root_block
    assert "--danger: #ff5f56;" in root_block
    assert "--success: #3ddc84;" in root_block
    assert "--warn: #fbbf24;" in root_block
    # --red stays as a deprecated alias so ~1,000 call sites keep working.
    assert "--red: var(--danger);" in root_block


def test_login_palette_matches_app_root():
    """static/login.html hand-mirrors the app palette; nothing pinned it.

    Without this, the login page can silently drift to a different scheme
    than the rest of the app.
    """
    css = _style_text()
    login_root = _first_root_block(LOGIN_HTML.read_text(encoding="utf-8"))
    css_root = _root_block(css)

    for token in (
        "--bg: #000000",
        "--panel: #141c23",
        f"--border: {BORDER}",
        f"--fg: {FG}",
        f"--fg-muted: {FG_MUTED}",
        f"--fg-subtle: {FG_SUBTLE}",
        f"--accent: {ACCENT}",
        "--danger: #ff5f56",
    ):
        assert token in css_root, f"{token} missing from style.css :root"
        assert token in login_root, f"{token} missing from login.html :root"

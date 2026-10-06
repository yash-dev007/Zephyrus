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


def test_ice_arctic_palette_is_the_only_root_definition():
    css = _style_text()

    root_block = _root_block(css)

    # Ice / Arctic is baked into :root as the single static definition, so the
    # selects it feeds stay dark with no light override to opt out of.
    assert "--bg: #000000;" in root_block
    assert "--fg: #c9d4dc;" in root_block
    assert "--panel: #141c23;" in root_block
    assert "--select-bg: var(--bg);" in root_block
    assert "--select-fg: var(--fg);" in root_block
    assert ":root.light" not in css
    assert ":root.light select" not in css


def test_status_tokens_never_collide_with_the_accent():
    """Danger must not share a value with the accent.

    The old palette declared `--red: #00ff41`, so every selector named
    danger/error/delete painted green. Pin the four roles apart so that
    regression cannot return.
    """
    css = _style_text()

    root_block = _root_block(css)

    assert "--accent: #7cc4f5;" in root_block
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
        "--border: #2f3841",
        "--fg: #c9d4dc",
        "--fg-muted: #9aa5ad",
        "--fg-subtle: #8b959c",
        "--accent: #7cc4f5",
        "--danger: #ff5f56",
    ):
        assert token in css_root, f"{token} missing from style.css :root"
        assert token in login_root, f"{token} missing from login.html :root"

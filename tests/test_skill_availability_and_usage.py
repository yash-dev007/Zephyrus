"""Regression tests for skill availability gating and usage accounting.

Covers three audited issues in the Agent-mode skill flow:

1. Skill context must not reach the prompt when `manage_skills` is disabled
   (incognito, revoked memory privilege, explicit web-only turns, ...).
2. A matched skill must not be injected when a tool it declares in
   `requires_toolsets` is disabled for the turn.
3. `uses` must count actual consumption (view/invoke), while prompt-time
   surfacing is tracked separately as `matched`.
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# ── module-load stubbing (matches other tests in this repo) ──────────────
for _mod in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext", "sqlalchemy.ext.declarative",
    "sqlalchemy.ext.hybrid", "sqlalchemy.sql", "sqlalchemy.sql.expression",
    "src.database",
    "src.agent_tools",
    "core.models", "core.database",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


from services.memory.skills import SkillsManager  # noqa: E402


SKILL_NAME = "layout-review"
SKILL_DESC = "Review layout and keyboard interactions of the current page."


def _write_skill(
    data_dir: Path,
    *,
    name: str = SKILL_NAME,
    description: str = SKILL_DESC,
    requires: str = "",
    fallback: str = "",
    status: str = "published",
) -> Path:
    skill_dir = data_dir / "skills" / "general" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm = [
        "---",
        f"name: {name}",
        f"description: {description}",
        "when_to_use: when the user wants a layout review",
        "version: 1.0.0",
        "category: general",
        "tags: []",
        f"status: {status}",
        "confidence: 0.9",
        "source: learned",
        "created: 2026-01-01T00:00:00Z",
    ]
    if requires:
        fm.append(f"requires_toolsets: [{requires}]")
    if fallback:
        fm.append(f"fallback_for_toolsets: [{fallback}]")
    fm += [
        "---",
        "",
        "## When to Use",
        "- when the user wants a layout review",
        "",
        "## Procedure",
        "1. review the layout and keyboard interactions",
        "",
    ]
    path = skill_dir / "SKILL.md"
    path.write_text("\n".join(fm), encoding="utf-8")
    return path


def _usage(data_dir: Path, name: str = SKILL_NAME) -> dict:
    usage_file = data_dir / "skills" / "_usage.json"
    if not usage_file.exists():
        return {}
    raw = json.loads(usage_file.read_text(encoding="utf-8"))
    return raw.get(name) or {}


def _patch_prefs(monkeypatch, data_dir: Path) -> None:
    import src.constants as _constants
    monkeypatch.setattr(_constants, "DATA_DIR", str(data_dir), raising=False)

    fake_prefs = types.ModuleType("routes.prefs_routes")
    fake_prefs._load_for_user = lambda user=None: {
        "skills_enabled": True,
        "auto_approve_skills": True,
    }
    monkeypatch.setitem(sys.modules, "routes.prefs_routes", fake_prefs)

    from src import agent_loop
    agent_loop._cached_base_prompt = None
    agent_loop._cached_base_prompt_key = None


QUERY = "please review the layout and keyboard interactions"


# ── 2. Matched skills respect disabled toolsets ──────────────────────────

def test_relevant_skills_hidden_when_required_tool_disabled(tmp_path):
    _write_skill(tmp_path, requires="read_file, grep")
    sm = SkillsManager(str(tmp_path))

    # Unknown active set → don't gate (same contract as index_for).
    names = [s["name"] for s in sm.get_relevant_skills(QUERY, threshold=0.2)]
    assert SKILL_NAME in names

    # Required tool missing → not injected.
    names = [
        s["name"]
        for s in sm.get_relevant_skills(
            QUERY, threshold=0.2, active_toolsets=["grep"],
        )
    ]
    assert SKILL_NAME not in names

    # All required tools active → injected.
    names = [
        s["name"]
        for s in sm.get_relevant_skills(
            QUERY, threshold=0.2, active_toolsets=["grep", "read_file"],
        )
    ]
    assert SKILL_NAME in names


def test_relevant_skills_fallback_hidden_when_substitute_active(tmp_path):
    _write_skill(tmp_path, fallback="web_search")
    sm = SkillsManager(str(tmp_path))

    names = [
        s["name"]
        for s in sm.get_relevant_skills(
            QUERY, threshold=0.2, active_toolsets=["web_search"],
        )
    ]
    assert SKILL_NAME not in names


# ── 3. matched vs uses ───────────────────────────────────────────────────

def test_record_match_does_not_inflate_uses(tmp_path):
    _write_skill(tmp_path)
    sm = SkillsManager(str(tmp_path))

    sm.record_match(SKILL_NAME)
    row = sm.load()[0]
    assert row["matched"] == 1
    assert row["uses"] == 0

    sm.record_use(SKILL_NAME)
    row = sm.load()[0]
    assert row["matched"] == 1
    assert row["uses"] == 1


def test_manage_skills_view_records_use(tmp_path, monkeypatch):
    import asyncio

    _write_skill(tmp_path)
    import src.constants as _constants
    monkeypatch.setattr(_constants, "DATA_DIR", str(tmp_path), raising=False)

    from src.tools.system import do_manage_skills

    result = asyncio.run(
        do_manage_skills(json.dumps({"action": "view", "name": SKILL_NAME}))
    )
    assert "results" in result
    assert _usage(tmp_path)["uses"] == 1
    assert _usage(tmp_path).get("matched", 0) == 0


# ── 1. No skill context when manage_skills is disabled ───────────────────

def _prompt_text(messages) -> str:
    return "\n".join(m.get("content", "") or "" for m in messages)


def test_prompt_omits_skills_when_manage_skills_disabled(tmp_path, monkeypatch):
    _write_skill(tmp_path)
    _patch_prefs(monkeypatch, tmp_path)

    from src.agent_loop import _build_system_prompt

    out, _ = _build_system_prompt(
        messages=[{"role": "user", "content": QUERY}],
        model="test-model",
        active_document=None,
        mcp_mgr=None,
        disabled_tools={"manage_skills"},
    )

    text = _prompt_text(out)
    assert SKILL_NAME not in text
    assert "## Available skills" not in text
    assert "## Relevant skills for this request" not in text
    # Prompt building must not write any usage for a suppressed skill.
    assert _usage(tmp_path) == {}


def test_prompt_match_increments_matched_not_uses(tmp_path, monkeypatch):
    _write_skill(tmp_path)
    _patch_prefs(monkeypatch, tmp_path)

    from src.agent_loop import _build_system_prompt

    out, _ = _build_system_prompt(
        messages=[{"role": "user", "content": QUERY}],
        model="test-model",
        active_document=None,
        mcp_mgr=None,
        disabled_tools=set(),
    )

    text = _prompt_text(out)
    assert SKILL_NAME in text
    assert "## Relevant skills for this request" in text

    usage = _usage(tmp_path)
    assert usage.get("matched") == 1
    assert usage.get("uses", 0) == 0


def test_prompt_omits_matched_skill_when_required_tool_disabled(tmp_path, monkeypatch):
    _write_skill(tmp_path, requires="read_file")
    _patch_prefs(monkeypatch, tmp_path)

    from src.agent_loop import _build_system_prompt

    out, _ = _build_system_prompt(
        messages=[{"role": "user", "content": QUERY}],
        model="test-model",
        active_document=None,
        mcp_mgr=None,
        disabled_tools={"read_file"},
    )

    text = _prompt_text(out)
    assert "## Relevant skills for this request" not in text
    assert _usage(tmp_path).get("matched", 0) == 0

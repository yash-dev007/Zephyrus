"""Persisted settings and tasks from before built-in email removal."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from src import settings
from src.task_scheduler import (
    RETIRED_HOUSEKEEPING_NAMES,
    TaskScheduler,
    is_retired_email_output,
)


def test_saved_email_reminder_channel_migrates_to_browser(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"reminder_channel": "email", "reminder_llm_synthesis": True}))
    monkeypatch.setattr(settings, "SETTINGS_FILE", path)
    monkeypatch.setattr(settings, "_settings_cache", None)

    loaded = settings.load_settings()

    assert loaded["reminder_channel"] == "browser"
    assert loaded["reminder_llm_synthesis"] is True
    assert json.loads(path.read_text())["reminder_channel"] == "browser"


def test_retired_email_task_targets_cannot_complete_without_delivery():
    assert is_retired_email_output("email")
    assert is_retired_email_output("email:self")
    assert is_retired_email_output("me@example.com")
    assert is_retired_email_output("mcp__email__send_email")
    assert not is_retired_email_output("session")
    assert not is_retired_email_output("notification")
    assert not is_retired_email_output("mcp__calendar__create_event")
    scheduler = TaskScheduler.__new__(TaskScheduler)
    for target in ("email:self", "me@example.com", "mcp__email__send_email"):
        task = SimpleNamespace(output_target=target, task_type="llm", action=None)
        with pytest.raises(ValueError, match="Email task output has been removed"):
            asyncio.run(scheduler._deliver_task_result(task, "result", None))


def test_legacy_email_housekeeping_names_are_retired():
    assert RETIRED_HOUSEKEEPING_NAMES["Email Tags"] == "check_email_urgency"
    assert RETIRED_HOUSEKEEPING_NAMES["Tidy Email (Summary)"] == "summarize_emails"

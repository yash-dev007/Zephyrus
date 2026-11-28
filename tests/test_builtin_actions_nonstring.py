"""Regression: builtin_actions heuristics must tolerate non-string input.

_classify_event_heuristic did `(summary or "").lower()`; a truthy non-string
(e.g. a dict) raised AttributeError. It now coerces/guards non-strings.
"""
from src.builtin_actions import _classify_event_heuristic


def test_classify_event_heuristic_non_string():
    out = _classify_event_heuristic(123)
    assert isinstance(out, tuple)

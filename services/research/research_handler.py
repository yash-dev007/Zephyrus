# services/research/research_handler.py
"""Compatibility shim for the single canonical research handler.

This module used to be a full, divergent copy of ``src/research_handler.py``.
Two implementations meant fixes landed in one and not the other (low-quality
source gating, analyzed-URL reporting, atomic saves, owner scoping), and the
services copy was the one actually reachable through ``ResearchService``.

Keep this module thin: re-export the canonical handler so both import paths
share one implementation and one on-disk contract.
"""

from src.research_handler import (  # noqa: F401
    RESEARCH_DATA_DIR,
    ResearchConfigurationError,
    ResearchHandler,
)

__all__ = [
    "RESEARCH_DATA_DIR",
    "ResearchConfigurationError",
    "ResearchHandler",
]

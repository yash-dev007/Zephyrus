"""Backward-compat shim — canonical location is routes/document/document_helpers.py.

This module is replaced in ``sys.modules`` by the canonical module object so
that ``import routes.document_helpers``, ``from routes.document_helpers import X``,
``importlib.import_module("routes.document_helpers")``, and string-targeted
monkeypatches all operate on the same object the application actually uses.
"""

import sys as _sys

from routes.document import document_helpers as _canonical  # noqa: F401

_sys.modules[__name__] = _canonical

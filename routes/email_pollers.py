"""Backward-compat shim — canonical location is routes/email/email_pollers.py.

This module is replaced in ``sys.modules`` by the canonical module object so
that ``import routes.email_pollers``, ``from routes.email_pollers import X``,
``importlib.import_module("routes.email_pollers")``, and string-targeted
monkeypatches all operate on the same object the application actually uses.
"""

import sys as _sys

from routes.email import email_pollers as _canonical  # noqa: F401

_sys.modules[__name__] = _canonical

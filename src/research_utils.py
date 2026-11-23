import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# src/research_utils.py
"""Shared utilities for the deep research system.

Centralizes text cleaning, quality filtering, and other logic
used across deep_research.py, research_handler.py, and visual_report.py.
"""

# ---------------------------------------------------------------------------
# Thinking / reasoning block stripping
# ---------------------------------------------------------------------------

def strip_thinking(text):
    """Strip thinking / reasoning patterns from LLM output.

    Delegates to `src.text_helpers.strip_think` (single source of truth).
    Kept as an alias here so existing `from src.research_utils import strip_thinking`
    callers don't break. Preserves None passthrough — many callers pass an
    `Optional[str]` LLM result and expect None back when the call failed.
    """
    if text is None:
        return None
    from src.text_helpers import strip_think
    return strip_think(text, prose=False, prompt_echo=True)


# ---------------------------------------------------------------------------
# Source quality filtering
# ---------------------------------------------------------------------------

# Markers indicating extracted content is boilerplate, error text, or empty.
# If any marker is found (case-insensitive), the content is filtered out.
LOW_QUALITY_MARKERS = [
    "insufficient to",
    "content is insufficient",
    "no substantive data",
    "does not contain",
    "not relevant to",
    "no relevant information",
    "unable to extract",
    "completely unrelated",
    "boilerplate",
    "footer text",
    # Phrases (not bare "cookie"/"copyright") so we still catch boilerplate
    # like consent banners and footers without discarding legitimate findings
    # that merely discuss cookies or copyright as their subject.
    "cookie consent",
    "cookie banner",
    "cookie notice",
    "copyright notice",
    "copyright footer",
    "all rights reserved",
]


def is_low_quality(summary: str) -> bool:
    """Check if a finding summary indicates useless or irrelevant content."""
    try:
        if not isinstance(summary, str) or not summary:
            return True
        low = summary.lower()
        return any(marker in low for marker in LOW_QUALITY_MARKERS)
    except Exception:
        return False  # fail open


# ---------------------------------------------------------------------------
# Citation grounding
# ---------------------------------------------------------------------------
# Negative lookbehind (?<!\!) prevents corrupting markdown images ![alt](url).
# URLs with balanced parentheses (e.g. Wikipedia links) are supported without
# leaving stray closing parentheses.
_MARKDOWN_LINK_RE = re.compile(
    r"(?<!\!)\[([^\]]*)\]\((https?://(?:[^\s()]+|\([^\s()]*\))+)(?:\s+[\"']([^\"']*)[\"'])?\)"
)
_AUTOLINK_RE = re.compile(r"<(https?://[^\s>]+)>")
_TRACKING_QUERY_PREFIXES = ("utm_", "gclid", "fbclid", "mc_cid", "mc_eid", "ref_")


def normalize_url(url: str) -> str:
    """Canonical form used when comparing cited URLs with fetched URLs.

    Lowercases scheme/host, drops fragments and common tracking parameters,
    removes a trailing slash, and keeps the query string otherwise intact.
    """
    try:
        raw = str(url or "").strip()
        if not raw:
            return ""
        parts = urlsplit(raw)
        scheme = (parts.scheme or "").lower()
        host = (parts.hostname or "").lower()
        if not scheme or not host:
            return raw
        netloc = host
        port = parts.port
        if port:
            if port in (80, 443):
                netloc = host
            else:
                netloc = f"{host}:{port}"
        query_pairs = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            lowered = key.lower()
            if lowered.startswith(_TRACKING_QUERY_PREFIXES):
                continue
            query_pairs.append((key, value))
        path = parts.path or "/"
        if path != "/":
            path = path.rstrip("/")
        return urlunsplit((scheme, netloc, path, urlencode(query_pairs), ""))
    except Exception:
        return str(url or "").strip()


def verify_citations(report_md: str, allowed_urls) -> tuple[str, dict]:
    """Strip markdown links that point outside the set of fetched sources.

    LLMs routinely invent plausible-looking URLs in the final report. Nothing
    downstream validates them, so a hallucinated link can reach the visual
    report and mislead the reader. Every ``[label](http...)`` link whose URL is
    not in ``allowed_urls`` is replaced with ``[label] (unverified source
    removed)`` and counted.

    Also handles bare ``<url>`` forms and optional link titles.

    Returns ``(cleaned_markdown, stats)`` where stats contains
    ``citations_verified``, ``citations_stripped`` and ``citations_total``.
    """
    if not isinstance(report_md, str) or not report_md:
        return report_md or "", {
            "citations_total": 0,
            "citations_verified": 0,
            "citations_stripped": 0,
        }

    allowed = {normalize_url(u) for u in (allowed_urls or []) if u}
    verified = 0
    stripped = 0

    def _replace_link(label: str, url: str, title: str) -> str:
        nonlocal verified, stripped
        if normalize_url(url) in allowed:
            verified += 1
            return f"[{label}]({url}" + (f' "{title}"' if title else "") + ")"
        stripped += 1
        return f"[{label}] (unverified source removed)"

    def _replace_autolink(url: str) -> str:
        nonlocal verified, stripped
        if normalize_url(url) in allowed:
            verified += 1
            return f"<{url}>"
        stripped += 1
        return "<unverified source removed>"

    cleaned = _MARKDOWN_LINK_RE.sub(
        lambda m: _replace_link(m.group(1), m.group(2), m.group(3) or ""),
        report_md,
    )
    cleaned = _AUTOLINK_RE.sub(
        lambda m: _replace_autolink(m.group(1)),
        cleaned,
    )
    return cleaned, {
        "citations_total": verified + stripped,
        "citations_verified": verified,
        "citations_stripped": stripped,
    }

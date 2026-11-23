"""Tests for research_utils.py — thinking block stripping and quality filtering."""

from src.research_utils import strip_thinking, is_low_quality, normalize_url, verify_citations


class TestStripThinking:
    def test_removes_think_tags(self):
        text = "<think>some internal reasoning</think>Final answer."
        assert strip_thinking(text) == "Final answer."

    def test_removes_thinking_tags(self):
        text = "<thinking>some internal reasoning</thinking>Final answer."
        assert strip_thinking(text) == "Final answer."

    def test_removes_nested_tags(self):
        text = "<think>outer <think>inner</think> still outer</think>Result."
        result = strip_thinking(text)
        assert "<think>" not in result
        assert "Result." in result

    def test_handles_orphaned_opening_tag(self):
        text = "<think>unclosed reasoning block\nFinal answer."
        result = strip_thinking(text)
        assert "<think>" not in result

    def test_handles_orphaned_closing_tag(self):
        text = "Some text</think> and more."
        result = strip_thinking(text)
        assert "</think>" not in result
        assert "Some text" in result

    def test_empty_string(self):
        assert strip_thinking("") == ""

    def test_none_input(self):
        assert strip_thinking(None) is None

    def test_no_thinking_tags(self):
        text = "Just a normal response with no tags."
        assert strip_thinking(text) == text

    def test_preserves_content_after_thinking(self):
        text = "<think>planning step</think>\n\n# Report\n\nHere is the report."
        result = strip_thinking(text)
        assert "# Report" in result
        assert "Here is the report." in result

    def test_strips_qwen_thinking_process(self):
        text = "Thinking Process: Let me analyze this carefully.\n\n# Answer\n\nThe answer is 42."
        result = strip_thinking(text)
        assert "Thinking Process" not in result
        assert "The answer is 42." in result


class TestIsLowQuality:
    def test_empty_string(self):
        assert is_low_quality("") is True

    def test_none_input(self):
        assert is_low_quality(None) is True

    def test_normal_summary(self):
        assert is_low_quality("Python 3.12 introduces several new features.") is False

    def test_insufficient_marker(self):
        assert is_low_quality("The content is insufficient to answer.") is True

    def test_no_relevant_info(self):
        assert is_low_quality("No relevant information found in the source.") is True

    def test_boilerplate(self):
        assert is_low_quality("This page contains only boilerplate text.") is True

    def test_unable_to_extract(self):
        assert is_low_quality("Unable to extract meaningful data.") is True

    def test_case_insensitive(self):
        assert is_low_quality("UNABLE TO EXTRACT any data") is True

    def test_copyright_marker(self):
        assert is_low_quality("Just a copyright notice at the bottom.") is True

    # Regression: bare "cookie"/"copyright" used to be substring markers, so
    # legitimate findings that merely discuss them as their subject were
    # discarded. They must now be kept.
    def test_keeps_finding_about_copyright_law(self):
        assert is_low_quality("This article explains the new EU copyright directive reforms.") is False

    def test_keeps_finding_about_cookies(self):
        assert is_low_quality("A technical guide to how tracking cookies and session cookies work.") is False

    def test_keeps_recipe_mentioning_cookies(self):
        assert is_low_quality("Recipe: the best chocolate chip cookies you will ever bake.") is False

    # Boilerplate is still caught via phrases.
    def test_cookie_consent_banner_still_filtered(self):
        assert is_low_quality("The page is just a cookie consent banner.") is True


class TestNormalizeUrl:
    def test_empty_and_none(self):
        assert normalize_url("") == ""
        assert normalize_url(None) == ""

    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTPS://EXAMPLE.COM/Page") == "https://example.com/Page"

    def test_drops_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"
        assert normalize_url("https://example.com/") == "https://example.com/"

    def test_strips_tracking_query_parameters(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social&page=2&gclid=12345&ref_=banner"
        assert normalize_url(url) == "https://example.com/article?page=2"

    def test_preserves_legitimate_query_parameters(self):
        url = "https://example.com/search?q=zephyrus&sort=recent"
        assert normalize_url(url) == "https://example.com/search?q=zephyrus&sort=recent"

    def test_strips_default_port(self):
        assert normalize_url("https://example.com:80/") == "https://example.com/"
        assert normalize_url("https://example.com:443/") == "https://example.com/"
        assert normalize_url("https://Example.com:443/A/") == "https://example.com/A"


class TestVerifyCitations:
    def test_preserves_markdown_images(self):
        report = "![Chart](https://cdn.test/chart.png)\n[Source](https://allowed.test/page)"
        cleaned, stats = verify_citations(report, {"https://allowed.test/page"})
        assert "![Chart](https://cdn.test/chart.png)" in cleaned
        assert "[Source](https://allowed.test/page)" in cleaned
        assert stats["citations_total"] == 1
        assert stats["citations_verified"] == 1
        assert stats["citations_stripped"] == 0

    def test_strips_unverified_sources(self):
        report = "[Allowed](https://allowed.test/page) and [Fake](https://fake.test/page)"
        cleaned, stats = verify_citations(report, ["https://allowed.test/page"])
        assert "[Allowed](https://allowed.test/page)" in cleaned
        assert "[Fake] (unverified source removed)" in cleaned
        assert stats["citations_total"] == 2
        assert stats["citations_verified"] == 1
        assert stats["citations_stripped"] == 1

    def test_empty_and_none_report(self):
        cleaned, stats = verify_citations("", {"https://allowed.test"})
        assert cleaned == ""
        assert stats["citations_total"] == 0

        cleaned_none, stats_none = verify_citations(None, {"https://allowed.test"})
        assert cleaned_none == ""
        assert stats_none["citations_total"] == 0

    def test_parens_and_title(self):
        report = '[Foo](https://en.wikipedia.org/wiki/Foo_(bar)) and [T](https://a.test/x "title")'
        cleaned, stats = verify_citations(report, [])
        assert '[Foo] (unverified source removed)' in cleaned
        assert '[T] (unverified source removed)' in cleaned
        assert stats["citations_total"] == 2
        assert stats["citations_verified"] == 0
        assert stats["citations_stripped"] == 2

    def test_image_links_preserved(self):
        report = "![Alt](https://cdn.test/img.png) [Link](https://bad.test/x)"
        cleaned, stats = verify_citations(report, ["https://cdn.test/img.png"])
        assert "![Alt](https://cdn.test/img.png)" in cleaned
        assert "[Link] (unverified source removed)" in cleaned
        assert stats["citations_total"] == 1
        assert stats["citations_verified"] == 0
        assert stats["citations_stripped"] == 1

    def test_autolinks_verified_and_stripped(self):
        report = "Allowed: <https://allowed.test/page> and fake: <https://fake.test/page>"
        cleaned, stats = verify_citations(report, ["https://allowed.test/page"])
        assert "<https://allowed.test/page>" in cleaned
        assert "<unverified source removed>" in cleaned
        assert stats["citations_total"] == 2
        assert stats["citations_verified"] == 1
        assert stats["citations_stripped"] == 1

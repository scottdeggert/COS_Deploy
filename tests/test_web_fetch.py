"""Standalone unit tests for tools.web_fetch.fetch_url. Not a live fetch."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tools.web_fetch import (
    ALLOWED_DOMAIN_SUFFIX,
    MAX_CONTENT_CHARS,
    fetch_url,
)


def _response(
    text: str,
    status: int = 200,
    content_type: str = "text/plain",
    location: str = "",
    url: str = "https://brightworkrealty.com/",
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.is_redirect = status in (301, 302, 303, 307, 308)
    resp.text = text
    resp.content = text.encode("utf-8")
    resp.headers = {"content-type": content_type}
    if location:
        resp.headers["location"] = location
    resp.url = url
    return resp


class TestFetchUrl(unittest.TestCase):
    def setUp(self) -> None:
        log_patch = patch("tools.web_fetch.log_event")
        self.mock_log = log_patch.start()
        self.addCleanup(log_patch.stop)
        client_patch = patch("tools.web_fetch.httpx.Client")
        self.mock_client_cls = client_patch.start()
        self.addCleanup(client_patch.stop)
        self.mock_client = MagicMock()
        self.mock_client_cls.return_value.__enter__.return_value = self.mock_client

    def test_rejects_off_allowlist_without_request(self) -> None:
        result = fetch_url("https://example.com/page")
        self.assertIn("domain not allowed", result)
        self.assertIn(ALLOWED_DOMAIN_SUFFIX, result)
        self.mock_client.get.assert_not_called()

    def test_rejects_lookalike_domain_without_request(self) -> None:
        result = fetch_url("https://evilbrightworkrealty.com/secret")
        self.assertIn("domain not allowed", result)
        self.mock_client.get.assert_not_called()

    def test_rejects_suffixed_host(self) -> None:
        result = fetch_url("https://brightworkrealty.com.evil.example/x")
        self.assertIn("domain not allowed", result)
        self.mock_client.get.assert_not_called()

    def test_rejects_non_http_scheme(self) -> None:
        result = fetch_url("file:///etc/passwd")
        self.assertIn("only http and https", result)
        self.mock_client.get.assert_not_called()

    def test_allows_apex_and_subdomain(self) -> None:
        self.mock_client.get.return_value = _response("ok")
        apex = fetch_url("https://brightworkrealty.com/notes.txt")
        self.assertEqual(apex, "ok")
        self.mock_client.get.return_value = _response("sub")
        sub = fetch_url("https://www.brightworkrealty.com/notes.txt")
        self.assertEqual(sub, "sub")
        self.assertEqual(self.mock_client.get.call_count, 2)

    def test_returns_raw_json_and_txt(self) -> None:
        self.mock_client.get.return_value = _response(
            '{"a":1}',
            content_type="application/json",
            url="https://brightworkrealty.com/data.json",
        )
        self.assertEqual(
            fetch_url("https://brightworkrealty.com/data.json"),
            '{"a":1}',
        )
        self.mock_client.get.return_value = _response(
            "plain",
            content_type="text/plain",
            url="https://brightworkrealty.com/notes.txt",
        )
        self.assertEqual(
            fetch_url("https://brightworkrealty.com/notes.txt"),
            "plain",
        )

    def test_strips_html_tags(self) -> None:
        html = (
            "<html><head><style>p{color:red}</style></head>"
            "<body><h1>Hello</h1><script>alert(1)</script>"
            "<p>World</p></body></html>"
        )
        self.mock_client.get.return_value = _response(
            html,
            content_type="text/html",
            url="https://brightworkrealty.com/about.html",
        )
        result = fetch_url("https://brightworkrealty.com/about.html")
        self.assertEqual(result, "Hello World")
        self.assertNotIn("<", result)
        self.assertNotIn("alert", result)
        self.assertNotIn("color:red", result)

    def test_strips_html_when_content_type_is_html(self) -> None:
        self.mock_client.get.return_value = _response(
            "<p>Listed home</p>",
            content_type="text/html; charset=utf-8",
            url="https://brightworkrealty.com/listings",
        )
        result = fetch_url("https://brightworkrealty.com/listings")
        self.assertEqual(result, "Listed home")

    def test_truncates_over_cap(self) -> None:
        body = "A" * (MAX_CONTENT_CHARS + 25)
        self.mock_client.get.return_value = _response(
            body,
            content_type="text/plain",
            url="https://brightworkrealty.com/long.txt",
        )
        result = fetch_url("https://brightworkrealty.com/long.txt")
        self.assertTrue(result.startswith("A" * MAX_CONTENT_CHARS))
        self.assertIn("truncated", result)
        self.assertIn(str(MAX_CONTENT_CHARS), result)
        self.assertLess(len(result), len(body) + 80)

    def test_http_error_returns_error_string(self) -> None:
        self.mock_client.get.return_value = _response(
            "missing",
            status=404,
            content_type="text/plain",
        )
        result = fetch_url("https://brightworkrealty.com/missing.txt")
        self.assertIn("HTTP 404", result)

    def test_timeout_returns_error_string(self) -> None:
        import httpx

        self.mock_client.get.side_effect = httpx.TimeoutException("timed out")
        result = fetch_url("https://brightworkrealty.com/slow.txt")
        self.assertIn("timed out", result)
        self.mock_client.get.assert_called_once()

    def test_blocks_redirect_off_allowlist(self) -> None:
        self.mock_client.get.return_value = _response(
            "",
            status=302,
            location="https://evil.example/steal",
            url="https://brightworkrealty.com/out",
        )
        result = fetch_url("https://brightworkrealty.com/out")
        self.assertIn("domain not allowed", result)
        self.assertEqual(self.mock_client.get.call_count, 1)

    def test_logs_start_and_success_with_byte_count(self) -> None:
        self.mock_client.get.return_value = _response("abcd")
        fetch_url("https://brightworkrealty.com/notes.txt")
        statuses = [call.args[2] for call in self.mock_log.call_args_list]
        self.assertEqual(statuses, ["start", "success"])
        success_kwargs = self.mock_log.call_args_list[-1].kwargs
        self.assertIn("bytes=4", success_kwargs["detail"])
        self.assertIn("brightworkrealty.com", success_kwargs["detail"])

    def test_logs_failure_for_rejected_domain(self) -> None:
        fetch_url("https://example.com/")
        statuses = [call.args[2] for call in self.mock_log.call_args_list]
        self.assertEqual(statuses, ["start", "failure"])
        failure_kwargs = self.mock_log.call_args_list[-1].kwargs
        self.assertIn("bytes=0", failure_kwargs["detail"])


if __name__ == "__main__":
    unittest.main()

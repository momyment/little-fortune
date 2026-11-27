#!/usr/bin/env python3
"""Unit tests for translate retry, cache, batching, and fallback.

No live network: urllib.request.urlopen is mocked.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_daily as s  # noqa: E402


def _google_body(text: str) -> bytes:
    return json.dumps([[[text, "src", None, None]]], ensure_ascii=False).encode()


def _mymemory_body(text: str) -> bytes:
    return json.dumps({"responseData": {"translatedText": text}}).encode()


class FakeResponse:
    def __init__(self, body: bytes, headers=None):
        self._body = body
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after

    class H(dict):
        def get(self, key, default=None):
            for k, v in self.items():
                if k.lower() == key.lower():
                    return v
            return default

    return urllib.error.HTTPError(
        "https://translate.googleapis.com/translate_a/single",
        code,
        "Too Many Requests" if code == 429 else "Error",
        H(headers),
        io.BytesIO(b""),
    )


class TranslateTests(unittest.TestCase):
    def setUp(self):
        self._attempts = s.TRANSLATE_MAX_ATTEMPTS
        self._interval = s.TRANSLATE_MIN_INTERVAL
        self._sleep = s.TRANSLATE_MAX_SLEEP
        s.TRANSLATE_MAX_ATTEMPTS = 4
        s.TRANSLATE_MIN_INTERVAL = 0
        s.TRANSLATE_MAX_SLEEP = 30
        s._google_rate_limited = False
        s._last_translate_http = 0.0
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = s.TranslateCache(str(Path(self.tmp.name) / "translate-cache.json"))

    def tearDown(self):
        s.TRANSLATE_MAX_ATTEMPTS = self._attempts
        s.TRANSLATE_MIN_INTERVAL = self._interval
        s.TRANSLATE_MAX_SLEEP = self._sleep
        s._google_rate_limited = False
        self.tmp.cleanup()

    def test_cache_hit_skips_http(self):
        self.cache.put("白菜", "ja", "ko", "배추")
        with mock.patch("urllib.request.urlopen") as urlopen:
            out = s.google_translate("白菜", "ja", "ko", self.cache)
        self.assertEqual(out, "배추")
        urlopen.assert_not_called()

    def test_successful_google_is_cached(self):
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(_google_body("배추"))):
            out = s.google_translate("白菜", "ja", "ko", self.cache)
        self.assertEqual(out, "배추")
        self.assertEqual(self.cache.get("白菜", "ja", "ko"), "배추")
        # Second call must not hit the network.
        with mock.patch("urllib.request.urlopen") as urlopen:
            self.assertEqual(s.google_translate("白菜", "ja", "ko", self.cache), "배추")
            urlopen.assert_not_called()

    def test_retry_after_is_honored(self):
        calls = {"n": 0}

        def urlopen(req, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise http_error(429, retry_after="2")
            return FakeResponse(_google_body("배추"))

        sleeps: list[float] = []
        with mock.patch("urllib.request.urlopen", side_effect=urlopen), mock.patch(
            "time.sleep", side_effect=lambda t: sleeps.append(t)
        ):
            out = s.google_translate("白菜", "ja", "ko", self.cache)
        self.assertEqual(out, "배추")
        self.assertEqual(calls["n"], 2)
        self.assertEqual(len(sleeps), 1)
        # Retry-After 2s + up to 30% jitter, and not the plain 2**attempt (=2) only
        # (jitter may still land near 2). Lower bound is 2.
        self.assertGreaterEqual(sleeps[0], 2.0)
        self.assertLessEqual(sleeps[0], 2.0 * 1.3 + 0.01)

    def test_exponential_backoff_without_retry_after(self):
        def urlopen(req, timeout=None):
            raise http_error(429)

        sleeps: list[float] = []
        with mock.patch("urllib.request.urlopen", side_effect=urlopen), mock.patch(
            "time.sleep", side_effect=lambda t: sleeps.append(t)
        ), mock.patch.object(s, "mymemory_translate", side_effect=RuntimeError("nope")):
            with self.assertRaises(RuntimeError) as ctx:
                s.google_translate("白菜", "ja", "ko", self.cache)
        self.assertIn("白菜", str(ctx.exception))
        # 4 attempts => 3 sleeps, bases 2, 4, 8 (plus jitter up to 30%)
        self.assertEqual(len(sleeps), 3)
        self.assertGreaterEqual(sleeps[0], 2.0)
        self.assertLessEqual(sleeps[0], 2.6)
        self.assertGreaterEqual(sleeps[1], 4.0)
        self.assertLessEqual(sleeps[1], 5.2)
        self.assertGreaterEqual(sleeps[2], 8.0)
        self.assertLessEqual(sleeps[2], 10.4)
        self.assertTrue(s._google_rate_limited)

    def test_mymemory_fallback_after_google_429(self):
        def urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "mymemory" in url:
                return FakeResponse(_mymemory_body("배추"))
            raise http_error(429)

        with mock.patch("urllib.request.urlopen", side_effect=urlopen), mock.patch(
            "time.sleep"
        ):
            out = s.google_translate("白菜", "ja", "ko", self.cache)
        self.assertEqual(out, "배추")
        self.assertEqual(self.cache.get("白菜", "ja", "ko"), "배추")
        self.assertTrue(s._google_rate_limited)

        # Next item in the same run should skip Google entirely.
        def urlopen2(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "mymemory" in url:
                return FakeResponse(_mymemory_body("당근"))
            raise AssertionError("Google should have been skipped")

        with mock.patch("urllib.request.urlopen", side_effect=urlopen2):
            out2 = s.google_translate("人参", "ja", "ko", self.cache)
        self.assertEqual(out2, "당근")

    def test_batch_translates_unique_texts(self):
        def urlopen(req, timeout=None):
            return FakeResponse(_google_body("배추\n당근"))

        with mock.patch("urllib.request.urlopen", side_effect=urlopen) as mocked:
            out = s.google_translate_many(["白菜", "人参", "白菜"], "ja", "ko", self.cache)
        self.assertEqual(out, ["배추", "당근", "배추"])
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(self.cache.get("白菜", "ja", "ko"), "배추")
        self.assertEqual(self.cache.get("人参", "ja", "ko"), "당근")

    def test_batch_mismatch_falls_back_one_by_one(self):
        calls = {"n": 0}

        def urlopen(req, timeout=None):
            calls["n"] += 1
            # First call is the batch (two lines expected); return one line only.
            if calls["n"] == 1:
                return FakeResponse(_google_body("배추"))
            q = req.full_url
            if "q=%E7%99%BD%E8%8F%9C" in q or "白菜" in q:
                return FakeResponse(_google_body("배추"))
            return FakeResponse(_google_body("당근"))

        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            out = s.google_translate_many(["白菜", "人参"], "ja", "ko", self.cache)
        self.assertEqual(out, ["배추", "당근"])
        self.assertGreaterEqual(calls["n"], 3)  # 1 batch + 2 singles

    def test_glossary_wins_over_google(self):
        glossary = {"白菜": "백김치"}  # site wording, not machine
        entries = [
            {
                "rank": 1,
                "sign": "게자리",
                "ja_summary": "良い一日",
                "ja_lucky": "白菜",
            }
        ]
        # Only the summary should hit the network (direct ja->ko).
        def urlopen(req, timeout=None):
            q = req.full_url
            if "sl=ja" in q and "tl=ko" in q:
                return FakeResponse(_google_body("좋은 하루"))
            raise AssertionError(f"unexpected request {q}")

        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            out = s.translate_entries(entries, glossary, self.cache)
        self.assertEqual(out[0]["lucky"], "백김치")
        self.assertEqual(out[0]["summary"], "좋은 하루")
        self.assertEqual(out[0]["ja_lucky"], "白菜")

    def test_translate_entries_reuses_cached_lucky(self):
        self.cache.put("白菜", "ja", "ko", "배추")
        self.cache.put("良い一日", "ja", "ko", "좋은 하루")
        entries = [
            {"rank": 1, "sign": "게자리", "ja_summary": "良い一日", "ja_lucky": "白菜"},
            {"rank": 2, "sign": "사자자리", "ja_summary": "良い一日", "ja_lucky": "白菜"},
        ]
        with mock.patch("urllib.request.urlopen") as urlopen:
            out = s.translate_entries(entries, {}, self.cache)
        urlopen.assert_not_called()
        self.assertEqual(out[0]["lucky"], "배추")
        self.assertEqual(out[1]["summary"], "좋은 하루")


    def test_translate_summary_is_direct_ja_ko(self):
        def urlopen(req, timeout=None):
            q = req.full_url
            if "sl=ja" in q and "tl=ko" in q:
                return FakeResponse(_google_body("좋은 하루"))
            raise AssertionError(f"unexpected request {q}")

        with mock.patch("urllib.request.urlopen", side_effect=urlopen) as mocked:
            out = s.translate_summary("良い一日", self.cache)
        self.assertEqual(out, "좋은 하루")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(self.cache.get("良い一日", "ja", "ko"), "좋은 하루")

    def test_retry_after_http_date(self):
        # A date 10 seconds in the future should produce a ~10s sleep (+jitter).
        when = s.dt.datetime.now(s.dt.timezone.utc) + s.dt.timedelta(seconds=10)
        raw = when.strftime("%a, %d %b %Y %H:%M:%S GMT")
        exc = http_error(429, retry_after=raw)
        with mock.patch("random.uniform", return_value=0):
            sleep_for = s._retry_after_seconds(exc, attempt=1)
        self.assertGreaterEqual(sleep_for, 8.0)
        self.assertLessEqual(sleep_for, 11.0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for scripts/write_api.py (no network)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import write_api as api  # noqa: E402


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class WriteApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        dump(
            self.root / "horoscope-editions.json",
            [
                {
                    "date": "2026-11-26",
                    "entries": [
                        {
                            "rank": 1,
                            "sign": "양자리",
                            "summary": "좋은 하루",
                            "lucky": "오르골",
                            "ja_summary": "よい一日",
                            "ja_lucky": "オルゴール",
                        }
                    ],
                },
                {
                    "date": "2026-11-24",
                    "entries": [
                        {"rank": 1, "sign": "게자리", "summary": "어제", "lucky": "사과"}
                    ],
                },
            ],
        )
        dump(
            self.root / "fortune-index.json",
            {"2026-11-25": "AAAA", "2026-11-26": "DgKzUPcD2yg"},
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_horoscope_editions_envelope(self):
        api.write_api(str(self.root), updated_at="2026-11-26T00:00:00Z")
        body = json.loads((self.root / "api/v1/horoscope/editions.json").read_text())
        self.assertTrue(body["ok"])
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["type"], "horoscope-editions")
        self.assertEqual(body["updated_at"], "2026-11-26T00:00:00Z")
        self.assertEqual(body["dates"], ["2026-11-24", "2026-11-26"])
        self.assertEqual(len(body["editions"]), 2)
        self.assertEqual(body["editions"][1]["date"], "2026-11-26")
        self.assertEqual(body["editions"][1]["entries"][0]["lucky"], "오르골")

    def test_per_day_file(self):
        api.write_api(str(self.root), updated_at="2026-11-26T00:00:00Z")
        day = json.loads((self.root / "api/v1/horoscope/2026-11-26.json").read_text())
        self.assertEqual(day["type"], "horoscope-edition")
        self.assertEqual(day["date"], "2026-11-26")
        self.assertEqual(day["edition"]["entries"][0]["sign"], "양자리")
        self.assertTrue((self.root / "api/v1/horoscope/2026-11-24.json").exists())

    def test_fortunes_index(self):
        api.write_api(str(self.root), updated_at="2026-11-26T00:00:00Z")
        body = json.loads((self.root / "api/v1/fortunes/index.json").read_text())
        self.assertEqual(body["type"], "fortune-index")
        self.assertEqual(body["dates"], ["2026-11-25", "2026-11-26"])
        self.assertEqual(body["fortunes"]["2026-11-26"]["shortcode"], "DgKzUPcD2yg")
        self.assertEqual(
            body["fortunes"]["2026-11-26"]["image"],
            "/little-fortune/fortunes/2026-11-26.jpg",
        )
        self.assertEqual(
            body["fortunes"]["2026-11-26"]["source"],
            "https://www.instagram.com/p/DgKzUPcD2yg/",
        )

    def test_backfill_from_legacy_files(self):
        # Running twice is safe; missing api/ is created from the legacy files.
        api.write_api(str(self.root), updated_at="2026-11-26T01:00:00Z")
        api.write_api(str(self.root), updated_at="2026-11-26T02:00:00Z")
        body = json.loads((self.root / "api/v1/horoscope/editions.json").read_text())
        self.assertEqual(body["updated_at"], "2026-11-26T02:00:00Z")
        self.assertEqual(body["dates"], ["2026-11-24", "2026-11-26"])

    def test_accepts_already_wrapped_editions(self):
        dump(
            self.root / "horoscope-editions.json",
            {
                "ok": True,
                "editions": [
                    {"date": "2026-11-26", "entries": [{"rank": 1, "sign": "양자리", "summary": "x"}]}
                ],
            },
        )
        dates = api.write_horoscope_api(str(self.root), updated_at="2026-11-26T00:00:00Z")
        self.assertEqual(dates, ["2026-11-26"])


if __name__ == "__main__":
    unittest.main()

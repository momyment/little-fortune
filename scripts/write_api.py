#!/usr/bin/env python3
"""Write static JSON API files under api/v1/ from the repo data files.

The live site is GitHub Pages (static files only), so these paths are the
public API. The horoscope page fetches them at runtime; daily collection
updates the files and does not need a site rebuild.

Endpoints (with the Pages base path /little-fortune):

  GET /api/v1/horoscope/editions.json
  GET /api/v1/horoscope/YYYY-MM-DD.json
  GET /api/v1/fortunes/index.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

API_VERSION = 1
HOROSCOPE_FILE = "horoscope-editions.json"
FORTUNE_INDEX = "fortune-index.json"
FORTUNES_DIR = "fortunes"
API_ROOT = os.path.join("api", "v1")
IMAGE_PREFIX = "/little-fortune/fortunes"


def utc_now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, data) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _editions_from_legacy(raw) -> list[dict]:
    if isinstance(raw, dict) and "editions" in raw:
        raw = raw["editions"]
    if not isinstance(raw, list):
        raise ValueError("horoscope data must be a list of editions")
    editions: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("date"):
            continue
        editions.append(
            {
                "date": item["date"],
                "entries": list(item.get("entries") or []),
            }
        )
    editions.sort(key=lambda e: e["date"])
    return editions


def write_horoscope_api(root: str, updated_at: str | None = None) -> list[str]:
    """Backfill / overwrite horoscope API files from horoscope-editions.json."""
    legacy = load_json(os.path.join(root, HOROSCOPE_FILE), [])
    editions = _editions_from_legacy(legacy)
    stamp = updated_at or utc_now_iso()
    dates = [e["date"] for e in editions]
    out_dir = os.path.join(root, API_ROOT, "horoscope")
    dump_json(
        os.path.join(out_dir, "editions.json"),
        {
            "ok": True,
            "version": API_VERSION,
            "type": "horoscope-editions",
            "updated_at": stamp,
            "dates": dates,
            "editions": editions,
        },
    )
    written = set(dates)
    for edition in editions:
        day = edition["date"]
        dump_json(
            os.path.join(out_dir, f"{day}.json"),
            {
                "ok": True,
                "version": API_VERSION,
                "type": "horoscope-edition",
                "updated_at": stamp,
                "date": day,
                "edition": edition,
            },
        )
    # Leave older day files in place if the legacy list shrank; do not delete.
    written_list = dates
    print(f"[api] wrote {len(written)} horoscope edition(s) under {out_dir}")
    return written_list


def write_fortunes_api(root: str, updated_at: str | None = None) -> list[str]:
    """Backfill / overwrite the fortune index API from fortune-index.json."""
    index = load_json(os.path.join(root, FORTUNE_INDEX), {})
    if not isinstance(index, dict):
        raise ValueError("fortune-index.json must be an object of date -> shortcode")
    stamp = updated_at or utc_now_iso()
    fortunes = {}
    dates: list[str] = []
    for date, shortcode in sorted(index.items()):
        if not isinstance(date, str) or not isinstance(shortcode, str):
            continue
        dates.append(date)
        fortunes[date] = {
            "shortcode": shortcode,
            "image": f"{IMAGE_PREFIX}/{date}.jpg",
            "source": f"https://www.instagram.com/p/{shortcode}/",
        }
    dump_json(
        os.path.join(root, API_ROOT, "fortunes", "index.json"),
        {
            "ok": True,
            "version": API_VERSION,
            "type": "fortune-index",
            "updated_at": stamp,
            "dates": dates,
            "fortunes": fortunes,
        },
    )
    print(f"[api] wrote {len(dates)} fortune date(s) under {API_ROOT}/fortunes")
    return dates


def write_api(root: str, updated_at: str | None = None) -> None:
    stamp = updated_at or utc_now_iso()
    write_horoscope_api(root, updated_at=stamp)
    write_fortunes_api(root, updated_at=stamp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write api/v1/*.json from horoscope-editions.json and fortune-index.json"
    )
    parser.add_argument(
        "--root",
        default="",
        help="Repo root (default: parent of scripts/)",
    )
    args = parser.parse_args(argv)
    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    write_api(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())

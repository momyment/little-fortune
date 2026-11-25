#!/usr/bin/env python3
"""Daily collector for little-fortune (momyment/little-fortune).

What it collects, every day (KST), without anyone's computer turned on:

1. 띠별 운세 (zodiac-by-birth-year) image from Instagram @sinbi_saju.
   Source: the public profile embed page
   (https://www.instagram.com/sinbi_saju/embed/), which needs no login.
   It lists the latest posts with shortcode, caption and image URL.
   The matching post's image is saved as ``fortunes/YYYY-MM-DD.jpg``
   and its shortcode is recorded in ``fortune-index.json``.
2. 별자리 운세 (12-sign horoscope) from the official Asahi Broadcasting
   (ABC, おはよう朝日です) JSON feed
   (https://www.asahi.co.jp/data/ohaasa2020/horoscope.json),
   translated from Japanese to Korean and appended to
   ``horoscope-editions.json``.

Why this works without rebuilding the site: both pages fetch their data
in the browser (``fetch(..., {cache: "no-store"})``), so updating the
three data files is enough. The committed ``index.html`` /
``horoscope/index.html`` are only the first paint; the client JS
replaces them with the fresh data on load.

No third-party dependencies: standard library only, so the GitHub
Actions runner needs nothing installed.

Translation notes (read scripts/README.md for the full story):
- Lucky items (``lucky``) come from ``glossary.json`` first. It was
  built by aligning the 12 existing human-translated editions with the
  original Japanese, so recurring items keep the site's own wording.
  Unknown items fall back to Google Translate (direct ja -> ko), then
  to the MyMemory public API if Google rate-limits the runner.
- Summaries are translated with Google Translate via an English pivot
  (ja -> en -> ko). Direct ja -> ko mangled this colloquial horoscope
  Japanese ("チャンスが舞い込む" -> "기회가 춤춘다"), while the pivot
  stays close to the human translations. It is still machine
  translation: the Japanese original is kept in ``ja_summary`` /
  ``ja_lucky`` so any awkward line can be traced and fixed by hand.
- Translations are cached in ``scripts/translate-cache.json`` (keyed by
  source text and language pair) so repeated words are never requested
  again. Google 429 responses honor Retry-After, back off with jitter,
  and are retried; a failed translation is also retried in the wait loop
  instead of crashing the process immediately.

Exit codes: 0 = collected (or already up to date), 1 = hard error,
2 = today's data not published yet (after waiting).
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html as htmlmod
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KST = dt.timezone(dt.timedelta(hours=9))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
# Instagram serves different embed markup per User-Agent. The plain
# "Mozilla/5.0" UA returns the server-rendered page that lists recent
# posts (graphql_media); a full Chrome UA returns a JS-heavy page
# without them. Try in order.
IG_UAS = [
    "Mozilla/5.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    UA,
]

IG_USERNAME = "sinbi_saju"
IG_EMBED_URL = f"https://www.instagram.com/{IG_USERNAME}/embed/"
ABC_URL = "https://www.asahi.co.jp/data/ohaasa2020/horoscope.json"

# ABC horoscope_st code -> Korean sign name (verified against the
# 2026-11-24 edition: 04 = かに座 = 게자리 at rank 1, etc.)
SIGN_BY_CODE = {
    "01": "양자리",   # おひつじ座
    "02": "황소자리",  # おうし座
    "03": "쌍둥이자리",  # ふたご座
    "04": "게자리",   # かに座
    "05": "사자자리",  # しし座
    "06": "처녀자리",  # おとめ座
    "07": "천칭자리",  # てんびん座
    "08": "전갈자리",  # さそり座
    "09": "사수자리",  # いて座
    "10": "염소자리",  # やぎ座
    "11": "물병자리",  # みずがめ座
    "12": "물고기자리",  # うお座
}

FORTUNE_INDEX = "fortune-index.json"
HOROSCOPE_EDITIONS = "horoscope-editions.json"
FORTUNES_DIR = "fortunes"
TRANSLATE_CACHE = os.path.join("scripts", "translate-cache.json")
TRANSLATE_MIN_INTERVAL = 1.0
TRANSLATE_MAX_ATTEMPTS = 7
TRANSLATE_MAX_SLEEP = 90.0


def log(msg: str) -> None:
    print(f"[scrape] {msg}", flush=True)


def http_get(url: str, timeout: int = 25, user_agent: str | None = None) -> bytes:
    """GET with a browser UA, retried a few times on transient errors."""
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": user_agent or UA}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            log(f"GET {url[:80]}... failed (attempt {attempt}/3): {exc}")
            time.sleep(5 * attempt)
    raise RuntimeError(f"GET failed after 3 attempts: {url}") from last


# --------------------------------------------------------------------------
# Translation (Google Translate web endpoint, no key needed)
# --------------------------------------------------------------------------

# Pace HTTP calls across the process, and skip Google for the rest of
# a collect_once attempt once it has been rate-limited.
_last_translate_http = 0.0
_google_rate_limited = False


def _pace_translate() -> None:
    """Wait so consecutive translate HTTP calls are at least MIN_INTERVAL apart."""
    global _last_translate_http
    gap = TRANSLATE_MIN_INTERVAL - (time.monotonic() - _last_translate_http)
    if gap > 0:
        time.sleep(gap)


def _mark_translate_http() -> None:
    global _last_translate_http
    _last_translate_http = time.monotonic()


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    """Sleep length for a failed translate attempt: Retry-After or exp. backoff + jitter."""
    retry_after: float | None = None
    if isinstance(exc, urllib.error.HTTPError) and exc.headers:
        raw = exc.headers.get("Retry-After")
        if raw:
            try:
                retry_after = float(raw)
            except ValueError:
                try:
                    when = email.utils.parsedate_to_datetime(raw)
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=dt.timezone.utc)
                    retry_after = max(
                        0.0, (when - dt.datetime.now(dt.timezone.utc)).total_seconds()
                    )
                except (TypeError, ValueError, OverflowError):
                    retry_after = None
    base = float(2 ** attempt)  # 2, 4, 8, 16, ...
    sleep_for = retry_after if retry_after is not None else base
    sleep_for = min(TRANSLATE_MAX_SLEEP, max(1.0, sleep_for))
    return sleep_for + random.uniform(0, 0.3 * sleep_for)


def _is_retryable_translate(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {408, 425, 429, 500, 502, 503, 504} or exc.code == 403
    return isinstance(exc, (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError))


class TranslateCache:
    """JSON cache keyed by 'src|tgt|text'. Written after every new hit."""

    def __init__(self, path: str):
        self.path = path
        self.data: dict[str, str] = {}
        if os.path.exists(path):
            try:
                raw = load_json(path, {})
                if isinstance(raw, dict):
                    self.data = {str(k): str(v) for k, v in raw.items()}
            except (OSError, json.JSONDecodeError) as exc:
                log(f"translate cache unreadable, starting empty: {exc}")
        log(f"translate cache: {len(self.data)} entries ({path})")

    @staticmethod
    def make_key(text: str, src: str, tgt: str) -> str:
        return f"{src}|{tgt}|{text}"

    def get(self, text: str, src: str, tgt: str) -> str | None:
        return self.data.get(self.make_key(text, src, tgt))

    def put(self, text: str, src: str, tgt: str, value: str) -> None:
        key = self.make_key(text, src, tgt)
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self._save()

    def _save(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        dump_json(self.path, dict(sorted(self.data.items())))


def _parse_google_payload(data) -> str:
    if not data or not data[0]:
        raise RuntimeError("Google Translate returned an empty payload")
    return "".join(part[0] for part in data[0] if part and part[0]).strip()


def _google_translate_http(text: str, src: str, tgt: str) -> str:
    """One Google Translate request with retry/backoff. Does not use the cache."""
    global _google_rate_limited
    query = urllib.parse.urlencode(
        {"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text}
    )
    url = "https://translate.googleapis.com/translate_a/single?" + query
    last: Exception | None = None
    for attempt in range(1, TRANSLATE_MAX_ATTEMPTS + 1):
        try:
            _pace_translate()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.load(resp)
            finally:
                _mark_translate_http()
            out = _parse_google_payload(data)
            if not out:
                raise RuntimeError("Google Translate returned an empty string")
            return out
        except Exception as exc:  # noqa: BLE001 - retry, then surface
            last = exc
            retryable = _is_retryable_translate(exc)
            code = getattr(exc, "code", None)
            log(
                f"Google Translate {src}->{tgt} failed "
                f"(attempt {attempt}/{TRANSLATE_MAX_ATTEMPTS}): {exc}"
            )
            if (not retryable) or attempt >= TRANSLATE_MAX_ATTEMPTS:
                break
            sleep_for = _retry_after_seconds(exc, attempt)
            if code == 429:
                log(f"HTTP 429, backing off {sleep_for:.1f}s")
            else:
                log(f"retrying in {sleep_for:.1f}s")
            time.sleep(sleep_for)
    if isinstance(last, urllib.error.HTTPError) and last.code in {403, 429}:
        _google_rate_limited = True
    raise RuntimeError(f"translate {src}->{tgt} failed: {text!r}") from last


def mymemory_translate(text: str, src: str, tgt: str) -> str:
    """Public MyMemory fallback (no API key). Used only after Google is exhausted."""
    query = urllib.parse.urlencode({"q": text, "langpair": f"{src}|{tgt}"})
    url = "https://api.mymemory.translated.net/get?" + query
    _pace_translate()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    finally:
        _mark_translate_http()
    translated = (data.get("responseData") or {}).get("translatedText") or ""
    translated = htmlmod.unescape(str(translated)).strip()
    upper = translated.upper()
    if (
        not translated
        or upper.startswith("MYMEMORY")
        or "QUERY LENGTH" in upper
        or "INVALID LANGUAGE" in upper
    ):
        raise RuntimeError(f"mymemory rejected {text!r}: {translated!r}")
    return translated


def google_translate(text: str, src: str, tgt: str,
                     cache: "TranslateCache | None" = None) -> str:
    """Translate one string, using the cache, Google, then MyMemory."""
    global _google_rate_limited
    text = text.strip()
    if not text:
        return ""
    if cache:
        hit = cache.get(text, src, tgt)
        if hit is not None:
            return hit
    last: Exception | None = None
    if not _google_rate_limited:
        try:
            out = _google_translate_http(text, src, tgt)
            if cache:
                cache.put(text, src, tgt, out)
            return out
        except Exception as exc:  # noqa: BLE001 - fall back
            last = exc
            _google_rate_limited = True
            log("Google Translate exhausted; using MyMemory for the rest of this attempt")
    try:
        out = mymemory_translate(text, src, tgt)
        if cache:
            cache.put(text, src, tgt, out)
        log(f"MyMemory fallback {src}->{tgt}: {text!r} -> {out!r}")
        return out
    except Exception as exc:  # noqa: BLE001 - surface both failures
        raise RuntimeError(f"translate {src}->{tgt} failed: {text!r}") from (last or exc)


def google_translate_many(texts: list[str], src: str, tgt: str,
                          cache: "TranslateCache | None" = None) -> list[str]:
    """Translate many strings, batching uncached ones into one Google request when possible."""
    results: list[str | None] = [None] * len(texts)
    missing: list[int] = []
    for i, raw in enumerate(texts):
        text = raw.strip()
        if not text:
            results[i] = ""
            continue
        if cache:
            hit = cache.get(text, src, tgt)
            if hit is not None:
                results[i] = hit
                continue
        missing.append(i)
    if not missing:
        return [r or "" for r in results]

    unique: list[str] = []
    seen: set[str] = set()
    for i in missing:
        text = texts[i].strip()
        if text not in seen:
            seen.add(text)
            unique.append(text)

    translated: dict[str, str] = {}
    can_batch = (
        len(unique) > 1
        and (not _google_rate_limited)
        and all("\n" not in t for t in unique)
    )
    if can_batch:
        try:
            blob = "\n".join(unique)
            raw = _google_translate_http(blob, src, tgt)
            lines = [ln.strip() for ln in raw.split("\n")]
            if len(lines) != len(unique) or any(not ln for ln in lines):
                raise RuntimeError(
                    f"batch split {len(lines)} lines, expected {len(unique)}"
                )
            for src_text, out in zip(unique, lines):
                if cache:
                    cache.put(src_text, src, tgt, out)
                translated[src_text] = out
        except Exception as exc:  # noqa: BLE001 - one-by-one is the safe path
            log(f"batch translate {src}->{tgt} failed, one-by-one: {exc}")
            translated.clear()
    if len(translated) != len(unique):
        for src_text in unique:
            if src_text not in translated:
                translated[src_text] = google_translate(src_text, src, tgt, cache)

    for i in missing:
        results[i] = translated[texts[i].strip()]
    return [r or "" for r in results]


def translate_summary(ja_text: str, cache: TranslateCache) -> str:
    """Japanese horoscope summary -> Korean, via an English pivot."""
    hit = cache.get(ja_text, "ja", "ko")
    if hit is not None:
        return hit
    ko = google_translate(google_translate(ja_text, "ja", "en", cache), "en", "ko", cache)
    cache.put(ja_text, "ja", "ko", ko)
    return ko


def load_glossary(root: str) -> dict:
    path = os.path.join(root, "scripts", "glossary.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("lucky", {})
    except FileNotFoundError:
        log("glossary.json not found, lucky items will use machine translation")
        return {}


# --------------------------------------------------------------------------
# Instagram: @sinbi_saju daily fortune image
# --------------------------------------------------------------------------

def _unescape_embed(raw: str) -> str:
    """Undo the JSON string escaping used inside the embed page."""
    text = raw.replace('\\"', '"').replace("\\/", "/").replace("\\\\", "\\")
    return text


def parse_embed_posts(page: str) -> list[dict]:
    """Extract the recent posts listed in the embed page.

    Each entry: shortcode, is_video, caption (decoded when possible),
    taken_at_timestamp (KST date derived from it), display_url (1080px).
    """
    text = _unescape_embed(page)
    posts: list[dict] = []
    # One shortcode_media object per post; fields appear in this order:
    # shortcode, is_video, dimensions, display_url, ..., caption, ..., taken_at_timestamp
    pattern = re.compile(
        r'"shortcode":"([A-Za-z0-9_\-]+)".{0,4000}?'
        r'"display_url":"([^"]+)".{0,6000}?'
        r'"text":"((?:[^"\\]|\\.)*)".{0,1500}?'
        r'"taken_at_timestamp":(\d+)',
        re.S,
    )
    for m in pattern.finditer(text):
        shortcode, url, caption_raw, ts = m.groups()
        is_video = '"is_video":true' in text[m.start():m.start() + 400]
        caption = caption_raw
        try:
            caption = caption_raw.encode("utf-8").decode("unicode_escape")
        except Exception:  # noqa: BLE001 - keep the raw caption
            pass
        posted = dt.datetime.fromtimestamp(int(ts), tz=KST).date()
        posts.append(
            {
                "shortcode": shortcode,
                "is_video": is_video,
                "caption": caption,
                "posted_date": posted,
                "display_url": url.replace("\\", ""),
            }
        )
    return posts


def caption_date(caption: str) -> dt.date | None:
    """'11월 24일 오늘의 띠별 운세입니다.' -> date (year taken from context)."""
    m = re.search(r"(\d+)\s*월\s*(\d+)\s*일", caption)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def fetch_instagram_post(target: dt.date, shortcode_override: str | None) -> dict:
    """Find today's fortune post. Returns {shortcode, image_url}."""
    if shortcode_override:
        # Single-post embed page contains the 1080px CDN URL directly.
        url = f"https://www.instagram.com/p/{shortcode_override}/embed/"
        log(f"shortcode override given, fetching {url}")
        page = http_get(url, user_agent=IG_UAS[0]).decode("utf-8", errors="ignore")
        m = re.search(
            r"https://[^\s\"\\]*cdninstagram[^\s\"\\]*?s1080x1080[^\s\"\\]*",
            page,
        )
        if m:
            image_url = htmlmod.unescape(m.group(0)).replace("\\", "")
            return {"shortcode": shortcode_override, "image_url": image_url}
        m = re.search(
            r'<meta property="og:image" content="([^"]+)"',
            htmlmod.unescape(page),
        )
        if m:
            log("warning: only the 640px og:image was found for the override")
            return {"shortcode": shortcode_override, "image_url": m.group(1)}
        raise RuntimeError(
            f"could not find an image for shortcode {shortcode_override}"
        )

    log(f"fetching Instagram embed page for @{IG_USERNAME}")
    posts: list[dict] = []
    for ua in IG_UAS:
        try:
            page = http_get(IG_EMBED_URL, user_agent=ua).decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001 - try the next UA
            log(f"embed fetch failed with UA {ua[:30]!r}: {exc}")
            continue
        posts = parse_embed_posts(page)
        log(f"embed page lists {len(posts)} recent posts (UA {ua[:30]!r})")
        if posts:
            break
    if not posts:
        raise LookupError(
            f"embed page for @{IG_USERNAME} lists no posts "
            "(Instagram may have changed its markup or blocked the request)"
        )
    for post in posts:
        if post["is_video"]:
            continue
        cap = caption_date(post["caption"])
        month_day = (target.month, target.day)
        # Posts go up at 00:00 KST on the fortune date itself.
        if post["posted_date"] == target or cap == month_day:
            if cap is not None and cap != month_day:
                log(f"skipping {post['shortcode']}: caption date mismatch")
                continue
            log(
                f"matched {post['shortcode']} for {target} "
                f"(posted {post['posted_date']}, caption: {post['caption'][:40]!r})"
            )
            return {"shortcode": post["shortcode"], "image_url": post["display_url"]}
    raise LookupError(
        f"no @{IG_USERNAME} post found for {target} "
        f"(saw: {[(p['shortcode'], str(p['posted_date'])) for p in posts]})"
    )


def download_image(url: str, dest: str) -> None:
    data = http_get(url)
    if not data.startswith(b"\xff\xd8\xff"):
        raise RuntimeError(f"downloaded file is not a JPEG: {url[:100]}")
    if len(data) < 50_000:
        raise RuntimeError(f"downloaded image suspiciously small ({len(data)} bytes)")
    with open(dest, "wb") as f:
        f.write(data)
    log(f"saved {dest} ({len(data)} bytes)")


# --------------------------------------------------------------------------
# ABC horoscope
# --------------------------------------------------------------------------

def fetch_abc(target: dt.date) -> list[dict] | None:
    """Fetch the official ABC JSON; return today's entries or None."""
    raw = http_get(ABC_URL)
    feed = json.loads(raw.decode("utf-8"))
    if not feed:
        raise RuntimeError("ABC horoscope feed is empty")
    edition = feed[0]
    onair = edition.get("onair_date", "")
    try:
        aired = dt.datetime.strptime(onair, "%Y%m%d").date()
    except ValueError:
        raise RuntimeError(f"unexpected ABC onair_date: {onair!r}") from None
    log(f"ABC feed onair_date is {aired} (target {target})")
    if aired != target:
        return None
    entries: list[dict] = []
    for detail in edition.get("detail", []):
        parts = [p.strip() for p in detail.get("horoscope_text", "").split("\t")]
        parts = [p for p in parts if p]
        if len(parts) < 2:
            raise RuntimeError(f"unexpected ABC text format: {detail!r}")
        lucky_ja, summary_ja = parts[-1], " ".join(parts[:-1])
        entries.append(
            {
                "rank": int(detail["ranking_no"]),
                "sign": SIGN_BY_CODE[detail["horoscope_st"]],
                "ja_summary": summary_ja,
                "ja_lucky": lucky_ja,
            }
        )
    entries.sort(key=lambda e: e["rank"])
    if len(entries) != 12 or {e["rank"] for e in entries} != set(range(1, 13)):
        raise RuntimeError(f"ABC edition has {len(entries)} entries, expected 12")
    return entries


def translate_entries(entries: list[dict], glossary: dict,
                      cache: TranslateCache) -> list[dict]:
    global _google_rate_limited
    _google_rate_limited = False

    luckies: list[str | None] = []
    uncached_lucky: list[str] = []
    for entry in entries:
        lucky_ja = entry["ja_lucky"]
        lucky = glossary.get(lucky_ja)
        if lucky:
            log(f"lucky {lucky_ja!r} -> glossary {lucky!r}")
            luckies.append(lucky)
            continue
        hit = cache.get(lucky_ja, "ja", "ko")
        if hit is not None:
            log(f"lucky {lucky_ja!r} -> cache {hit!r}")
            luckies.append(hit)
            continue
        luckies.append(None)
        uncached_lucky.append(lucky_ja)

    if uncached_lucky:
        got = google_translate_many(uncached_lucky, "ja", "ko", cache)
        it = iter(got)
        luckies = [lu if lu is not None else next(it) for lu in luckies]
        for lucky_ja, lucky in zip(uncached_lucky, got):
            log(f"lucky {lucky_ja!r} -> translated {lucky!r}")

    summaries: list[str | None] = []
    uncached_sum: list[str] = []
    for entry in entries:
        hit = cache.get(entry["ja_summary"], "ja", "ko")
        if hit is not None:
            summaries.append(hit)
        else:
            summaries.append(None)
            uncached_sum.append(entry["ja_summary"])
    if uncached_sum:
        # Pivot ja -> en -> ko, batched, then remember the direct ja -> ko mapping.
        ens = google_translate_many(uncached_sum, "ja", "en", cache)
        kos = google_translate_many(ens, "en", "ko", cache)
        for ja, ko in zip(uncached_sum, kos):
            cache.put(ja, "ja", "ko", ko)
        it = iter(kos)
        summaries = [su if su is not None else next(it) for su in summaries]

    out: list[dict] = []
    for entry, lucky, summary in zip(entries, luckies, summaries):
        out.append(
            {
                "rank": entry["rank"],
                "sign": entry["sign"],
                "summary": summary or "",
                "lucky": lucky or "",
                "ja_summary": entry["ja_summary"],
                "ja_lucky": entry["ja_lucky"],
            }
        )
    return out


# --------------------------------------------------------------------------
# File updates (idempotent)
# --------------------------------------------------------------------------

def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def update_fortune(root: str, target: dt.date, post: dict) -> bool:
    """Download + record the fortune. Returns True if the date is now present."""
    index_path = os.path.join(root, FORTUNE_INDEX)
    index = load_json(index_path, {})
    key = target.isoformat()
    img_path = os.path.join(root, FORTUNES_DIR, f"{key}.jpg")
    if index.get(key) == post["shortcode"] and os.path.exists(img_path):
        log(f"fortune for {key} already collected ({post['shortcode']})")
        return True
    os.makedirs(os.path.join(root, FORTUNES_DIR), exist_ok=True)
    download_image(post["image_url"], img_path)
    index[key] = post["shortcode"]
    dump_json(index_path, index)
    log(f"fortune-index.json: {key} -> {post['shortcode']}")
    return True


def update_horoscope(root: str, target: dt.date, entries: list[dict]) -> bool:
    path = os.path.join(root, HOROSCOPE_EDITIONS)
    editions = load_json(path, [])
    key = target.isoformat()
    if any(e.get("date") == key for e in editions):
        log(f"horoscope for {key} already collected")
        return True
    editions.append({"date": key, "entries": entries})
    editions.sort(key=lambda e: e.get("date", ""))
    dump_json(path, editions)
    log(f"horoscope-editions.json: added {key} ({len(entries)} signs)")
    return True


# --------------------------------------------------------------------------

def collect_once(root: str, target: dt.date, shortcode_override: str | None,
                 glossary: dict, cache: TranslateCache) -> tuple[bool, bool]:
    """One attempt. Returns (fortune_satisfied, horoscope_satisfied):
    True when that side's data for the date is present (newly collected
    or already there), False when it still needs to be waited for."""
    fortune_done = horoscope_done = False
    try:
        post = fetch_instagram_post(target, shortcode_override)
        fortune_done = update_fortune(root, target, post)
    except LookupError as exc:
        log(f"fortune not published yet: {exc}")
    except Exception as exc:  # noqa: BLE001 - reported, retried by caller
        log(f"fortune collection failed: {exc}")

    # ABC airs on weekdays (Mon-Fri) only: the existing editions skip
    # Sat/Sun (e.g. no 2026-11-14/15), so a missing weekend edition is
    # normal, not an error.
    if target.weekday() >= 5:
        log(f"{target} is a weekend, skipping horoscope (ABC is Mon-Fri)")
        horoscope_done = True
    elif any(
        e.get("date") == target.isoformat()
        for e in load_json(os.path.join(root, HOROSCOPE_EDITIONS), [])
    ):
        log(f"horoscope for {target} already collected")
        horoscope_done = True
    else:
        try:
            entries = fetch_abc(target)
        except Exception as exc:  # noqa: BLE001 - reported, retried by caller
            log(f"horoscope collection failed: {exc}")
            entries = None
        if entries is None:
            log("horoscope not published yet")
        else:
            try:
                translated = translate_entries(entries, glossary, cache)
                horoscope_done = update_horoscope(root, target, translated)
            except Exception as exc:  # noqa: BLE001 - retried by the wait loop
                log(f"horoscope translation failed: {exc}")
    return fortune_done, horoscope_done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect today's little-fortune data")
    parser.add_argument("--date", default="",
                        help="Target date YYYY-MM-DD in KST (default: today)")
    parser.add_argument("--wait-minutes", type=int, default=120,
                        help="Keep retrying until today's posts appear (default: 120)")
    parser.add_argument("--poll-seconds", type=int, default=600,
                        help="Seconds between retries (default: 600)")
    parser.add_argument("--fortune-shortcode", default="",
                        help="Instagram shortcode override for the fortune image")
    parser.add_argument("--root", default="",
                        help="Repo root (default: parent of scripts/)")
    args = parser.parse_args(argv)

    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.date:
        target = dt.date.fromisoformat(args.date)
    else:
        target = dt.datetime.now(KST).date()
    glossary = load_glossary(root)
    cache = TranslateCache(os.path.join(root, TRANSLATE_CACHE))
    log(f"target date: {target} ({target.strftime('%A')}), root: {root}")

    deadline = time.monotonic() + max(0, args.wait_minutes) * 60
    attempt = 0
    while True:
        attempt += 1
        log(f"attempt {attempt}")
        fortune_done, horoscope_done = collect_once(
            root, target, args.fortune_shortcode or None, glossary, cache
        )
        if fortune_done and horoscope_done:
            # Both sides done. But "done" also means "already collected":
            # verify today's data is actually present before finishing.
            index = load_json(os.path.join(root, FORTUNE_INDEX), {})
            editions = load_json(os.path.join(root, HOROSCOPE_EDITIONS), [])
            has_fortune = target.isoformat() in index
            has_horoscope = target.weekday() >= 5 or any(
                e.get("date") == target.isoformat() for e in editions
            )
            if has_fortune and has_horoscope:
                log(f"all done for {target}")
                return 0
        if time.monotonic() >= deadline:
            log(f"gave up after {args.wait_minutes} min: {target} not fully published")
            return 2
        sleep_for = min(args.poll_seconds, max(0, deadline - time.monotonic()))
        log(f"waiting {sleep_for:.0f}s for publication...")
        time.sleep(sleep_for)


if __name__ == "__main__":
    sys.exit(main())

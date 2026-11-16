#!/usr/bin/env python3
"""
Engoo Daily News – robust daily fetcher
- 3 new articles per topic (levels 4-9)
- Skips existing articles
- Retries + clear error reporting
- Writes status.json so you can see what happened
"""

import re
import time
import json
import traceback
import requests
from pathlib import Path
from datetime import datetime, timezone

# ====================== CONFIG ======================
ROOT = Path(__file__).resolve().parent.parent

TOPICS = {
    "Business_Politics": "838db612-5db8-4f6f-9ca7-8643e42de879",
    "Science_Technology": "36c03b50-bbba-481f-a7e4-d2b29d3fa47c",
    "Health_Lifestyle": "80531599-4b8d-43b6-ad11-e4b4f58b7365",
    "Culture_Society": "1a633e68-dba4-4cba-857a-a9dca82b92c1",
    "Travel_Experiences": "06fb2b41-5ebc-4dc8-aea9-779bb60c2224",
}

CATEGORY_ID = "0225ae09-5d63-41c2-bd75-693985d07d78"
BRAND = "5a4657f2-e151-4c48-9cce-000000000002"

MIN_LEVEL = 4
MAX_LEVEL = 9
ARTICLES_PER_TOPIC = 3
MAX_LOOKBACK_PAGES = 5
MAX_RETRIES = 3
RETRY_DELAY = 4          # seconds between retries
REQUEST_TIMEOUT = 25

# ====================================================

session = requests.Session()
session.headers.update({
    "User-Agent": "EngooDailyGitBot/1.1 (educational use)",
    "Accept": "application/json",
})


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def safe_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[<>:"/\\|?*\n\r\t]', "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:max_len].rstrip("._") or "untitled"


def normalize_title(t: str) -> str:
    t = re.sub(r"[^\w\s]", "", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def get_existing_titles(folder: Path) -> set:
    titles = set()
    if not folder.exists():
        return titles
    for f in folder.glob("*.txt"):
        try:
            first = f.read_text(encoding="utf-8").splitlines()[0]
            if first.startswith("Title: "):
                titles.add(normalize_title(first[7:]))
            else:
                titles.add(normalize_title(f.stem))
        except Exception:
            titles.add(normalize_title(f.stem))
    return titles


def request_with_retry(method: str, url: str, **kwargs):
    """Simple retry wrapper for network resilience."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
            if r.status_code == 429:
                wait = RETRY_DELAY * attempt * 2
                print(f"    [rate-limit] 429 – waiting {wait}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            if r.status_code in (403, 401):
                raise RuntimeError(
                    f"Access denied (HTTP {r.status_code}). "
                    "Engoo may have blocked the request or changed authentication."
                )
            if r.status_code >= 500:
                print(f"    [server error] {r.status_code} – retrying ({attempt}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY * attempt)
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout as e:
            last_error = e
            print(f"    [timeout] attempt {attempt}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY * attempt)
        except requests.exceptions.ConnectionError as e:
            last_error = e
            print(f"    [connection error] attempt {attempt}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY * attempt)
        except RuntimeError:
            raise
        except Exception as e:
            last_error = e
            print(f"    [error] {type(e).__name__}: {e} (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries. Last error: {last_error}")


def fetch_headers(course_id: str, start: int = 0, page_size: int = 30) -> list:
    params = {
        "category": CATEGORY_ID,
        "course": course_id,
        "database_timeout": 10,
        "direction": "desc",
        "for_brand": BRAND,
        "max_level": MAX_LEVEL,
        "min_level": MIN_LEVEL,
        "order": "last_published_at",
        "page_size": page_size,
        "published_latest": "true",
        "start": start,
        "type": "Published",
    }
    r = request_with_retry("GET", "https://api.engoo.com/api/lesson_headers", params=params)
    data = r.json()
    if "data" not in data:
        # Possible API structure change
        raise RuntimeError(
            "Unexpected API response structure (missing 'data' key). "
            "Engoo may have changed their API. Full response keys: " + str(list(data.keys())[:10])
        )
    return data["data"]


def fetch_lesson(lesson_id: str) -> dict:
    r = request_with_retry("GET", f"https://api.engoo.com/api/lessons/{lesson_id}")
    data = r.json()
    if "data" not in data:
        raise RuntimeError("Unexpected lesson response structure (missing 'data').")
    return data["data"]


def extract_article(lesson: dict) -> str:
    title = lesson.get("title_text", {}).get("text", "Untitled")
    level = lesson.get("content_level", "?")
    date = (lesson.get("last_published_at") or "")[:10]

    lines = [
        f"Title: {title}",
        f"Level: {level}",
        f"Date: {date}",
        f"Fetched: {now_utc()}",
        "",
        "=" * 60,
        "",
    ]

    found_article = False
    for ex in lesson.get("exercises", []):
        for sec in ex.get("sections", []):
            if sec.get("_type") == "ArticleSection":
                found_article = True
                lines.append("ARTICLE")
                lines.append("-" * 40)
                for para in sec.get("paragraphs", []):
                    sents = []
                    for ps in para.get("paragraph_sentences", []):
                        t = None
                        if isinstance(ps, dict):
                            if "text" in ps and isinstance(ps["text"], str):
                                t = ps["text"]
                            else:
                                def find_text(o, depth=0):
                                    if depth > 6:
                                        return None
                                    if isinstance(o, dict):
                                        if "text" in o and isinstance(o["text"], str) and len(o["text"]) > 10:
                                            return o["text"]
                                        for v in o.values():
                                            r = find_text(v, depth + 1)
                                            if r:
                                                return r
                                    return None
                                t = find_text(ps)
                        if t:
                            sents.append(t.strip())
                    if sents:
                        lines.append(" ".join(sents))
                        lines.append("")
                lines.append("")
                break
        if found_article:
            break

    if not found_article:
        lines.append("[WARNING] Could not locate ArticleSection – structure may have changed.")
        lines.append("")

    # Vocab note
    for ex in lesson.get("exercises", []):
        for sec in ex.get("sections", []):
            if sec.get("_type") == "VocabSection":
                n = len(sec.get("vocab_section_words", []))
                if n:
                    lines.insert(6, "VOCABULARY")
                    lines.insert(7, "-" * 40)
                    lines.insert(8, f"( {n} vocabulary items in the original lesson )")
                    lines.insert(9, "")
                break
        else:
            continue
        break

    return "\n".join(lines).strip() + "\n"


def process_topic(topic_name: str, course_id: str, status: dict) -> int:
    folder = ROOT / topic_name
    folder.mkdir(exist_ok=True)
    existing = get_existing_titles(folder)

    topic_status = {
        "existing": len(existing),
        "added": 0,
        "errors": [],
        "articles": [],
    }
    status["topics"][topic_name] = topic_status

    print(f"\n[{topic_name}] already have {len(existing)} articles")

    candidates = []
    start = 0

    try:
        for page in range(MAX_LOOKBACK_PAGES):
            headers = fetch_headers(course_id, start=start, page_size=30)
            if not headers:
                break
            for h in headers:
                title = h.get("title_text", {}).get("text", "")
                nt = normalize_title(title)
                level = h.get("content_level")
                if level is None or not (MIN_LEVEL <= level <= MAX_LEVEL):
                    continue
                if nt in existing:
                    continue
                if any(normalize_title(c.get("title_text", {}).get("text", "")) == nt for c in candidates):
                    continue
                candidates.append(h)
                if len(candidates) >= ARTICLES_PER_TOPIC + 3:
                    break
            if len(candidates) >= ARTICLES_PER_TOPIC:
                break
            start += 30
            time.sleep(0.5)
    except Exception as e:
        msg = f"Failed to list articles: {e}"
        print(f"  ERROR: {msg}")
        topic_status["errors"].append(msg)
        status["ok"] = False
        return 0

    print(f"  candidates found: {len(candidates)}")

    saved = 0
    for h in candidates[:ARTICLES_PER_TOPIC]:
        title = h.get("title_text", {}).get("text", "untitled")
        level = h.get("content_level", "?")
        print(f"  → L{level}  {title[:65]}")

        try:
            lesson = fetch_lesson(h["id"])
            content = extract_article(lesson)
            fname = f"{safe_filename(title)}_level{level}.txt"
            path = folder / fname

            if path.exists():
                print("    (file already exists – skip)")
                continue

            path.write_text(content, encoding="utf-8")
            existing.add(normalize_title(title))
            saved += 1
            topic_status["articles"].append({"title": title, "level": level, "file": fname})
            time.sleep(0.4)

        except Exception as e:
            err = f"{title[:40]}… → {type(e).__name__}: {e}"
            print(f"    FAIL: {err}")
            topic_status["errors"].append(err)
            status["ok"] = False

    topic_status["added"] = saved
    return saved


def main():
    print("=" * 60)
    print(f"Engoo Daily fetch started – {now_utc()}")
    print(f"Target: {ARTICLES_PER_TOPIC} new articles × {len(TOPICS)} topics  (levels {MIN_LEVEL}-{MAX_LEVEL})")
    print("=" * 60)

    status = {
        "started": now_utc(),
        "ok": True,
        "total_added": 0,
        "topics": {},
        "fatal_error": None,
    }

    try:
        total = 0
        for name, course in TOPICS.items():
            total += process_topic(name, course, status)
        status["total_added"] = total

    except Exception as e:
        status["ok"] = False
        status["fatal_error"] = f"{type(e).__name__}: {e}"
        print("\nFATAL ERROR:")
        traceback.print_exc()

    status["finished"] = now_utc()

    # Write status file (always)
    status_path = ROOT / "status.json"
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable summary
    summary_path = ROOT / "last_run.txt"
    lines = [
        f"Last run : {status['finished']}",
        f"Success  : {status['ok']}",
        f"Added    : {status['total_added']} articles",
        "",
    ]
    for topic, info in status["topics"].items():
        lines.append(f"{topic}: +{info['added']}  (errors: {len(info['errors'])})")
        for err in info["errors"][:3]:
            lines.append(f"   • {err}")
    if status.get("fatal_error"):
        lines.append("")
        lines.append(f"FATAL: {status['fatal_error']}")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"Finished. Added {status['total_added']} articles. Success={status['ok']}")
    if not status["ok"]:
        print("There were errors – check status.json and the log above.")
        print("If Engoo changed their API you will need to update the script.")
    print("=" * 60)

    # Exit with non-zero code only on complete failure (so GitHub marks the job red)
    if not status["ok"] and status["total_added"] == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

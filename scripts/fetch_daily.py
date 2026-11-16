#!/usr/bin/env python3
"""
Engoo Daily News – fetch 3 new articles per topic (levels 4-9)
Runs daily via GitHub Actions. Skips articles that already exist in the repo.
"""

import os
import re
import time
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

# === Config ===
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
MIN_LEVEL, MAX_LEVEL = 4, 9
ARTICLES_PER_TOPIC = 3
MAX_LOOKBACK_PAGES = 4  # how far back to search for new ones

session = requests.Session()
session.headers.update({
    "User-Agent": "EngooDailyGitBot/1.0 (educational; github.com)",
    "Accept": "application/json",
})


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
    r = session.get("https://api.engoo.com/api/lesson_headers", params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_lesson(lesson_id: str) -> dict:
    r = session.get(f"https://api.engoo.com/api/lessons/{lesson_id}", timeout=30)
    r.raise_for_status()
    return r.json().get("data", {})


def extract_article(lesson: dict) -> str:
    title = lesson.get("title_text", {}).get("text", "Untitled")
    level = lesson.get("content_level", "?")
    date = (lesson.get("last_published_at") or "")[:10]

    lines = [
        f"Title: {title}",
        f"Level: {level}",
        f"Date: {date}",
        f"Fetched: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "=" * 60,
        "",
    ]

    # Article body only
    for ex in lesson.get("exercises", []):
        for sec in ex.get("sections", []):
            if sec.get("_type") == "ArticleSection":
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
                                def find_text(o):
                                    if isinstance(o, dict):
                                        if "text" in o and isinstance(o["text"], str) and len(o["text"]) > 10:
                                            return o["text"]
                                        for v in o.values():
                                            r = find_text(v)
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


def process_topic(topic_name: str, course_id: str) -> int:
    folder = ROOT / topic_name
    folder.mkdir(exist_ok=True)
    existing = get_existing_titles(folder)
    print(f"\n[{topic_name}] existing files: {len(existing)}")

    candidates = []
    start = 0
    for _ in range(MAX_LOOKBACK_PAGES):
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
            if len(candidates) >= ARTICLES_PER_TOPIC + 2:
                break
        if len(candidates) >= ARTICLES_PER_TOPIC:
            break
        start += 30
        time.sleep(0.4)

    print(f"  new candidates found: {len(candidates)}")
    saved = 0
    for h in candidates[:ARTICLES_PER_TOPIC]:
        title = h.get("title_text", {}).get("text", "untitled")
        level = h.get("content_level", "?")
        print(f"  → L{level}  {title[:60]}")
        try:
            lesson = fetch_lesson(h["id"])
            content = extract_article(lesson)
            fname = f"{safe_filename(title)}_level{level}.txt"
            path = folder / fname
            if path.exists():
                print("    (already exists on disk, skip)")
                continue
            path.write_text(content, encoding="utf-8")
            existing.add(normalize_title(title))
            saved += 1
            time.sleep(0.35)
        except Exception as e:
            print(f"    ERROR: {e}")
    return saved


def main():
    print(f"Engoo Daily fetch – {datetime.now(timezone.utc).isoformat()}")
    print(f"Target: {ARTICLES_PER_TOPIC} new articles per topic (levels {MIN_LEVEL}-{MAX_LEVEL})")
    total = 0
    for name, course in TOPICS.items():
        total += process_topic(name, course)
    print(f"\nDone. Added {total} new articles.")
    # Write a small status file for the workflow log
    status = ROOT / "last_run.txt"
    status.write_text(
        f"Last run: {datetime.now(timezone.utc).isoformat()}\n"
        f"Articles added: {total}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

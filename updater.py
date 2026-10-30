#!/usr/bin/env python3
"""Pulls Hebrew news RSS feeds, keeps items about PM / Defense Minister /
Mossad head / Shin Bet head, and writes data.json. Standard library only."""
import json, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Add or remove feeds here. Each one: (display name, RSS/Atom URL).
FEEDS = [
    ("ynet", "https://www.ynet.co.il/Integration/StoryRss2.xml"),
    ("טיימס אוף ישראל", "https://he.timesofisrael.com/feed/"),
]

# Order matters: the first category that matches wins.
RULES = [
    ("mossad", ["ראש המוסד", "גופמן"]),
    ("shin",   ["ראש השבכ", "זיני"]),
    ("def",    ["שר הביטחון", "ישראל כץ"]),
    ("pm",     ["ראש הממשלה", "נתניהו", "רהמ"]),
]
MAX_ITEMS = 300
UA = {"User-Agent": "Mozilla/5.0 (security-updates-bot)"}

def norm(s):
    return re.sub(r"[\"'״׳”“’‘`]", "", s or "")

def classify(text):
    t = norm(text)
    for cat, words in RULES:
        if any(norm(w) in t for w in words):
            return cat
    return None

def parse_date(s):
    if not s:
        return datetime.now(timezone.utc)
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def tag(e):
    return e.tag.split("}")[-1]

def fetch(name, url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        root = ET.fromstring(r.read())
    out = []
    for e in root.iter():
        if tag(e) not in ("item", "entry"):
            continue
        f = {tag(c): c for c in e}
        title = (f["title"].text or "").strip() if "title" in f else ""
        link = ""
        if "link" in f:
            link = (f["link"].text or f["link"].attrib.get("href", "")).strip()
        desc = ""
        for k in ("description", "summary", "content"):
            if k in f and f[k].text:
                desc = f[k].text
                break
        date = ""
        for k in ("pubDate", "published", "updated", "date"):
            if k in f and f[k].text:
                date = f[k].text
                break
        cat = classify(title + " " + re.sub(r"<[^>]+>", " ", desc))
        if cat and title and link:
            out.append({"title": title, "link": link, "source": name,
                        "ts": parse_date(date).isoformat(), "cat": cat})
    return out

def main():
    try:
        with open("data.json", encoding="utf-8") as f:
            old = json.load(f).get("items", [])
    except Exception:
        old = []
    items = {i["link"]: i for i in old}
    ok = 0
    for name, url in FEEDS:
        try:
            got = fetch(name, url)
            ok += 1
            new = [g for g in got if g["link"] not in items]
            for g in got:
                items.setdefault(g["link"], g)
            print(f"{name}: {len(got)} relevant, {len(new)} new")
        except Exception as ex:
            print(f"{name}: FAILED ({ex})", file=sys.stderr)
    merged = sorted(items.values(), key=lambda x: x["ts"], reverse=True)[:MAX_ITEMS]
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(),
                   "items": merged}, f, ensure_ascii=False, indent=1)
    if ok == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pulls Hebrew news RSS feeds and keeps security-related headlines in data.json."""
import json, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = [
    ("ynet", "https://www.ynet.co.il/Integration/StoryRss2.xml"),
    ("טיימס אוף ישראל", "https://he.timesofisrael.com/feed/"),
    ("וואלה", "https://rss.walla.co.il/feed/1?type=main"),
    ("מעריב", "https://www.maariv.co.il/rss/rsschadashot"),
    ("מעריב מבזקים", "https://www.maariv.co.il/rss/rssfeedsmivzakichadashot"),
]

# The first matching category wins. Matching is on the TITLE only.
RULES = [
    ("intel", ["ראש המוסד", "גופמן", "המוסד", "ראש השבכ", "זיני", "השבכ"]),
    ("idf",   ["הרמטכל", "אייל זמיר", "פיקוד הצפון", "פיקוד המרכז", "פיקוד הדרום"]),
    ("leb",   ["לבנון", "חיזבאללה", "נעים קאסם", "הליטאני", "ביירות"]),
    ("gaza",  ["עזה", "חמאס", "הקו הצהוב"]),
    ("syr",   ["סוריה", "סורי", "א-שרע", "דמשק", "החרמון", "אזור החיץ"]),
    ("iran",  ["איראן", "איראני", "טהרן", "פורדו", "הורמוז"]),
    ("gov",   ["שר הביטחון", "ישראל כץ", "שר החוץ", "גדעון סער", "ראש הממשלה", "נתניהו"]),
]
EXCLUDE = ["לביטוח לאומי"]
SECURITY = ["איראן", "ביטחו", "צהל", "מלחמ", "חמאס", "חיזבאללה", "תקיפ",
            "מבצע", "רמטכל", "עזה", "לבנון", "טילים", "סוריה", "תימן", "החות"]
MAX_ITEMS = 400
UA = {"User-Agent": "Mozilla/5.0 (security-news-bot)"}

def norm(s):
    return re.sub(r"[\"'״׳”“’‘`]", "", s or "")

def classify(title):
    t = norm(title)
    if any(x in t for x in EXCLUDE):
        return None
    for cat, words in RULES:
        if any(norm(w) in t for w in words):
            # PM / general government stories need a security word in the title.
            if cat == "gov" and ("שר הביטחון" not in t and "ישראל כץ" not in t
                                 and "שר החוץ" not in t and "גדעון סער" not in t
                                 and not any(w in t for w in SECURITY)):
                continue
            return cat
    return None

def parse_date(s):
    now = datetime.now(timezone.utc)
    if not s:
        return now
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return now
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

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
        date = ""
        for k in ("pubDate", "published", "updated", "date"):
            if k in f and f[k].text:
                date = f[k].text
                break
        cat = classify(title)
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
    items = {}
    for i in old:  # re-check old items against the current rules
        c = classify(i.get("title", ""))
        if c and i.get("link"):
            i["cat"] = c
            i.pop("manual", None)
            items[i["link"]] = i
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

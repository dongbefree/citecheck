#!/usr/bin/env python3
"""B-layer: existence check against Crossref + Open Library.

Deliberately narrower than a "find the best match" engine. It answers one
question only: does a record with this title exist, and if so do year and
publisher agree? A wrong verdict here is worse than no verdict, so anything
below the confidence bar is reported as 无法核实, never as 错误.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audit import parse, units

UA = "citation-audit/0.1 (mailto:noreply@example.org)"
CONF = 0.86


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def sim(a: str, b: str) -> float:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return max(SequenceMatcher(None, na, nb).ratio(), jac)


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def crossref(title: str) -> list[dict]:
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query.bibliographic": title, "rows": 10,
         "select": "title,author,issued,publisher,DOI,type,container-title"})
    try:
        items = get(url + "&mailto=noreply@example.org")["message"]["items"]
    except Exception:
        return []
    return [{"src": "crossref", "title": (i.get("title") or [""])[0],
             "year": (i.get("issued", {}).get("date-parts") or [[None]])[0][0],
             "publisher": i.get("publisher", ""), "doi": i.get("DOI", ""),
             "type": i.get("type", ""),
             "container": (i.get("container-title") or [""])[0]} for i in items]


def openlibrary(title: str) -> list[dict]:
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(
        {"title": title, "limit": 8,
         "fields": "title,author_name,first_publish_year,publisher,key"})
    try:
        docs = get(url).get("docs", [])
    except Exception:
        return []
    out = []
    for d in docs:
        pubs = d.get("publisher") or []
        out.append({"src": "openlibrary", "title": d.get("title", ""),
                    "year": d.get("first_publish_year"),
                    "publisher": pubs[0] if pubs else "", "doi": d.get("key", ""),
                    "type": "book", "container": ""})
    return out


def check(unit: dict) -> dict:
    t, y = unit["title"], unit["year"]
    cands = crossref(t) + openlibrary(t)
    scored = [(sim(t, c["title"]), c) for c in cands]
    scored.sort(key=lambda x: -x[0])
    if not scored or scored[0][0] < CONF:
        return {**unit, "status": "无法核实", "best": None, "conf": round(scored[0][0], 2) if scored else 0}
    conf, c = scored[0]
    diffs = []
    if y and c["year"] and abs(int(c["year"]) - int(y)) > 1:
        diffs.append(f"年份：引用 {y}，记录 {c['year']}")
    q = (unit.get("publisher") or "").lower()
    r = (c["publisher"] or "").lower()
    if q and r and not (q.split()[0] in r or r.split()[0] in q):
        diffs.append(f"出版社：引用 {unit['publisher']}，记录 {c['publisher']}")
    return {**unit, "status": "存在" if not diffs else "存在但字段不符",
            "best": c, "diffs": diffs, "conf": round(conf, 2)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    a = ap.parse_args()
    _, notes = parse(open(a.file, encoding="utf-8").read())
    works = []
    seen = set()
    for n, raw in notes.items():
        for u in units(raw):
            k = norm(u["title"])[:60]
            if k in seen:
                continue
            seen.add(k)
            works.append((n, u))
    rows = []
    for n, u in works:
        r = check(u)
        b = r["best"] or {}
        rows.append({"note": n, "title": u["title"], "year": u["year"],
                     "status": r["status"], "conf": r["conf"],
                     "record": (b.get("title") or "")[:80], "rec_year": b.get("year"),
                     "rec_pub": b.get("publisher") or "", "src": b.get("src", ""),
                     "diffs": r.get("diffs", [])})
    print(json.dumps(rows, ensure_ascii=False, indent=2))

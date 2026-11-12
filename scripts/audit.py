#!/usr/bin/env python3
"""A-layer audit: internal consistency of footnotes / endnotes.

No network. Every finding is derived from the manuscript itself, so a hit here
is a fact about the text, not a guess about the world.

Design rule: report what the text contradicts, never what it merely fails to
match against an external index.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict

NOTE_HEAD = re.compile(r"^#{1,6}\s*(脚注|尾注|注释|Notes?|Footnotes?|Endnotes?)\s*$", re.I)
DEF = re.compile(r"^\[(\d+)\]\s*(.+)$")
MARKER = re.compile(r"\[(\d+)\]")
ESCAPED = re.compile(r"\\\[(\d+)\\\]")
ITAL = re.compile(r"\*(.+?)\*")
PAREN = re.compile(r"[(（]([^()（）]*)[)）]")
YEAR = re.compile(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)")
CJK = re.compile(r"[\u4e00-\u9fff]")
SEV = {"ERROR": "错误", "WARNING": "可疑", "INFO": "提示"}


def parse(text: str):
    lines = text.splitlines()
    head = next((i for i, ln in enumerate(lines) if NOTE_HEAD.match(ln.strip())), None)
    if head is None:
        sys.exit("找不到脚注区标题（如 `## 脚注`）")
    body = "\n".join(lines[:head])
    notes, cur = OrderedDict(), None
    for ln in lines[head + 1:]:
        m = DEF.match(ln.strip())
        if m:
            cur = int(m.group(1))
            notes[cur] = m.group(2).strip()
        elif cur and ln.strip() and not ln.startswith("#"):
            notes[cur] += " " + ln.strip()
    return body, notes


def markers(body: str) -> list[int]:
    """Backslash escapes must be removed before matching, otherwise the second
    marker in `\\[4\\]\\[5]` is swallowed by the trailing backslash."""
    clean = ESCAPED.sub(r"[\1]", body).replace("\\[", "[").replace("\\]", "]")
    return [int(x) for x in MARKER.findall(clean)]


def units(note: str) -> list[dict]:
    """Split a note into one record per italicised work.

    A note is prose, not a list: note [4] packs five works into one sentence.
    Splitting on 。 merges them; splitting per italic span does not."""
    hits = list(ITAL.finditer(note))
    out = []
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(note)
        post = note[h.end():end]
        pre = note[max(0, h.start() - 160):h.start()]
        # "Quoted Article Title," *Journal* Vol (Year): pages  -> italic is container
        q = re.search(r'[“"]([^”"]{4,140})[”"]\s*,?\s*$', pre)
        title = q.group(1).strip() if q else h.group(1).strip()
        container = h.group(1).strip() if q else ""
        place = pub = None
        for p in PAREN.findall(post):
            m = re.match(r"^\s*([^:：]+)[:：]\s*([^,，]+)[,，]\s*(\d{4})", p)
            if m:
                place, pub = m.group(1).strip(), m.group(2).strip()
                break
            m2 = re.search(r"([A-Z][\w&.\s]{2,}?(?:Press|Books|Blackwell|Vrin|Clarendon))\s*,\s*(\d{4})", p)
            if m2:
                pub = m2.group(1).strip()
                break
        ys = YEAR.findall(post)
        year = int(ys[0]) if ys else None
        kind = "article" if container else "book"
        if kind == "article":
            # An article is complete when volume and page range are present;
            # place/publisher is meaningless for it.
            complete = bool(re.search(r"\b\d+\s*\(", post)) and bool(re.search(r"\d+\s*[–—-]\s*\d+", post))
        else:
            complete = bool(place and pub)
        out.append({"title": title, "container": container, "place": place,
                    "publisher": pub, "year": year, "kind": kind,
                    "complete": complete, "is_full": bool(place and pub),
                    "raw": note[h.start():end].strip()})

    # Quoted article titles with no italic venue: a note of the form
    # Author, "Article Title", 2007 carries no italics at all, so the loop
    # above never sees it.
    for m in re.finditer(r'[“"]([^”"]{4,140})[”"]\s*[,，]\s*(\d{4})', note):
        # skip when the quote is the article title of "*Journal* Vol (Year)" --
        # that case is already handled above
        if re.match(r"\s*,?\s*\*", note[m.end():m.end() + 12]):
            continue
        out.append({"title": m.group(1).strip(), "container": "", "place": None,
                    "publisher": None, "year": int(m.group(2)), "kind": "article",
                    "complete": False, "is_full": False,
                    "raw": note[m.start():m.start() + 80]})
    return out


def work_key(m: dict) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", m["title"].lower())).strip()


def analyze(cited: list[int], notes: dict[int, str], body: str = "") -> dict:
    """Shared core. `cited` is the marker number sequence in reading order;
    `notes` maps note number to note text. Both text and .docx front-ends
    funnel through here so a fix only has to be made once."""
    escaped = [int(x) for x in ESCAPED.findall(body)]
    findings = []

    def add(sev, chk, msg, item=None, anchor=None):
        findings.append({"sev": sev, "check": chk, "msg": msg,
                         "item": item, "anchor": anchor})

    if escaped:
        add("ERROR", "转义残留",
            f"正文有 {len(escaped)} 个被转义的引注标记 `\\[{escaped[0]}\\]`，"
            f"导出后显示为字面量而非上标（共 {len(escaped)} 处）")

    orphan = [n for n in notes if n not in cited]
    missing = [n for n in cited if n not in notes]
    for n in missing:
        add("ERROR", "缺注释", f"正文引用 [{n}]，脚注区无对应条目", anchor=n)
    for n in orphan:
        add("ERROR", "孤儿注释", f"脚注 [{n}] 已给出，但正文从未引用该编号", anchor=n)

    order, seen = [], set()
    for n in cited:
        if n not in seen:
            seen.add(n)
            order.append(n)
    if order != sorted(order):
        add("WARNING", "编号顺序", f"按首次出现应编号 {sorted(order)}，实际为 {order}")

    for i in range(len(cited) - 1):
        if cited[i] == cited[i + 1]:
            add("WARNING", "重复标记", f"[{cited[i]}] 连续出现两次", anchor=cited[i])

    works: dict[str, list[tuple[int, dict]]] = OrderedDict()
    for n, raw in notes.items():
        for m in units(raw):
            works.setdefault(work_key(m), []).append((n, m))

    never_full = []
    for key, items in works.items():
        nums = [n for n, _ in items]
        by_note = dict(items)
        years = {m["year"] for _, m in items if m["year"]}
        if len(years) > 1:
            add("ERROR", "年份不一致",
                f"同一文献在不同脚注中年份不同：{sorted(years)}（脚注 {nums}）", key, anchor=nums[0])
        pubs = {(m["place"], m["publisher"]) for _, m in items if m["place"] and m["publisher"]}
        if len(pubs) > 1:
            add("ERROR", "出版项不一致",
                f"同一文献的出版地/出版社不一致：{sorted(pubs)}（脚注 {nums}）", key, anchor=nums[0])

        cited_nums = [n for n in order if n in nums]
        if not cited_nums:
            continue
        first = cited_nums[0]
        fulls = sorted(n for n in nums if by_note[n]["complete"])
        hidden = [n for n in fulls if n < first]
        if hidden and not by_note[first]["complete"]:
            add("ERROR", "全称位置错位",
                f"脚注 [{first}] 用简称引用，全称却写在脚注 [{hidden[0]}]，而该注未被正文引用；"
                f"应把全称移到首次引用处", key, anchor=first)
        later_full = [n for n in cited_nums[1:] if by_note[n]["complete"]]
        if by_note[first]["complete"] and later_full:
            add("WARNING", "重复全称",
                f"脚注 {later_full} 重复给出完整出版信息，后续应改用简称", key, anchor=later_full[0])
        m0 = items[0][1]
        if not fulls:
            if m0["kind"] == "book":
                never_full.append((nums[0], f"{m0['title']} {m0['year'] or ''}（注 {nums[0]}）"))
            else:
                add("WARNING", "文章信息不全",
                    f"脚注 {nums} 的期刊文章缺卷期或页码：{m0['title']}", key, anchor=nums[0])

    if never_full:
        add("WARNING", "未给全称",
            f"{len(never_full)} 种文献全文只以简略形式出现，从未给出完整出版地/出版社："
            + "；".join(t for _, t in never_full), anchor=never_full[0][0])

    for n, raw in notes.items():
        if re.search(r"\d+-\d+", raw):
            add("INFO", "连接号", f"脚注 [{n}] 页码范围用连字符，应改为 en dash（–）", anchor=n)
        if re.search(r"(?<![A-Za-z])(ibid|Ibid)\.", raw):
            add("INFO", "ibid 使用", f"脚注 [{n}] 使用 ibid.，Chicago 第 17 版已不推荐", anchor=n)

    return {"notes": len(notes), "cited": len(cited), "order": order,
            "orphans": orphan, "missing": missing, "findings": findings}


def audit(text: str) -> dict:
    body, notes = parse(text)
    return analyze(markers(body), notes, body)


def report(res: dict, path: str) -> str:
    rank = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    fs = sorted(res["findings"], key=lambda x: rank[x["sev"]])
    c = {k: sum(1 for f in fs if f["sev"] == k) for k in rank}
    out = [f"# 引用审计报告 · {path}", "",
           f"- 脚注条目 {res['notes']}　正文引注 {res['cited']} 处",
           f"- 错误 {c['ERROR']}　可疑 {c['WARNING']}　提示 {c['INFO']}",
           "- 检查层级：A 层（内部一致性，不依赖外部数据库）", "",
           "| 级别 | 检查项 | 说明 |", "|---|---|---|"]
    for f in fs:
        out.append(f"| {SEV[f['sev']]} | {f['check']} | {f['msg']} |")
    if not fs:
        out.append("| — | — | 未发现内部一致性问题 |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    res = audit(open(a.file, encoding="utf-8").read())
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    else:
        r = report(res, a.file)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(r)
        print(r)

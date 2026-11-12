#!/usr/bin/env python3
"""Front-end: audit a .docx and write findings back as native Word comments.

Anchoring rule: a finding about note N is commented on the note itself, in the
notes block at the end of the document. A finding about the body is commented
on the paragraph where it occurs. Findings that land on the same paragraph are
merged into one comment, so the margin does not get shredded.

The source file is never modified; output goes to a sibling copy.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audit import analyze, report

AUTHOR = "引用审计"


def flavored(p) -> str:
    """Word marks book titles with an italic run property, not with asterisks.
    The audit core reads `*Title*`, so the formatting has to be re-encoded into
    text here -- otherwise every title is invisible and every check silently
    passes. This was a real defect, not a hypothetical."""
    out = []
    for r in p.runs:
        t = r.text or ""
        if not t:
            continue
        if r.italic and t.strip():
            lead = t[: len(t) - len(t.lstrip())]
            trail = t[len(t.rstrip()):]
            out.append(f"{lead}*{t.strip()}*{trail}")
        else:
            out.append(t)
    return "".join(out)


def extract(doc) -> tuple[list[int], dict[int, str], dict[int, int], int]:
    """Return (cited numbers in order, note text, note -> paragraph index,
    index of the last body paragraph)."""
    paras = doc.paragraphs
    i = len(paras) - 1
    while i >= 0 and not paras[i].text.strip():
        i -= 1
    block = []
    while i >= 0:
        txt = flavored(paras[i])
        m = re.match(r"^(\d{1,3})(?=\D)", txt)
        if not m:
            break
        block.append((i, int(m.group(1)), txt[m.end():].strip()))
        i -= 1
    block.reverse()

    nums = [n for _, n, _ in block]
    if not nums or nums != list(range(1, len(nums) + 1)):
        raise SystemExit(
            "无法识别文末注释块。当前版本要求注释为文末连续段落，"
            f"每段以数字开头，编号从 1 连续递增。识别到的编号：{nums[:12]}")

    notes = {n: t for _, n, t in block}
    note_para = {n: idx for idx, n, _ in block}
    body_end = block[0][0] - 1

    cited, seen = [], set()
    for pi in range(0, body_end + 1):
        for r in paras[pi].runs:
            if not r.font.superscript:
                continue
            t = (r.text or "").strip()
            if not re.fullmatch(r"\d{1,3}(?:[,\s，、]*\d{1,3})*", t):
                continue
            for num in re.findall(r"\d+", t):
                cited.append(int(num))
    return cited, notes, note_para, body_end


def anchor(doc, para, text: str) -> None:
    c = doc.part.comments.add_comment(text, author=AUTHOR, initials="CA")
    cid = str(c.comment_id)
    p = para._p
    runs = p.findall(qn("w:r"))
    start = OxmlElement("w:commentRangeStart")
    start.set(qn("w:id"), cid)
    if runs:
        runs[0].addprevious(start)
    else:
        p.append(start)
    end = OxmlElement("w:commentRangeEnd")
    end.set(qn("w:id"), cid)
    if runs:
        runs[-1].addnext(end)
    else:
        start.addnext(end)
    ref_run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rstyle = OxmlElement("w:rStyle")
    rstyle.set(qn("w:val"), "CommentReference")
    rpr.append(rstyle)
    ref_run.append(rpr)
    ref = OxmlElement("w:commentReference")
    ref.set(qn("w:id"), cid)
    ref_run.append(ref)
    end.addnext(ref_run)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    if not a.file.lower().endswith(".docx"):
        raise SystemExit("需要 .docx 文件")

    doc = Document(a.file)
    cited, notes, note_para, body_end = extract(doc)
    res = analyze(cited, notes)

    print(report(res, os.path.basename(a.file)))

    groups: dict[int, list[str]] = {}
    for f in res["findings"]:
        n = f.get("anchor")
        if n in note_para:
            idx = note_para[n]
        else:
            idx = 0
        groups.setdefault(idx, []).append(f"【{f['sev']} · {f['check']}】{f['msg']}")

    for idx, msgs in sorted(groups.items()):
        anchor(doc, doc.paragraphs[idx], "\n".join(msgs))

    out = a.out or re.sub(r"\.docx$", ".audit.docx", a.file)
    doc.save(out)
    print(f"\n批注已写入：{out}（{len(groups)} 处，共 {len(res['findings'])} 条发现）")


if __name__ == "__main__":
    main()

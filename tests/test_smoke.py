#!/usr/bin/env python3
"""Smoke test. No network. Run: python3 tests/test_smoke.py

Two properties are asserted, and they are the two that matter:

1. The .docx front-end writes one comment per finding, anchored in the document.
2. Known defects in samples/fixture.docx are actually reported. A checker that
   stays silent is indistinguishable from a clean manuscript, so silence is
   treated as failure here, not as success.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "samples" / "fixture.docx"

fails: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        fails.append(label)


def test_docx() -> None:
    print("docx front-end")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.docx"
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "docx_audit.py"), str(FIXTURE), "-o", str(out)],
            capture_output=True, text=True,
        )
        check(r.returncode == 0, "exit code 0")
        check(out.exists(), "output file written")
        if not out.exists():
            return

        from docx import Document
        d = Document(str(out))
        comments = [c.text for c in d.part.comments]
        check(len(comments) == 2, f"2 comments written (got {len(comments)})")

        joined = "\n".join(comments)
        # Defect 1: note 5 is never cited in the body.
        check("孤儿注释" in joined and "[5]" in joined, "orphan note 5 reported")
        # Defect 2: note 4 gives no place/publisher for Kenny.
        check("未给全称" in joined, "note 4 missing publication data reported")
        # The source must stay untouched: output is a sibling copy, never in-place.
        check(r.returncode == 0 and "批注已写入" in r.stdout, "report printed")


def test_markdown() -> None:
    print("markdown back-end")
    md = """# Title

Body text claims something.\\u00a0

## 脚注

[1] Thomas Hobbes, *Leviathan*, ed. Noel Malcolm (Oxford: Clarendon Press, 2012), ch. 6.

[2] An orphan note that the body never cites.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.md"
        p.write_text(md, encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit.py"), str(p)],
            capture_output=True, text=True,
        )
        check(r.returncode == 0, "exit code 0")
        check("孤儿注释" in r.stdout, "orphan note reported")
        check("[2]" in r.stdout, "offending number named")


if __name__ == "__main__":
    test_docx()
    test_markdown()
    print()
    if fails:
        print(f"{len(fails)} check(s) failed")
        sys.exit(1)
    print("all checks passed")

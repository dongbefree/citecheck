#!/usr/bin/env python3
"""Regenerate samples/fixture.docx.

The fixture is a synthetic manuscript carrying exactly two known defects, so the
smoke test has something stable to assert against:

  defect 1  note 5 is orphaned — the body never cites it
  defect 2  note 4 gives no place or publisher, and is the only appearance of
            that work, so its full form is missing

References are invented. No real bibliography is used, which keeps the fixture
free of anyone's actual reading list.

Note the italic runs: Word marks book titles with run properties, not asterisks.
The fixture is built the same way a real manuscript is, so the parser's
`flavored()` path is exercised rather than bypassed.
"""
from pathlib import Path

from docx import Document

OUT = Path(__file__).resolve().parent.parent / "samples" / "fixture.docx"

BODY = [
    ("The argument turns on a claim about the body", "1"),
    (", and on a second claim about what a state is about", "2"),
    (". The remainder is methodological", "3"),
    (", and names the standard objection", "4"),
    (".", None),
]

NOTES = [
    ("1", [("A. N. Author, ", False), ("Studies in a Problem", True),
           (", ed. B. Editor (Oxford: Example Press, 2012), ch. 6.", False)]),
    ("2", [("C. D. Writer, ", False), ("A Second Book", True),
           (" (Cambridge: Example Press, 1997), 124\u2013157.", False)]),
    ("3", [("A methodological aside, cited once.", False)]),
    ("4", [("E. F. Critic, ", False), ("Form and Object", True),
           (", 1963, 188\u2013194.", False)]),
    ("5", [("G. H. Author, ", False), ("A Fifth Book", True),
           (" (Oxford: Example Press, 1984).", False)]),
]


def main() -> None:
    doc = Document()
    p = doc.add_paragraph()
    for text, marker in BODY:
        p.add_run(text)
        if marker:
            p.add_run(marker).font.superscript = True

    for num, parts in NOTES:
        q = doc.add_paragraph(num)
        for text, italic in parts:
            q.add_run(text).italic = italic

    doc.save(str(OUT))
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()

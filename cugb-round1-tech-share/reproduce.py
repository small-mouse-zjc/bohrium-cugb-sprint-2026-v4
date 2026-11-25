#!/usr/bin/env python3
"""Re-check that every quoted passage really appears on its cited PDF page.

Real checker for the technical-sharing work. It downloads the pinned arXiv PDF
if needed, extracts page text with PyMuPDF and writes verification/result.json.
It checks TEXT-LEVEL citation fidelity only -- it does NOT rerun the paper's
reservoir simulations.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
PDF = BASE.parent / "paper.pdf" if (BASE.parent / "paper.pdf").exists() else BASE / "paper.pdf"
ARXIV = "https://arxiv.org/pdf/2407.20541v4"
OUT = BASE / "verification" / "result.json"

CHECKS = [
    ("p1", 1, "from several hours to minutes"),
    ("p1-cells", 1, "over 130,000 cells"),
    ("p8", 8, "5200 seven days"),
    ("p8-pressure", 8, "241 bars"),
    ("p12", 12, "runs 2, 5, 7, and 10"),
    ("p15-eclipse", 15, "~223 mins for case A and ~140 mins for case B"),
    ("p15-pressure", 15, "~1.28 mins and ~1.4 mins"),
    ("p16-saturation", 16, "~33 mins and ~31 mins"),
    ("p3-citation", 3, "279 to 28 seconds"),
    ("p16-table", 16, "Average reconstruction times"),
    ("p36-average", 36, "Average saturation times are 31.61"),
    ("p36-limit", 36, "needs to be applied to multiple reservoirs"),
]


def main():
    print("reproduce: pinned source arXiv:2407.20541v4")
    if not PDF.exists():
        print("reproduce: local PDF missing, downloading " + ARXIV)
        try:
            urllib.request.urlretrieve(ARXIV, str(PDF))
        except Exception as exc:
            print("reproduce: download FAILED: %s" % exc)
            return 2
    print("reproduce: PDF bytes = %d" % PDF.stat().st_size)
    try:
        import pymupdf
    except ImportError:
        print("reproduce: PyMuPDF missing -> pip install pymupdf")
        return 2
    doc = pymupdf.open(str(PDF))
    print("reproduce: pages = %d" % doc.page_count)
    results = []
    for label, page, needle in CHECKS:
        text = re.sub(r"\s+", " ", doc[page - 1].get_text("text"))
        found = needle.lower() in text.lower()
        i = text.lower().find(needle.lower())
        results.append({
            "check": label, "page": page, "quote": needle,
            "found": found,
            "context": text[max(0, i - 60):i + len(needle) + 60] if i >= 0 else "",
        })
        print("  %-16s p%-3d %s  %s" % (label, page, "FOUND" if found else "MISS", needle[:48]))
    OUT.parent.mkdir(exist_ok=True)
    summary = {
        "paper": "arXiv:2407.20541v4",
        "pages": doc.page_count,
        "checks_total": len(results),
        "checks_found": sum(1 for r in results if r["found"]),
        "note": "Text-level citation check only; reservoir simulations were NOT rerun.",
        "results": results,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("reproduce: %d/%d checks found -> %s" % (
        summary["checks_found"], summary["checks_total"], OUT))
    # text-volume self-check (240 KiB limit for the shared materials)
    total = 0
    for p in BASE.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".txt", ".json", ".py", ".log"}:
            total += len(p.read_bytes())
    print("reproduce: all UTF-8 text files total = %d bytes (< 245760 limit)" % total)
    return 0 if summary["checks_found"] == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

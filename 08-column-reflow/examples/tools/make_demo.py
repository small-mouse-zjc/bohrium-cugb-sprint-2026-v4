#!/usr/bin/env python3
"""生成"已知真值"的双栏演示 PDF，用于验证阅读顺序算法。

  python make_demo.py --out /tmp/demo
产出 demo.pdf 与 truth.json（真值顺序）；文档内容为构造文本，无科学数据。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

W, H = 595, 842
TEXT = ("Left-column paragraph {n}. It describes step {n} of the demo procedure and keeps numbers like {n}2 m. "
        "The paragraph ends with a full stop so it can be split cleanly.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    truth = []

    def page_new():
        return doc.new_page(width=W, height=H)

    def put(rect, text, size=9):
        page.insert_textbox(fitz.Rect(*rect), text, fontsize=size, fontname="helv")

    # 第 1 页
    page = page_new()
    put((50, 20, 545, 40), "Demo Journal of Reflow 2026 - preprint", size=8)
    put((50, 786, 545, 826), "Demo preprint, not for citation", size=8)
    put((50, 50, 545, 80), "[[T1]] A Two-Column Demo Paper", size=14)
    put((50, 90, 545, 140), "[[A1]] Abstract. This demo document has a fixed, known reading order so that the "
                             "reflow algorithm can be checked against ground truth rather than opinion.", size=9)
    truth += ["T1", "A1"]

    y = 160
    for i in range(1, 6):
        put((50, y, 275, y + 72), f"[[P{i}]] " + TEXT.format(n=i), size=9)
        truth.append(f"P{i}")
        y += 82
    y = 160
    for i in range(6, 11):
        put((305, y, 545, y + 72), f"[[P{i}]] " + TEXT.format(n=i), size=9)
        truth.append(f"P{i}")
        y += 82
    put((50, 690, 545, 730), "[[F1]] Figure 1. A cross-column caption that must stay below both columns.", size=9)
    truth.append("F1")

    # 第 2 页
    page = page_new()
    put((50, 20, 545, 40), "Demo Journal of Reflow 2026 - preprint", size=8)
    put((50, 786, 545, 826), "Demo preprint, not for citation", size=8)
    y = 60
    for i in range(11, 16):
        put((50, y, 275, y + 72), f"[[P{i}]] " + TEXT.format(n=i), size=9)
        truth.append(f"P{i}")
        y += 82
    y = 60
    for i in range(16, 21):
        put((305, y, 545, y + 72), f"[[P{i}]] " + TEXT.format(n=i), size=9)
        truth.append(f"P{i}")
        y += 82


    # 第 3 页：不规则双栏（左栏短、右栏长、半页宽块插在栏中、跨块断词）
    page = page_new()
    put((50, 20, 545, 40), "Demo Journal of Reflow 2026 - preprint", size=8)
    put((50, 786, 545, 826), "Demo preprint, not for citation", size=8)
    put((50, 55, 275, 115), "[[L1]] Left column starts here and is shorter than the right column.", size=9)
    put((50, 130, 275, 190), "[[L2]] A hyphenated word is split across blocks: micro-", size=9)
    put((50, 152, 275, 212), "[[L3]] structure continues in the next block.", size=9)
    put((305, 55, 545, 115), "[[Q1]] Right column block one continues normally.", size=9)
    put((305, 130, 545, 190), "[[Q2]] Right column block two continues normally.", size=9)
    put((305, 205, 545, 265), "[[Q3]] Right column block three continues normally.", size=9)
    put((50, 285, 545, 320), "[[G1]] Table 2. A wide cross-column block inserted inside the two columns: it spans the full text width and must be read at its own vertical position, after the left column and before the remaining right-column blocks.", size=9)
    put((305, 340, 545, 400), "[[Q4]] Right column resumes below the inserted block.", size=9)
    put((305, 415, 545, 475), "[[Q5]] Right column block five continues normally.", size=9)
    put((305, 490, 545, 550), "[[Q6]] Right column block six ends the page.", size=9)
    truth += ["L1", "L2", "L3", "Q1", "Q2", "Q3", "G1", "Q4", "Q5", "Q6"]
    pdf = out / "demo.pdf"
    doc.save(str(pdf))
    (out / "truth.json").write_text(json.dumps({"order": truth, "note": "构造文档，真值由生成顺序确定"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pdf": str(pdf), "blocks": len(truth)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

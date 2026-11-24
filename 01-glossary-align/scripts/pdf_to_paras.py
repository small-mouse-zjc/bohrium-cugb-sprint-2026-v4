#!/usr/bin/env python3
"""把 PDF / 纯文本切成带稳定编号的段落。

用法:
  python pdf_to_paras.py --in paper.pdf --out work/paras.jsonl
  python pdf_to_paras.py --in paper.txt --out work/paras.jsonl
  python pdf_to_paras.py --in paper.pdf --check-order

输出:
  <out>           每行一个段落 {"id","page","col","bbox","section","text","chars"}
  <out>.meta.json 文档级元信息（页数、每页字符数、丢弃的页眉页脚、警告、状态）
  <out>.md         人读版，段落前带 [P0001] 与页码，便于模型逐段翻译

设计要点（与"看起来像全文"的整页文本不同）:
  1. 先按版面把块分成 通栏/左栏/右栏，再按"横向带 + 栏内自上而下"排序；
  2. 页眉页脚按位置 + 跨页重复率剔除，不混进正文；
  3. 段落编号一旦生成即固定，翻译后不允许重排；
  4. 无文字层时明确置 status=no_text_layer，不用空白冒充正文。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path


# ---------- 版面块 ----------

def _clean_line(s: str) -> str:
    s = s.replace("\u00ad", "")
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def _dehyphenate(text: str) -> str:
    return re.sub(r"(\w)-\s*\n?\s*(\w)", r"\1\2", text)


def _split_columns(blocks, page_w: float):
    """把一页的块分成 span / left / right。无可靠双栏证据时全部按 span 处理。"""
    if not blocks:
        return [], [], []
    # 双栏判据: 至少 2 个块中心在左半且 2 个块中心在右半, 且两栏 x 区间几乎不重叠
    left = [b for b in blocks if b["x1"] <= page_w * 0.52]
    right = [b for b in blocks if b["x0"] >= page_w * 0.46]
    span = [b for b in blocks if b not in left and b not in right]
    if len(left) >= 2 and len(right) >= 2:
        return span, left, right
    return blocks, [], []


def _page_order(blocks, page_w: float):
    """返回该页按阅读顺序排列的块，以及每块的栏标记。"""
    span, left, right = _split_columns(blocks, page_w)
    if not left and not right:
        return [(b, "span") for b in sorted(blocks, key=lambda x: (x["y0"], x["x0"]))]

    ordered = []
    # 通栏块（标题、跨栏图、宽表）按 y 切成横向带；每条带内先左栏后右栏
    spans = sorted(span, key=lambda x: x["y0"])
    bands = []
    prev_y = -1e9
    for s in spans:
        bands.append((prev_y, s["y0"]))
        prev_y = s["y1"]
    bands.append((prev_y, 1e9))
    for (y_from, y_to) in bands:
        ls = [b for b in left if y_from <= b["y0"] < y_to]
        rs = [b for b in right if y_from <= b["y0"] < y_to]
        for b in sorted(ls, key=lambda x: (x["y0"], x["x0"])):
            ordered.append((b, "L"))
        for b in sorted(rs, key=lambda x: (x["y0"], x["x0"])):
            ordered.append((b, "R"))
        for b in sorted(spans, key=lambda x: x["y0"]):
            if y_from <= b["y0"] < y_to:
                ordered.append((b, "span"))
    return ordered


def _is_heading(text: str, size: float, median_size: float) -> bool:
    if not text or len(text) > 90:
        return False
    if text.endswith((".", ",", ";", ":", "。", "，")):
        return False
    if size >= max(median_size * 1.15, median_size + 1.0):
        return True
    return bool(re.match(r"^(\d+(\.\d+)*)\s+[A-Z\u4e00-\u9fa5]", text))


# ---------- PDF ----------

def extract_pdf(path: Path):
    try:
        import fitz  # PyMuPDF
    except Exception:
        return extract_pdf_fallback(path)

    doc = fitz.open(str(path))
    pages = []
    median_sizes = []
    for page in doc:
        raw = page.get_text("dict")
        sizes = [s["size"] for b in raw.get("blocks", []) if b.get("type") == 0
                 for l in b.get("lines", []) for s in l.get("spans", []) if s.get("text", "").strip()]
        if sizes:
            median_sizes.append(statistics.median(sizes))
    doc_median = statistics.median(median_sizes) if median_sizes else 10.0

    for pno, page in enumerate(doc, start=1):
        raw = page.get_text("dict")
        pw, ph = page.rect.width, page.rect.height
        blocks = []
        chars = 0
        for b in raw.get("blocks", []):
            if b.get("type") != 0:
                continue
            lines, max_size = [], 0.0
            for line in b.get("lines", []):
                txt = "".join(s.get("text", "") for s in line.get("spans", []))
                if not txt.strip():
                    continue
                lines.append(_clean_line(txt))
                for s in line.get("spans", []):
                    max_size = max(max_size, float(s.get("size", 0)))
            if not lines:
                continue
            text = _dehyphenate(" ".join(lines))
            text = _clean_line(text)
            if not text:
                continue
            chars += len(text)
            x0, y0, x1, y1 = b["bbox"]
            blocks.append({"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                           "size": max_size, "lines": len(lines)})
        pages.append({"no": pno, "w": pw, "h": ph, "blocks": blocks, "chars": chars})

    # 页眉页脚：位置在上下 8% 内，且跨页重复（归一化后）
    def norm(t: str) -> str:
        return re.sub(r"\s+", " ", t).strip().lower()

    freq = {}
    for p in pages:
        for b in p["blocks"]:
            if b["y1"] <= p["h"] * 0.08 or b["y0"] >= p["h"] * 0.92:
                k = norm(b["text"])
                if len(k) <= 120:
                    freq[k] = freq.get(k, 0) + 1

    dropped = []
    kept_pages = []
    for p in pages:
        kept = []
        for b in p["blocks"]:
            if (b["y1"] <= p["h"] * 0.08 or b["y0"] >= p["h"] * 0.92) and freq.get(norm(b["text"]), 0) >= 2:
                dropped.append({"page": p["no"], "text": b["text"][:80]})
                continue
            kept.append(b)
        kept_pages.append(dict(p, blocks=kept))

    paras = []
    cur_section = ""
    for p in kept_pages:
        ordered = _page_order(p["blocks"], p["w"])
        last = None
        for b, col in ordered:
            text = b["text"]
            is_head = _is_heading(text, b["size"], doc_median)
            if is_head:
                cur_section = text
                # 标题也作为可翻译段落输出（SKILL 要求标题与正文一视同仁），用 H 前缀编号，不打乱正文 P 编号
                paras.append({"text": text, "col": col, "page": p["no"], "y1": b["y1"],
                              "bbox": [round(b["x0"], 1), round(b["y0"], 1), round(b["x1"], 1), round(b["y1"], 1)],
                              "section": text, "type": "heading"})
                continue
            # 同栏续段合并：上一块未以句末标点结尾、本块小写开头、垂直间距小
            if (last is not None and last["col"] == col and not is_head
                    and not re.search(r"[.!?。！？:;]\s*$", last["text"])
                    and re.match(r"[a-z\u4e00-\u9fa5]", text)
                    and 0 <= b["y0"] - last["y1"] <= max(12, doc_median * 1.6)):
                last["text"] = _clean_line(last["text"] + " " + text)
                last["y1"] = b["y1"]
                continue
            last = {"text": text, "col": col, "page": p["no"], "y1": b["y1"],
                    "bbox": [round(b["x0"], 1), round(b["y0"], 1), round(b["x1"], 1), round(b["y1"], 1)],
                    "section": cur_section}
            paras.append(last)

    out, np_, nh = [], 0, 0
    for p in paras:
        if p.get("type") == "heading":
            nh += 1
            pid = f"H{nh:03d}"
        else:
            np_ += 1
            pid = f"P{np_:04d}"
        out.append({"id": pid, "type": p.get("type", "body"), "page": p["page"], "col": p["col"],
                    "bbox": p["bbox"], "section": p["section"], "text": p["text"],
                    "chars": len(p["text"])})
    meta = {"source": str(path), "pages": len(pages), "chars_per_page": [p["chars"] for p in pages],
            "dropped_headers_footers": dropped, "warnings": [], "status": "ok"}
    if sum(p["chars"] for p in pages) < 50 * len(pages):
        meta["status"] = "no_text_layer"
        meta["warnings"].append("每页平均字符数过低，疑似扫描件/无文字层，需 OCR")
    return out, meta


def extract_pdf_fallback(path: Path):
    """没有 PyMuPDF 时用 pypdf 取文本；无法判断栏位，明确告警。"""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    out, chars = [], []
    n = 1
    for pno, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        chars.append(len(text))
        for chunk in re.split(r"\n\s*\n", text):
            chunk = _clean_line(_dehyphenate(chunk))
            if len(chunk) < 2:
                continue
            out.append({"id": f"P{n:04d}", "page": pno, "col": "unknown", "bbox": None,
                        "section": "", "text": chunk, "chars": len(chunk)})
            n += 1
    meta = {"source": str(path), "pages": len(reader.pages), "chars_per_page": chars,
            "dropped_headers_footers": [], "status": "ok",
            "warnings": ["未安装 PyMuPDF，已按页面文本流输出，栏位未知，存在串栏风险"]}
    if sum(chars) < 50 * max(1, len(reader.pages)):
        meta["status"] = "no_text_layer"
    return out, meta


# ---------- 纯文本 ----------

def extract_txt(path: Path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    chunks = re.split(r"\n\s*\n", raw)
    out, section, page = [], "", 1
    nh = 0
    for c in chunks:
        c = _clean_line(c)
        if not c:
            continue
        if len(c) < 90 and not c.endswith((".", "。", "!", "?")) and re.match(r"^(?:\d+(?:\.\d+)*\s+)?[A-Z\u4e00-\u9fa5]", c):
            section = c
            nh += 1
            out.append({"id": f"H{nh:03d}", "type": "heading", "page": page, "col": "unknown", "bbox": None,
                        "section": section, "text": c, "chars": len(c)})
            continue
        if "\f" in c:
            page += c.count("\f")
            c = c.replace("\f", " ")
        out.append({"id": f"P{len([x for x in out if x['type']=='body'])+1:04d}", "type": "body", "page": page,
                    "col": "unknown", "bbox": None, "section": section, "text": c, "chars": len(c)})
    meta = {"source": str(path), "pages": page, "chars_per_page": [len(raw)], "dropped_headers_footers": [],
            "status": "ok", "warnings": ["纯文本输入无版面信息，页码为估算"]}
    return out, meta


def check_order(paras, meta):
    """粗检串栏：相邻段落若左栏末尾接右栏开头，常见症状是句子在栏间断开。"""
    warn = list(meta.get("warnings", []))
    for a, b in zip(paras, paras[1:]):
        if a["col"] == "L" and b["col"] == "R" and a["page"] == b["page"]:
            if not re.search(r"[.!?。！？]\s*$", a["text"]):
                warn.append(f"{a['id']}->{b['id']} 左栏末尾无句末标点即转右栏，疑似串栏")
    return warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--check-order", action="store_true")
    args = ap.parse_args()

    p = Path(args.inp)
    if p.suffix.lower() == ".pdf":
        paras, meta = extract_pdf(p)
    elif p.suffix.lower() in (".txt", ".md"):
        paras, meta = extract_txt(p)
    else:
        print(json.dumps({"status": "unsupported_input", "suffix": p.suffix}, ensure_ascii=False))
        sys.exit(2)

    if args.check_order:
        print(json.dumps({"warnings": check_order(paras, meta), "pages": meta["pages"]}, ensure_ascii=False, indent=2))
        return

    out = Path(args.out or "paras.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in paras:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta_path = Path(str(out) + ".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    md = Path(str(out) + ".md")
    with md.open("w", encoding="utf-8") as f:
        for r in paras:
            f.write(f"[{r['id']}] p.{r['page']} {r['col']} §{r['section']}\n{r['text']}\n\n")
    print(json.dumps({"status": meta["status"], "paragraphs": len(paras), "pages": meta["pages"],
                      "out": str(out), "warnings": meta["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

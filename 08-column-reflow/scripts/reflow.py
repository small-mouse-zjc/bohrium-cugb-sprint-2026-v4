#!/usr/bin/env python3
"""双栏/多栏阅读顺序重排。

  python reflow.py --pdf paper.pdf --out out --audit
  python reflow.py --pdf paper.pdf --out out --baseline      # 朴素 y→x 顺序，用于对照

输出 paragraphs.jsonl / reflow.json / reflow.md
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


def clean(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()


def join_lines(lines):
    buf = ""
    for ln in lines:
        ln = ln.rstrip()
        if not buf:
            buf = ln
        elif buf.endswith("-") and re.search(r"[A-Za-z]-$", buf):
            buf = buf[:-1] + ln.lstrip()
        else:
            buf = buf + " " + ln.lstrip()
    return clean(buf)


PAGE_NUM_RE = re.compile(r"^(page\s*)?\d+(\s*(of|/)\s*\d+)?$", re.I)


def band_key(text: str) -> str:
    """把页码/卷期这类"每页只差一个数字"的文本归一成同一键。"""
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    return re.sub(r"\d+", "#", t)


def is_band_block(b, H) -> bool:
    return b["y1"] <= H * 0.07 or b["y0"] >= H * 0.92


def drop_band_blocks(pages):
    """剔除页眉页脚：逐字重复 / 页码形态 / 跨页仅数字不同的短行。"""
    freq, nfreq = {}, {}
    for p in pages:
        med = statistics.median([b["size"] for b in p["blocks"] if b["size"]]) if p["blocks"] else 10
        p["med_size"] = med
        for b in p["blocks"]:
            if is_band_block(b, p["H"]):
                k = re.sub(r"\s+", " ", b["text"]).lower()
                freq[k] = freq.get(k, 0) + 1
                nk = band_key(b["text"])
                nfreq[nk] = nfreq.get(nk, 0) + 1
    dropped = []
    for pno, p in enumerate(pages, start=1):
        kept = []
        for b in p["blocks"]:
            if is_band_block(b, p["H"]):
                txt = re.sub(r"\s+", " ", b["text"]).strip()
                k = txt.lower()
                small = b["size"] <= p["med_size"] * 0.92
                reason = None
                if freq.get(k, 0) >= 2:
                    reason = "跨页逐字重复"
                elif PAGE_NUM_RE.match(txt):
                    reason = "页码形态"
                elif len(txt) <= 80 and nfreq.get(band_key(txt), 0) >= 2 and small:
                    reason = "跨页仅数字不同（running head/页码）"
                if reason:
                    dropped.append({"page": pno, "text": txt[:60], "reason": reason})
                    continue
            kept.append(b)
        p["blocks"] = kept
    return dropped


def mark_notes(pages):
    """边注/脚注：窄块贴左右页边，标 role=note，不进正文阅读序列。"""
    notes = []
    for pno, p in enumerate(pages, start=1):
        for b in p["blocks"]:
            w = b["x1"] - b["x0"]
            if w <= 0.3 * p["W"] and (b["x1"] <= 0.2 * p["W"] or b["x0"] >= 0.8 * p["W"]):
                b["role"] = "note"
                notes.append({"page": pno, "text": b["text"][:60],
                              "bbox": [round(b["x0"], 1), round(b["y0"], 1), round(b["x1"], 1), round(b["y1"], 1)]})
    return notes


def read_blocks(page):
    d = page.get_text("dict")
    out = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        lines = [clean("".join(s.get("text", "") for s in l.get("spans", []))) for l in b.get("lines", [])]
        lines = [l for l in lines if l]
        if not lines:
            continue
        text = join_lines(lines)
        if not text:
            continue
        x0, y0, x1, y1 = b["bbox"]
        size = max((s.get("size", 0) for l in b.get("lines", []) for s in l.get("spans", [])), default=0)
        out.append({"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "size": size})
    return out


def classify(blocks, W):
    left_max = W * 0.55
    right_min = W * 0.45
    cols, spans = [], []
    for b in blocks:
        if (b["x1"] - b["x0"]) > 0.6 * W or (b["x0"] < right_min and b["x1"] > left_max):
            spans.append(b)
        else:
            cols.append(b)
    if len(cols) < 4:
        return [], blocks, 1
    xs = sorted(b["x0"] for b in cols)
    starts = [xs[0]]
    for x in xs[1:]:
        if x - starts[-1] > 0.12 * W:
            starts.append(x)
    starts.sort()
    for b in cols:
        b["col"] = max(i for i, s in enumerate(starts) if b["x0"] >= s - 2)
    return spans, cols, len(starts)


def page_order(blocks, W):
    spans, cols, ncol = classify(blocks, W)
    if not spans and not cols:
        return []
    ordered = []
    spans_sorted = sorted(spans, key=lambda b: (b["y0"], b["x0"]))
    prev = -1e9
    for s in spans_sorted:
        band = [b for b in cols if prev <= b["y0"] < s["y0"]]
        for i in range(ncol):
            ordered += sorted([b for b in band if b.get("col") == i], key=lambda b: b["y0"])
        ordered.append(s)
        prev = s["y1"]
    band = [b for b in cols if b["y0"] >= prev]
    for i in range(ncol):
        ordered += sorted([b for b in band if b.get("col") == i], key=lambda b: b["y0"])
    return ordered


def naive_order(blocks):
    return sorted(blocks, key=lambda b: (round(b["y0"], 1), b["x0"]))


def merge_paragraphs(seq):
    out = []
    for b in seq:
        if out:
            p = out[-1]
            same_col = p.get("col") == b.get("col")
            gap = b["y0"] - p["y1"]
            prev_open = not re.search(r"[.!?。！？:;]\s*$", p["text"])
            start_lower = re.match(r"[a-z(]", b["text"]) is not None
            if same_col and prev_open and start_lower and gap <= max(12, 1.6 * (b["size"] or 10)):
                p["text"] = clean(p["text"] + " " + b["text"])
                p["y1"] = b["y1"]
                p["x1"] = max(p["x1"], b["x1"])
                continue
        out.append(dict(b))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()

    import fitz
    doc = fitz.open(a.pdf)
    pages = []
    for page in doc:
        W, H = page.rect.width, page.rect.height
        pages.append({"W": W, "H": H, "blocks": read_blocks(page)})

    # 页眉页脚：逐字重复 + 页码形态 + 跨页仅数字不同（页码/running head）
    dropped = drop_band_blocks(pages)
    # 边注/脚注：贴页边的窄块标 note，不混入正文
    notes = mark_notes(pages)

    paras, layout = [], 1
    for pno, p in enumerate(pages, start=1):
        body = [b for b in p["blocks"] if b.get("role") != "note"]
        if a.baseline:
            seq = naive_order(body)
            for b in seq:
                b.setdefault("col", "?")
            nl = 1
        else:
            seq = page_order(body, p["W"])
            _, cols, nl = classify(body, p["W"])
            if nl > 1 and layout == 1:
                layout = nl
            if not seq:
                seq = naive_order(body)
        for b in merge_paragraphs(seq):
            paras.append({"id": f"P{len(paras)+1:04d}", "page": pno, "col": b.get("col", "span"),
                          "bbox": [round(b["x0"], 1), round(b["y0"], 1), round(b["x1"], 1), round(b["y1"], 1)],
                          "text": b["text"]})
        for b in [x for x in p["blocks"] if x.get("role") == "note"]:
            paras.append({"id": f"P{len(paras)+1:04d}", "page": pno, "col": "note", "role": "note",
                          "bbox": [round(b["x0"], 1), round(b["y0"], 1), round(b["x1"], 1), round(b["y1"], 1)],
                          "text": b["text"]})
    for i, r in enumerate(paras):
        r["order_index"] = i

    # 跨页续接：上页末段无句末标点、下页首段小写开头 → 记 continues_from
    continues = []
    body_paras = [r for r in paras if not r.get("role")]
    for a1, b1 in zip(body_paras, body_paras[1:]):
        if a1["page"] == b1["page"]:
            continue
        if not re.search(r"[.!?。！？]\s*$", a1["text"]) and re.match(r"[a-z(]", b1["text"]):
            b1["continues_from"] = a1["id"]
            continues.append({"from": a1["id"], "to": b1["id"], "reason": "上页末段无句末标点、下页小写开头"})

    suspicious = []
    for a1, b1 in zip(paras, paras[1:]):
        if a1["page"] != b1["page"] or isinstance(a1["col"], str) or isinstance(b1["col"], str):
            continue
        if a1["col"] < b1["col"] and not re.search(r"[.!?。！？]\s*$", a1["text"]):
            suspicious.append({"from": a1["id"], "to": b1["id"], "reason": "左栏末尾无句末标点即转右栏"})

    info = {"pdf": Path(a.pdf).name, "pages": len(pages), "paragraphs": len(paras),
            "layout": "single" if layout == 1 else f"{layout}-column",
            "dropped_headers_footers": dropped, "suspicious": suspicious,
            "note_blocks": notes, "continues": continues,
            "mode": "baseline" if a.baseline else "reflow",
            "chars": sum(len(r["text"]) for r in paras)}

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "paragraphs.jsonl").open("w", encoding="utf-8") as f:
        for r in paras:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "reflow.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    md = "\n\n".join(f"[{r['id']}] p.{r['page']} {r['col']}\n{r['text']}" for r in paras)
    (out / "reflow.md").write_text(md + "\n", encoding="utf-8")
    print(json.dumps({"layout": info["layout"], "pages": info["pages"], "paragraphs": len(paras),
                      "dropped": len(dropped), "suspicious": len(suspicious), "mode": info["mode"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

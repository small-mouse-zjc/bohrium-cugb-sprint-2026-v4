#!/usr/bin/env python3
"""06 输入解析：把 case.json 变成带偏移的文档（章节 / 段落 / 页码）。

设计原则：所有偏移都是从真实输入字符串上算出来的，笔记的锚点因此可以被
audit.py 用 `text[start:end]` 反查；解析失败不猜内容，只记 warnings。
"""
import json
import re

KNOWN_HEAD = {
    "abstract", "introduction", "related work", "background", "motivation",
    "materials and methods", "methods", "method", "experimental", "experiments",
    "results", "results and discussion", "discussion", "conclusions", "conclusion",
    "limitations", "future work", "references", "acknowledgements", "appendix",
}
NUM_HEAD = re.compile(r"^\s*(\d+(?:\.\d+)*)[\.\)]?\s+([^\n]{1,70})$")
PLAIN_HEAD = re.compile(r"^\s*([A-Z][A-Za-z][A-Za-z \-/&]{2,60})\s*$")


def _paras(text, base):
    """在 text 上切段落，返回 [(para_text, start, end)]，start/end 为全局偏移。"""
    spans = []
    for m in re.finditer(r"[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*", text):
        s, e = m.start(), m.end()
        seg = m.group(0)
        if not seg.strip():
            continue
        spans.append((seg.strip(), base + s + (len(seg) - len(seg.lstrip())), base + e))
    return spans


def _heading_of(line):
    raw = line.strip()
    if not raw or len(raw) > 72:
        return None
    m = NUM_HEAD.match(raw)
    if m and not raw.rstrip().endswith("."):
        return raw
    norm = re.sub(r"[^a-z ]", "", raw.lower()).strip()
    if norm in KNOWN_HEAD and (raw.isupper() or raw.istitle() or raw[0].isupper()):
        return raw
    if PLAIN_HEAD.match(raw) and raw.isupper() and len(raw.split()) <= 6:
        return raw
    return None


def detect_sections(raw):
    """无 sections 字段时，按行检测标题；检测不到就整篇当一节。"""
    lines, out, cur = raw.split("\n"), [], None
    pos = 0
    offsets = []
    for ln in lines:
        offsets.append((pos, pos + len(ln)))
        pos += len(ln) + 1
    heads = []
    for i, ln in enumerate(lines):
        h = _heading_of(ln)
        if h:
            heads.append((i, h))
    if not heads:
        return [(None, raw)], "no_section_headings"
    blocks = []
    for k, (i, h) in enumerate(heads):
        start_line = i + 1
        end_line = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = "\n".join(lines[start_line:end_line]).strip()
        blocks.append((h, body))
    pre = "\n".join(lines[:heads[0][0]]).strip()
    if pre:
        blocks.insert(0, (None, pre))
    return blocks, None


def unwrap(body: str) -> str:
    r"""把 PDF 抽取常见的"句中断行"归一成空格，只保留空行作为段落分隔。

    pdftotext 产出的正文几乎每行都硬换行；notes.py 的切句器是 `[^\n]`，句子被
    换行切断后只抽出后半截，前半截（常含 12 MPa 这类数据）会被静默丢掉。归一
    之后 doc["text"] 内部不再有横跨句子的 \n，text[span]==quote 的不变量不变。
    """
    chunks = re.split(r"\n[ \t]*\n", body or "")
    out = []
    for ch in chunks:
        lines = [ln.strip() for ln in ch.split("\n")]
        joined = " ".join(ln for ln in lines if ln)
        if joined:
            out.append(joined)
    return "\n\n".join(out)


def build_doc(case):
    """返回 doc：{text, sections:[{index,heading,start,end,page}], paras:[...], warnings}"""
    warns = []
    blocks, page_map = [], {}
    if isinstance(case, dict) and isinstance(case.get("sections"), list) and case["sections"]:
        for s in case["sections"]:
            if isinstance(s, dict):
                h = str(s.get("heading") or s.get("title") or s.get("name") or "")
                body = s.get("text") or s.get("content") or ""
                if not body and isinstance(s.get("paragraphs"), list):
                    # 列表里一项就是一段：必须用空行连接，否则经 unwrap() 后会被折成一段，
                    # ¶ 段序锚点整体失准（¶ 序号全错、按段落定位证据退化成整节）
                    body = "\n\n".join(str(p) for p in s["paragraphs"])
                pg = s.get("page")
            else:
                h, body, pg = "", str(s), None
            blocks.append((h or None, str(body), pg))
    else:
        raw = ""
        pages = None
        if isinstance(case, dict):
            raw = str(case.get("text") or case.get("full_text") or case.get("manuscript") or "")
            pages = case.get("pages")
        # pages 形态：按页切块并把页码带下去（旧实现算出 page_map 却从没落到 section/para，
        # 锚点里永远没有 p.N，页码锚定形同虚设）
        if not raw and isinstance(pages, list) and pages:
            for p in pages:
                if isinstance(p, dict):
                    ptxt, pg = str(p.get("text", "")), p.get("page")
                else:
                    ptxt, pg = str(p), None
                if not ptxt.strip():
                    continue
                pb, w = detect_sections(ptxt)
                if w:
                    warns.append({"issue": w, "detail": "该页未检测到章节标题，整页作为单节处理"})
                for h, b in pb:
                    blocks.append((h, b, pg))
        if raw:
            blocks, w = detect_sections(raw)
            blocks = [(h, b, None) for h, b in blocks]
            if w:
                warns.append({"issue": w, "detail": "未检测到章节标题，整篇作为单节处理，章节对齐只能做到全篇级"})
        elif not blocks:
            blocks = []

    text, sections, paras = "", [], []
    for h, body, pg in blocks:
        body = unwrap(body.strip())
        if not body and not h:
            continue
        head_txt = (h + "\n") if h else ""
        if text:
            text += "\n\n"
        s_start = len(text)
        text += head_txt + body
        s_end = len(text)
        sections.append({"index": len(sections), "heading": h or f"Section {len(sections)+1}",
                         "start": s_start, "end": s_end, "page": pg,
                         "body_start": s_start + len(head_txt)})
        for p, ps, pe in _paras(body, s_start + len(head_txt)):
            paras.append({"text": p, "start": ps, "end": pe, "section": len(sections) - 1, "page": pg})

    if not text.strip():
        warns.append({"issue": "no_text_layer", "detail": "输入里没有可读正文（可能只有图片/扫描件引用）"})
    if any(s["heading"].startswith("Section ") for s in sections):
        warns.append({"issue": "heading_missing", "detail": "部分小节没有标题，按顺序编号占位"})
    return {"text": text, "sections": sections, "paras": paras, "warnings": warns}


def section_text(doc, idx):
    s = doc["sections"][idx]
    return doc["text"][s["body_start"]:s["end"]]

#!/usr/bin/env python3
"""06 笔记审计：章节对齐 / 锚点可反查 / 卡片有据 / 数字来自原文。

和 v2 的关键差别：锚点不再由作者自报 verified=true，而是拿 note.span 回到
doc.text 上切片比对；比对不上就是 N07。审计可以完全独立于生成脚本运行。
"""
import json
import re

CARD_FIELDS = ["problem", "data", "method", "findings", "limitations", "premises"]
NOT_REPORTED = "not_reported"
NUM_RE = re.compile(r"(?<![A-Za-z0-9_.])(\d+(?:\.\d+)?)")
TRIVIAL = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}


def numbers(text):
    return {m.group(1) for m in NUM_RE.finditer(text or "")
            if m.group(1) not in TRIVIAL and not re.fullmatch(r"(?:19|20)\d{2}", m.group(1))}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def rate(num, den):
    return None if not den else round(num / den, 4)


def audit(result, doc):
    res = result.get("result") or {}
    notes = res.get("notes") or []
    align = res.get("section_alignment") or []
    card = res.get("reading_card") or {}
    support = res.get("card_support") or {}
    text = doc["text"]
    src_secs = [s["heading"] for s in doc["sections"]]
    blocking, advisory = [], []

    structured = str(res.get("structured_notes", ""))
    if len(structured) < 200:
        blocking.append({"type": "notes_too_short", "chars": len(structured), "code": "N01"})

    if src_secs and len(align) != len(src_secs):
        blocking.append({"type": "section_count", "expected": len(src_secs), "got": len(align), "code": "N02"})
    src_norm = {_norm(s) for s in src_secs}
    for a in align:
        name = str(a.get("section", ""))
        if name and _norm(name) not in src_norm:
            blocking.append({"type": "section_not_in_source", "section": name, "code": "N03"})
        if not str(a.get("notes", "")).strip():
            blocking.append({"type": "section_notes_empty", "section": name, "code": "N04"})
        if not str(a.get("anchor", "")).strip():
            blocking.append({"type": "section_anchor_empty", "section": name, "code": "N05"})

    for f in CARD_FIELDS:
        if not str(card.get(f, "")).strip():
            blocking.append({"type": "card_field_empty", "field": f, "code": "N06"})

    # 逐条笔记锚点反查
    unresolvable, mismatched, nonverbatim, anchor_ok = [], [], [], 0
    for n in notes:
        q = str(n.get("quote", ""))
        span = n.get("span") or []
        if q and q not in text:
            nonverbatim.append({"note_id": n.get("note_id"), "quote": q[:60]})
        if len(span) != 2 or not q:
            unresolvable.append({"note_id": n.get("note_id"), "why": "no_span_or_quote"})
            continue
        s, e = int(span[0]), int(span[1])
        if not (0 <= s < e <= len(text)) or text[s:e] != q:
            if q in text:
                mismatched.append({"note_id": n.get("note_id"), "why": "span_offset_wrong"})
            continue
        idx = n.get("section_index")
        if isinstance(idx, int) and 0 <= idx < len(doc["sections"]):
            sec = doc["sections"][idx]
            if not (sec["body_start"] <= s and e <= sec["end"]):
                mismatched.append({"note_id": n.get("note_id"), "why": "quote_in_other_section"})
                continue
        anchor_ok += 1
    if unresolvable:
        blocking.append({"type": "anchor_unresolvable", "items": unresolvable, "code": "N07"})
    if mismatched:
        blocking.append({"type": "anchor_section_mismatch", "items": mismatched, "code": "N08"})
    if nonverbatim:
        blocking.append({"type": "note_not_verbatim", "items": nonverbatim, "code": "N10"})

    # 卡片支撑
    empty_support, bad_support, card_nonverbatim = [], [], []
    known = {n.get("note_id") for n in notes}
    for f in CARD_FIELDS:
        val = str(card.get(f, ""))
        if not val or val == NOT_REPORTED:
            continue
        sid = [str(x) for x in (support.get(f) or [])]
        if not sid:
            empty_support.append(f)
        elif any(x not in known for x in sid):
            bad_support.append({"field": f, "ids": sid})
        elif val not in text:
            card_nonverbatim.append({"field": f, "value": val[:60]})
    if empty_support:
        blocking.append({"type": "card_field_unsupported", "fields": empty_support, "code": "N11"})
    if bad_support:
        blocking.append({"type": "card_support_unknown_id", "items": bad_support, "code": "N11b"})
    if card_nonverbatim:
        blocking.append({"type": "card_value_not_verbatim", "items": card_nonverbatim, "code": "N11c"})

    # 数字来源
    src_nums = numbers(text)
    used = " ".join(n.get("quote", "") for n in notes) + " " + json.dumps(card, ensure_ascii=False)
    note_nums = numbers(used)
    unsourced = sorted(note_nums - src_nums) if src_nums else []
    if unsourced:
        blocking.append({"type": "unsourced_numbers", "values": unsourced, "code": "N09"})
    elif not src_nums and note_nums:
        blocking.append({"type": "numbers_without_source_text", "values": sorted(note_nums), "code": "N09b"})

    # 章节覆盖：原文某节一句笔记都没有
    covered = {n.get("section_index") for n in notes}
    missing = [doc["sections"][i]["heading"] for i in range(len(doc["sections"])) if i not in covered]
    if missing:
        blocking.append({"type": "section_without_note", "sections": missing, "code": "N12"})

    if any(v == NOT_REPORTED for v in card.values()):
        advisory.append({"type": "card_field_not_reported",
                         "fields": [f for f in CARD_FIELDS if card.get(f) == NOT_REPORTED]})
    if not any(n.get("role") == "limitation" for n in notes):
        advisory.append({"type": "no_limitation_note"})

    rates = {
        "anchor_resolvability_rate": rate(anchor_ok, len(notes)),
        "section_coverage_rate": rate(len(set(covered) & set(range(len(doc["sections"])))), len(doc["sections"])),
        "verbatim_support_rate": rate(len(notes) - len(nonverbatim), len(notes)),
        "card_support_rate": rate(sum(1 for f in CARD_FIELDS if str(card.get(f, "")) not in ("", NOT_REPORTED)),
                                  sum(1 for f in CARD_FIELDS if str(card.get(f, "")) != NOT_REPORTED)),
        "number_sourced_rate": rate(len(note_nums & src_nums), len(note_nums)),
        "notes_count": len(notes),
        "sections": len(doc["sections"]),
    }
    return {"blocking": blocking, "advisory": advisory, "rates": rates,
            "pass": not blocking, "codes": sorted({b["code"] for b in blocking})}


def render(result, report, doc):
    res = result.get("result") or {}
    r = report["rates"]
    lines = ["# 笔记对齐与锚点审计", "",
             f"- 原文 {r['sections']} 节 / 笔记 {r['notes_count']} 条",
             f"- 锚点可反查率 `{r['anchor_resolvability_rate']}`；章节覆盖率 `{r['section_coverage_rate']}`；"
             f"逐字率 `{r['verbatim_support_rate']}`；卡片有据率 `{r['card_support_rate']}`；数字有源率 `{r['number_sourced_rate']}`",
             "", "## 章节—笔记—锚点", "", "| 小节 | 角色 | 锚点 | 原文句（截断） |", "|---|---|---|---|"]
    for n in res.get("notes") or []:
        lines.append(f"| {n.get('section','')} | {n.get('role','')} | {n.get('anchor','')} | {str(n.get('quote',''))[:60]} |")
    lines += ["", "## 阅读卡片", ""]
    for f in CARD_FIELDS:
        v = str((res.get("reading_card") or {}).get(f, ""))
        ids = ", ".join(str(x) for x in ((res.get("card_support") or {}).get(f) or [])) or "—"
        lines.append(f"- **{f}**（{ids}）：{v[:140]}")
    lines += ["", "## 结论", ""]
    if report["pass"]:
        lines.append("- 全部硬门槛通过：章节与原文一一对应，锚点可用偏移反查，卡片字段均有笔记支撑，数字均来自原文。")
    for b in report["blocking"]:
        lines.append(f"- **阻断 {b['code']}** `{b['type']}`：{json.dumps(b, ensure_ascii=False)}")
    for a in report["advisory"]:
        lines.append(f"- 提示 `{a['type']}`：{json.dumps(a, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"

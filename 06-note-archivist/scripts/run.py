"""06 平台入口：/input/case.json → /app/output/result.json（status 由产物判定）。"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit as auditlib      # noqa: E402
import card as cardlib        # noqa: E402
import extract                # noqa: E402
import notes as noteslib      # noqa: E402

OUT = "/app/output"
CANDIDATE_INPUTS = ["/input/case.json", "case.json", "input/case.json"]


def find_input(explicit=None):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for p in CANDIDATE_INPUTS:
        if os.path.isfile(p):
            return p
    return None


def _verify(doc, n):
    """锚点核验必须是"拿 span 回原文切片比对"，不是自报 verified=true。

    比对三件事：切片与 quote 逐字一致、span 落在正文范围内、锚点里的页码/段号与该 span 所属段落一致。
    """
    s, e = n["span"]
    text = doc["text"]
    slice_ok = 0 <= s <= e <= len(text) and text[s:e] == n["quote"]
    page_ok = True
    if n.get("page") is not None:
        page_ok = any(p["start"] <= s < p["end"] and p.get("page") == n["page"] for p in doc["paras"])
    return {"note_id": n["note_id"], "anchor": n["anchor"],
            "verified": bool(slice_ok and page_ok),
            "check": "text[span]==quote" + ("" if n.get("page") is None else " and page(span)==anchor page"),
            "slice": text[s:e][:60] if 0 <= s <= e <= len(text) else None,
            "span_in_range": 0 <= s <= e <= len(text), "page_matches": page_ok}


def render_notes(doc, notes):
    lines = ["# 结构化笔记", ""]
    for sec in doc["sections"]:
        mine = [n for n in notes if n["section_index"] == sec["index"]]
        lines.append(f"## {sec['heading']}")
        lines.append("")
        if not mine:
            lines.append("- （本节未抽取到可回链句子，见 uncertainty）")
        for n in mine:
            lines.append(f"- [{n['role']}] {n['quote']}")
            lines.append(f"  - anchor: `{n['anchor']}`")
        lines.append("")
    return "\n".join(lines)


def build(case_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    rejected = {"case_id": "unknown", "status": "rejected", "result": {}, "evidence": [], "uncertainty": [
        {"issue": "case.json_not_found", "detail": f"尝试过 {CANDIDATE_INPUTS}"}]}
    if not case_path:
        return rejected, None, None
    try:
        with open(case_path, "r", encoding="utf-8") as f:
            raw = f.read()
        case = json.loads(raw)
    except Exception as exc:  # 解析失败不猜内容
        rejected["uncertainty"][0] = {"issue": "case_json_unreadable", "detail": str(exc)[:200]}
        return rejected, None, None
    if not isinstance(case, dict):
        case = {"text": raw}

    doc = extract.build_doc(case)
    case_id = str(case.get("case_id") or case.get("id") or "case")

    if len(doc["text"].strip()) < 50:
        res = {"case_id": case_id, "status": "cannot_determine", "result": {}, "evidence": [],
               "uncertainty": doc["warnings"] + [{"issue": "text_too_short", "detail": f"{len(doc['text'])} chars"}]}
        return res, None, doc

    per_section = 3
    budget = case.get("note_budget")
    if isinstance(budget, int) and 1 <= budget <= 6:
        per_section = budget
    notes, w2 = noteslib.build_notes(doc, per_section=per_section)
    align = noteslib.render_sections(doc, notes)
    card, support, gaps = cardlib.build_card(notes)
    structured = render_notes(doc, notes)

    res = {
        "case_id": case_id,
        "status": "success",
        "result": {
            "structured_notes": structured,
            "notes": notes,
            "section_alignment": align,
            "reading_card": card,
            "card_support": support,
            "anchor_verification": [_verify(doc, n) for n in notes],
            "artifacts": {"notes_md": os.path.join(outdir, "notes.md"),
                          "reading_card_json": os.path.join(outdir, "reading_card.json")},
        },
        "evidence": [{"anchor": n["anchor"], "note": n["quote"][:80]} for n in notes],
        "uncertainty": doc["warnings"] + w2 + gaps,
    }
    return res, case, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="case.json 路径（默认 /input/case.json）")
    ap.add_argument("--output", default=OUT)
    args = ap.parse_args()

    case_path = find_input(args.input)
    res, case, doc = build(case_path, args.output)
    if doc is None:
        res.setdefault("uncertainty", []).append({"issue": "no_parse", "detail": "无法解析输入"})
        status = "rejected"
        report = {"blocking": [], "advisory": [], "rates": {}, "pass": False, "codes": []}
    else:
        report = auditlib.audit(res, doc)
        if not doc["text"].strip():
            status = "cannot_determine"
        elif not report["pass"]:
            status = "needs_attention"
        elif any(v == cardlib.NOT_REPORTED for v in (res["result"].get("reading_card") or {}).values()) \
                or report["advisory"]:
            status = "partial"
        else:
            status = "success"
        res["status"] = status
        res["audit"] = report
        res["metrics"] = {k: v for k, v in report["rates"].items()}

        if res["result"]:
            with open(os.path.join(args.output, "notes.md"), "w", encoding="utf-8") as f:
                f.write(res["result"]["structured_notes"])
            with open(os.path.join(args.output, "reading_card.json"), "w", encoding="utf-8") as f:
                json.dump({"case_id": res["case_id"], "reading_card": res["result"]["reading_card"],
                           "card_support": res["result"]["card_support"]}, f, ensure_ascii=False, indent=2)
            with open(os.path.join(args.output, "section_align.md"), "w", encoding="utf-8") as f:
                f.write(auditlib.render(res, report, doc))

    res.setdefault("case_id", "unknown")
    with open(os.path.join(args.output, "result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps({"status": res["status"], "pass": report["pass"],
                      "blocking": [b["code"] for b in report.get("blocking", [])],
                      "rates": report.get("rates", {})}, ensure_ascii=False))
    return 0 if res["status"] in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""02 平台入口：/input/case.json → 润色 → 事实台账 → /app/output/result.json

  python scripts/run.py                          # 默认 /input → /app/output
  python scripts/run.py --input examples/demo --output out

case.json 字段（容错）：
  text / draft / source_text / original / paragraphs[]   学生草稿
  polished_text / revised_text                            LLM 润色稿（可选；无则用最小编辑引擎）
  terms[]                                                 术语表（可省）
  case_id / id
输出：polished.md / audit.json / diff_audit.md / result.json
status：success=无阻断且保留率全 1.0；partial=有阻断或术语不一致；
        needs_attention=润色稿为空或过短；cannot_determine=无草稿；rejected=缺 case.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fact_ledger  # noqa: E402
import guard  # noqa: E402
import polish  # noqa: E402
import term_check  # noqa: E402


def draft_text(case: dict) -> str:
    for k in ("text", "draft", "source_text", "original"):
        v = case.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    parts = []
    for k in ("paragraphs", "sentences"):
        v = case.get(k)
        if isinstance(v, list):
            for p in v:
                parts.append(p.get("text", "") if isinstance(p, dict) else str(p))
    return "\n\n".join(x for x in parts if x and x.strip()).strip()


def write(out: Path, payload: dict, rc: int):
    (out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    a = ap.parse_args()
    inp, out = Path(a.input), Path(a.output)
    out.mkdir(parents=True, exist_ok=True)

    case_p = inp / "case.json"
    if not case_p.exists():
        return write(out, {"case_id": "unknown", "status": "rejected",
                           "result": {"polished_text": "", "changes": []},
                           "notes": [f"缺少 {case_p}"]}, 2)
    case = json.loads(case_p.read_text(encoding="utf-8"))
    case_id = case.get("case_id") or case.get("id") or "unknown"

    original = draft_text(case)
    if not original:
        return write(out, {"case_id": case_id, "status": "cannot_determine",
                           "result": {"polished_text": "", "changes": []},
                           "notes": ["case.json 里没有可润色的正文（text/draft/paragraphs 均为空）"]}, 2)

    supplied = case.get("polished_text") or case.get("revised_text")
    if isinstance(supplied, str) and supplied.strip():
        polished_text = supplied.strip()
        changes = case.get("changes") or []
        unchanged = []
        mode = "llm"
    else:
        polished_text, changes, unchanged = polish.polish_text(original)
        mode = "minimal-edit"

    ledger = fact_ledger.audit(original, polished_text, changes)
    terms = term_check.check(case.get("terms"), polished_text)

    (out / "polished.md").write_text("# Polished text\n\n" + polished_text + "\n", encoding="utf-8")
    (out / "diff_audit.md").write_text(
        fact_ledger.render(ledger, polished_note=f"- 模式：{mode}；改动 {len(changes)} 条，"
                                                f"未改动句子 {len(unchanged)} 条"), encoding="utf-8")

    result = {
        "case_id": case_id,
        "status": "success",
        "result": {
            "polished_text": polished_text,
            "changes": changes,
            "unchanged_sentences": unchanged,
            "no_change_statement": ("原文无需修改" if not changes else
                                    f"其余 {len(unchanged)} 句原文未改（见 unchanged_sentences）"),
            "preserved": {k: v for k, v in ledger["rates"].items()
                          if k in ("number_retention", "citation_retention",
                                   "hedge_retention", "negation_retention")},
            "artifacts": {"polished_md": str((out / "polished.md").resolve()),
                          "audit_json": str((out / "audit.json").resolve()),
                          "diff_audit_md": str((out / "diff_audit.md").resolve())},
        },
        "evidence": [{"anchor": f"sentence {x['i']+1}", "note": f"相似度 {x['similarity']}，"
                                                                f"事实标记 {'一致' if set(x['facts_before']) == set(x['facts_after']) else '有变化'}"}
                     for x in ledger["ledger"]],
        "uncertainty": [{"issue": f"第 {x['i']+1} 句改写幅度大（相似度 {x['similarity']}），建议人工确认主张未变"}
                        for x in ledger["ledger"] if 0.45 <= x["similarity"] < 0.85],
    }
    audit = {"case_id": case_id, "mode": mode, "blocking": ledger["blocking"],
             "advisory": ledger["advisory"], "rates": ledger["rates"],
             "terms": terms, "ledger": ledger["ledger"]}
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    structural = guard.check_result(result, case, str(out))
    rates = dict(ledger["rates"])
    rates["term_consistency"] = terms["rates"].get("term_consistency")

    if len(polished_text.strip()) < 20:
        status = "needs_attention"
    elif ledger["blocking"] or not structural["ok"]:
        status = "partial"
    elif any(rates[k] not in (None, 1.0) for k in ("number_retention", "citation_retention",
                                                    "hedge_retention", "negation_retention")):
        status = "partial"
    elif terms["violations"]:
        status = "partial"
    else:
        status = "success"

    result["status"] = status
    result["metrics"] = {**rates, "blocking": len(ledger["blocking"]),
                         "advisory": len(ledger["advisory"]),
                         "term_violations": len(terms["violations"]), "pass": status == "success"}
    result["notes"] = []
    if ledger["blocking"]:
        result["notes"].append("阻断: " + ",".join(sorted({b["type"] for b in ledger["blocking"]})))
    if terms["violations"]:
        result["notes"].append("术语未统一: " + ",".join(v["concept"] for v in terms["violations"]))
    if not structural["ok"]:
        result["notes"].append("结构错误: " + "; ".join(structural["errors"]))

    return write(out, result, 0 if status == "success" else 1)


if __name__ == "__main__":
    sys.exit(main())

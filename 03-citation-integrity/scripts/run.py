#!/usr/bin/env python3
"""03 平台入口：/input/case.json → 引用重排 → 四方审计 → /app/output/result.json

  python scripts/run.py                        # 默认 /input → /app/output
  python scripts/run.py --input examples/demo --output out

case.json 字段（容错）：
  manuscript / editable_manuscript / text / draft       正文
  bibliography / references / sources / bib             原始文献表
  style                                                 numeric（默认）/ author-year
  result / proposed_result                               LLM 已产出的结果（给了就只审计）
输出：manuscript.md / bibliography.json / result.json / cite_chain.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cite_chain  # noqa: E402
import guard  # noqa: E402
import renumber  # noqa: E402


def pick_text(case: dict) -> str:
    for k in ("manuscript", "editable_manuscript", "text", "draft", "original"):
        v = case.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def pick_bib(case: dict) -> list:
    for k in ("bibliography", "references", "sources", "bib"):
        v = case.get(k)
        if isinstance(v, list) and v:
            return v
    return []


def write(out: Path, payload: dict, rc: int):
    (out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
                           "result": {"editable_manuscript": "", "bibliography": []},
                           "notes": [f"缺少 {case_p}"]}, 2)
    case = json.loads(case_p.read_text(encoding="utf-8"))
    case_id = case.get("case_id") or case.get("id") or "unknown"
    style = case.get("style") or "numeric"
    ms, orig_bib = pick_text(case), pick_bib(case)

    if not ms:
        return write(out, {"case_id": case_id, "status": "cannot_determine",
                           "result": {"editable_manuscript": "", "bibliography": []},
                           "notes": ["case.json 没有正文（manuscript/text/draft 为空）"]}, 2)
    if not orig_bib:
        return write(out, {"case_id": case_id, "status": "cannot_determine",
                           "result": {"editable_manuscript": ms, "bibliography": []},
                           "notes": ["case.json 没有原始文献表，无法核验引用真假"]}, 2)

    supplied = case.get("result") or case.get("proposed_result")
    if isinstance(supplied, dict) and (supplied.get("editable_manuscript") or supplied.get("bibliography")):
        res_data = supplied
        mode = "llm"
    else:
        res_data = renumber.renumber(ms, orig_bib, style)
        mode = "engine"

    result = {"case_id": case_id, "status": "success",
              "result": {**res_data, "style": style,
                         "artifacts": {"manuscript": str((out / "manuscript.md").resolve()),
                                       "bibliography": str((out / "bibliography.json").resolve())}},
              "evidence": [{"anchor": f"citation {m['citation']}", "note": f"from_id={m['from_id']} → bib_id={m['bib_id']}"}
                           for m in res_data.get("number_mapping", [])],
              "uncertainty": res_data.get("uncertainty") or []}

    audit = cite_chain.audit(result, case)
    result["metrics"] = {**audit["rates"], "mode": mode,
                         "blocking": len(audit["blocking"]),
                         "pass": audit["pass"] and not res_data.get("unresolved")}
    if not audit["pass"]:
        result["status"] = "partial"
    elif res_data.get("unresolved"):
        result["status"] = "partial"
    result["notes"] = []
    if audit["blocking"]:
        result["notes"].append("阻断: " + ",".join(sorted({b["code"] for b in audit["blocking"]})))
    if res_data.get("unresolved"):
        result["notes"].append(f"未解析引用 {len(res_data['unresolved'])} 处，保持原样")

    (out / "manuscript.md").write_text(result["result"]["editable_manuscript"] + "\n", encoding="utf-8")
    (out / "bibliography.json").write_text(
        json.dumps(result["result"]["bibliography"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "cite_chain.md").write_text(cite_chain.render(result, audit), encoding="utf-8")

    structural = guard.check_result(result, case, str(out))
    if not structural["ok"]:
        result["status"] = "partial"
        result["notes"].append("结构错误: " + "; ".join(structural["errors"]))

    return write(out, result, 0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    sys.exit(main())

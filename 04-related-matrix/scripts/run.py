#!/usr/bin/env python3
"""04 平台入口：读 /input/case.json → matrix.build → claim_bind → /app/output/result.json。

  python scripts/run.py                          # 默认 /input → /app/output
  python scripts/run.py --input examples/demo --output /tmp/o --works examples/demo/works.json \
      --dims examples/demo/dimensions.json --manuscript examples/demo/manuscript.json \
      --draft examples/demo/intro_draft.md

status 口径（不手填，由实际产物判定）：
  success          绑定核对 pass、贡献>=1 条、工作>=3 篇
  partial          矩阵出来了但绑定核对未过，或缺草稿/贡献/空白
  cannot_determine 只有 works，连矩阵都建不起来
  rejected         输入缺 works.json 或 dimensions.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

WORKS_KEYS = ("works", "works_file", "worksJson", "papers", "literature")
DIMS_KEYS = ("dimensions", "dims", "dimensions_file", "axes")
MS_KEYS = ("manuscript", "manuscript_file", "paper")
DRAFT_KEYS = ("draft", "intro", "intro_draft", "related_work", "draft_file")
CASE_KEYS = ("case_id", "caseId", "id", "name")


def dig(obj, keys, depth=0):
    if depth > 4:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and isinstance(obj[k], str):
                return obj[k]
        for v in obj.values():
            got = dig(v, keys, depth + 1)
            if got:
                return got
    elif isinstance(obj, list):
        for v in obj[:5]:
            got = dig(v, keys, depth + 1)
            if got:
                return got
    return None


def find_file(inp: Path, names):
    for n in names:
        for p in inp.rglob(n):
            if "output" not in p.parts:
                return p
    return None


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    ap.add_argument("--works")
    ap.add_argument("--dims")
    ap.add_argument("--manuscript")
    ap.add_argument("--draft")
    a = ap.parse_args()

    inp, outp = Path(a.input), Path(a.output)
    outp.mkdir(parents=True, exist_ok=True)
    case, case_id = {}, "unknown"
    for name in ("case.json", "task.json", "input.json"):
        p = inp / name
        if p.exists():
            try:
                case = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                case_id = str(case.get("case_id") or dig(case, CASE_KEYS) or name.split(".")[0])
                break
            except Exception as e:
                case = {"_parse_error": str(e)}

    def pick(arg, keys, names):
        if arg:
            return Path(arg)
        rel = dig(case, keys)
        if rel and (inp / rel).exists():
            return inp / rel
        return find_file(inp, names)

    works = pick(a.works, WORKS_KEYS, ("works.json",))
    dims = pick(a.dims, DIMS_KEYS, ("dimensions.json", "dims.json"))
    ms = pick(a.manuscript, MS_KEYS, ("manuscript.json",))
    draft = pick(a.draft, DRAFT_KEYS, ("intro_draft.md", "intro.md", "related_work.md"))

    result = {"case_id": case_id, "status": "cannot_determine", "metrics": {}, "notes": [], "artifacts": []}
    if works is None or dims is None:
        result["status"] = "rejected"
        result["notes"].append(f"缺 works.json 或 dimensions.json（input={inp}）")
        (outp / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(2)

    # 1) 矩阵
    rc, text = run([sys.executable, str(HERE / "matrix.py"), "build",
                    "--works", str(works), "--dims", str(dims), "--out", str(outp)])
    try:
        mx = json.loads((outp / "matrix.json").read_text(encoding="utf-8"))
    except Exception:
        mx = {}
        result["notes"].append("matrix.json 未生成：" + text[-200:])
    m = result["metrics"]
    m.update({"works": mx.get("works"), "groups": len(mx.get("groups") or {}),
              "gaps": len(mx.get("gaps") or []), "conflicts": len(mx.get("conflicts") or []),
              "gap_cells": len(mx.get("gap_cells") or []), "thin_groups": len(mx.get("thin_groups") or []),
              "matrix_rc": rc})

    # 2) 论断-引用绑定（没有草稿就没有这一步，如实记 partial 原因）
    if draft is None or ms is None:
        result["status"] = "partial" if mx else "cannot_determine"
        result["notes"].append("缺 intro_draft.md 或 manuscript.json，未做论断绑定核对；"
                                "矩阵已产出，但不能判 success")
    else:
        rc2, text2 = run([sys.executable, str(HERE / "claim_bind.py"),
                          "--draft", str(draft), "--works", str(works),
                          "--manuscript", str(ms), "--out", str(outp), "--no-fail"])
        try:
            bd = json.loads((outp / "bind.json").read_text(encoding="utf-8"))
        except Exception:
            bd = {}
            result["notes"].append("bind.json 未生成：" + text2[-200:])
        rates = bd.get("rates") or {}
        m.update({"bind_rc": rc2, "bind_pass": bool(bd.get("pass")),
                  "claims": bd.get("claims"), "claim_cited": bd.get("claim_cited"),
                  "contributions": bd.get("contributions"),
                  "claim_citation_rate": rates.get("claim_citation_rate"),
                  "gap_support_rate": rates.get("gap_support_rate"),
                  "key_work_coverage": rates.get("key_work_coverage"),
                  "recent_work_coverage": rates.get("recent_work_coverage"),
                  "contribution_evidence_rate": rates.get("contribution_evidence_rate"),
                  "group_style": rates.get("group_style"),
                  "gaps_total": bd.get("gaps_total"), "gaps_covered": bd.get("gaps_covered"),
                  "claim_evidence_checks": bd.get("claim_evidence_checks"),
                  "hard_violations": len([v for v in (bd.get("violations") or [])
                                          if v.get("type") in ("claim_uncited", "dangling_citation",
                                                                "gap_unsupported", "claim_evidence_conflict",
                                                                "contribution_no_evidence",
                                                                "contribution_evidence_missing", "key_work_uncited",
                                                                "contribution_missing")])})
        contrib = bd.get("contributions") or 0
        if bd.get("pass") and contrib >= 1 and (mx.get("works") or 0) >= 3:
            result["status"] = "success"
        elif bd:
            result["status"] = "partial"
            if contrib == 0:
                result["notes"].append("草稿没有贡献条目，贡献证据率无法计算（不记 1.0）")
            if not (mx.get("gaps") or []):
                result["notes"].append("没有推出候选空白（局限未达 ≥2 篇），不能声称有空白")
        else:
            result["status"] = "cannot_determine"

    result["artifacts"] = [p for p in ("matrix.json", "matrix.md", "bind.json", "bind_report.md")
                           if (outp / p).exists()]
    (outp / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()

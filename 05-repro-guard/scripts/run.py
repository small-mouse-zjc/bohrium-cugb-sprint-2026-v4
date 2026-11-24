#!/usr/bin/env python3
"""05 平台入口：/input/case.json → 参数溯源 → 复现清单 → /app/output/result.json

  python scripts/run.py                      # 默认 /input → /app/output
  python scripts/run.py --input examples/demo --output out

case.json 字段（容错）：
  draft / methods / manuscript   方法章节 md/txt
  params / params_path           参数声明 json（{"params":[...]}）
  sources / evidence / files     来源文件列表（config/yaml/log/py）
  manifest                       复现清单 json
  steps                          步骤 json
输出：params.csv / audit.json / repro.json / repro.md / result.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
KEYS = ["declared_params", "sourced_rate", "unsourced", "conflicts",
        "repro_coverage", "step_completeness", "limitation_specificity"]


def pick(d, names):
    for n in names:
        v = d.get(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def pick_list(d, names):
    for n in names:
        v = d.get(n)
        if isinstance(v, list) and v:
            return [x for x in v if isinstance(x, str) and x.strip()]
    return None


def resolve(base: Path, p: str | None):
    if not p:
        return None
    q = Path(p)
    if q.is_absolute():
        return q
    cand = base / q
    return cand if cand.exists() else q


def call(args):
    return subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")


def write_result(out: Path, payload: dict, rc: int):
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
        return write_result(out, {"case_id": "unknown", "status": "rejected", "metrics": {"pass": False},
                                  "notes": [f"缺少 {case_p}"], "artifacts": []}, 2)
    case = json.loads(case_p.read_text(encoding="utf-8"))
    case_id = case.get("case_id") or case.get("id") or "unknown"

    draft = resolve(inp, pick(case, ["draft", "methods", "manuscript", "draft_path"]))
    params = resolve(inp, pick(case, ["params", "params_path", "declarations"]))
    sources = [resolve(inp, s) for s in (pick_list(case, ["sources", "evidence", "files", "source_files"]) or [])]
    manifest = resolve(inp, pick(case, ["manifest", "repro_manifest"]))
    steps = resolve(inp, pick(case, ["steps", "repro_steps"]))

    if not draft or not draft.exists():
        return write_result(out, {"case_id": case_id, "status": "rejected", "metrics": {"pass": False},
                                  "notes": [f"缺少方法章节: {draft}"], "artifacts": []}, 2)
    if not params or not params.exists():
        return write_result(out, {"case_id": case_id, "status": "rejected", "metrics": {"pass": False},
                                  "notes": [f"缺少参数声明: {params}"], "artifacts": []}, 2)

    artifacts, notes = [], []
    if not sources:
        audit = {"rates": {"declared_params": 0, "sourced_rate": None, "unsourced": 0, "conflicts": 0},
                 "rows": [], "violations": [{"type": "source_missing", "detail": "没有任何来源文件，参数无法溯源"}],
                 "pass": False}
        (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "params.csv").write_text("key,value,unit,source,source_locator,status,note\n", encoding="utf-8")
        artifacts += ["params.csv", "audit.json"]
    else:
        ra = call([ROOT / "scripts/param_align.py", "--draft", draft, "--params", params,
                   "--out", out, "--no-fail", "--sources"] + sources)
        audit_p = out / "audit.json"
        if not audit_p.exists():
            return write_result(out, {"case_id": case_id, "status": "rejected",
                                      "metrics": {"pass": False, "step": "param_align"},
                                      "notes": [ra.stdout[-300:], ra.stderr[-300:]], "artifacts": []}, 2)
        audit = json.loads(audit_p.read_text(encoding="utf-8"))
        artifacts += ["params.csv", "audit.json"]

    if manifest and manifest.exists() and steps and steps.exists():
        rr = call([ROOT / "scripts/repro_check.py", "--manifest", manifest, "--steps", steps,
                   "--params", out / "params.csv", "--out", out, "--no-fail"])
        repro_p = out / "repro.json"
        if repro_p.exists():
            repro = json.loads(repro_p.read_text(encoding="utf-8"))
            artifacts += ["repro.json", "repro.md"]
        else:
            repro = {"rates": {}, "pass": False, "violations": []}
            notes.append("repro_check 未产出 repro.json")
    else:
        repro = {"rates": {}, "pass": False, "violations": []}
        notes.append("未提供 manifest/steps：只完成参数溯源，复现清单未核")

    arates, rrates = audit.get("rates", {}), repro.get("rates", {})
    metrics = {k: arates.get(k) for k in ("declared_params", "sourced_rate", "unsourced", "conflicts")}
    metrics.update({"repro_coverage": rrates.get("repro_coverage"),
                    "step_completeness": rrates.get("step_completeness"),
                    "limitation_specificity": rrates.get("limitation_specificity"),
                    "pass": bool(audit.get("pass") and repro.get("pass"))})

    if not sources:
        status = "cannot_determine"
        notes.append("未给来源文件：无法核验参数是否有出处，只能交付待核草稿")
    elif audit.get("pass") and repro.get("pass"):
        status = "success"
    else:
        status = "partial"
        failed = repro.get("failed_gates") or []
        if failed:
            notes.append("未达门槛: " + ",".join(failed))
        if not audit.get("pass"):
            notes.append(f"参数溯源未过：无源 {arates.get('unsourced')}、冲突 {arates.get('conflicts')}")

    payload = {"case_id": case_id, "status": status, "metrics": metrics, "notes": notes,
               "artifacts": artifacts, "input_mode": "platform" if str(inp) == "/input" else "local"}
    return write_result(out, payload, 0 if status == "success" else 1)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""复现清单九项 + 步骤四要素核对。

  python repro_check.py --manifest manifest.json --steps steps.json --params params.csv --out out
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

COND_WORDS = ["压力", "温度", "规模", "分辨率", "样本", "范围", "条件", "场景", "仅", "低于", "高于", "少于", "大于", "当"]


def nonempty(v):
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple)):
        return all(nonempty(x) for x in v) and len(v) > 0
    if isinstance(v, dict):
        return all(nonempty(x) for x in v.values()) and len(v) > 0
    return v is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()

    m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    st = json.loads(Path(a.steps).read_text(encoding="utf-8"))["steps"]
    with open(a.params, encoding="utf-8") as f:
        prows = list(csv.DictReader(f))

    checks = {
        "code_version": m.get("code_version"),
        "environment": m.get("env"),
        "dependencies": m.get("deps"),
        "hardware": m.get("hardware"),
        "data_access": (m.get("data") or {}).get("access"),
        "data_version_split": [(m.get("data") or {}).get("name"), (m.get("data") or {}).get("version"),
                               (m.get("data") or {}).get("split")],
        "seed": (m.get("data") or {}).get("seed"),
        "command": m.get("command"),
        "runtime": m.get("runtime"),
    }
    missing = [k for k, v in checks.items() if not nonempty(v)]

    bad_steps = []
    for s in st:
        lack = [k for k in ("input", "operation", "output", "decision") if not nonempty(s.get(k))]
        if lack:
            bad_steps.append({"step": s.get("id"), "name": s.get("name"), "lack": lack})

    limits = m.get("limitations") or []
    vague = [x for x in limits if not (any(w in x for w in COND_WORDS) or any(ch.isdigit() for ch in x))]

    unsourced = [r for r in prows if r.get("status") != "sourced"]
    rates = {
        "repro_coverage": round((9 - len(missing)) / 9, 4),
        "step_completeness": round((len(st) - len(bad_steps)) / max(1, len(st)), 4) if st else None,
        "limitation_specificity": round((len(limits) - len(vague)) / len(limits), 4) if limits else None,
        "unsourced_params": len(unsourced),
    }
    viol = [{"type": "repro_field_missing", "detail": k} for k in missing]
    viol += [{"type": "step_incomplete", "detail": f"步骤 {b['step']} 缺 {b['lack']}"} for b in bad_steps]
    viol += [{"type": "limitation_vague", "detail": x} for x in vague]
    viol += [{"type": "param_not_sourced", "detail": f"{r['key']}={r['value']}"} for r in unsourced]
    if not limits:
        viol.append({"type": "limitation_missing", "detail": "manifest 没有 limitations：无法证明作者知道方法边界"})
    if not st:
        viol.append({"type": "step_missing", "detail": "steps 为空"})

    # pass 显式比对每一条门槛，不让空集或 0.0 混过去
    gates = {
        "repro_coverage": 1.0,
        "step_completeness": 1.0,
        "limitation_specificity": 1.0,
        "unsourced_params": 0,
    }
    failed_gates = [k for k, v in gates.items() if rates[k] is None or rates[k] < v]
    report = {"rates": rates, "missing": missing, "bad_steps": bad_steps, "vague_limits": vague,
              "failed_gates": failed_gates,
              "pass": not viol and not failed_gates, "violations": viol}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "repro.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    def p(x):
        return "—" if x is None else f"{x:.2%}"
    lines = ["# 复现核对", "", f"- 复现九项覆盖 {p(rates['repro_coverage'])}；缺: {', '.join(missing) or '无'}",
             f"- 步骤四要素完整率 {p(rates['step_completeness'])}",
             f"- 限制条件具体率 {p(rates['limitation_specificity'])}（无 limitations 记 —，直接卡 pass）",
             f"- 未溯源参数 {rates['unsourced_params']} 个", ""]
    if viol:
        lines += ["| 类型 | 说明 |", "|---|---|"] + [f"| {v['type']} | {v['detail']} |" for v in viol]
    (out / "repro.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], **rates, "violations": len(viol)}, ensure_ascii=False))
    if not a.no_fail and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""05 指标汇总：参数溯源 + 复现清单，并与基线对照。

  python eval/metrics.py --out_dir out --base_dir base

缺 audit.json / repro.json 时该侧字段记 None（不崩溃）；差值只在两侧都有数时给。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

KEYS = [("声明参数", "declared_params"), ("有源参数率", "sourced_rate"), ("无源数值", "unsourced"),
        ("冲突值", "conflicts"), ("复现九项覆盖", "repro_coverage"),
        ("步骤四要素完整率", "step_completeness"), ("限制具体率", "limitation_specificity")]


def load(d):
    d = Path(d)
    out = {k: None for _, k in KEYS}
    out["pass"] = False
    out["missing"] = []
    ap = d / "audit.json"
    rp = d / "repro.json"
    if ap.exists():
        a = json.loads(ap.read_text(encoding="utf-8"))
        for k in ("declared_params", "sourced_rate", "unsourced", "conflicts"):
            out[k] = a.get("rates", {}).get(k)
        out["audit_pass"] = bool(a.get("pass"))
    else:
        out["missing"].append("audit.json")
        out["audit_pass"] = False
    if rp.exists():
        r = json.loads(rp.read_text(encoding="utf-8"))
        for k in ("repro_coverage", "step_completeness", "limitation_specificity"):
            out[k] = r.get("rates", {}).get(k)
        out["repro_pass"] = bool(r.get("pass"))
    else:
        out["missing"].append("repro.json")
        out["repro_pass"] = False
    out["pass"] = bool(out["audit_pass"] and out["repro_pass"])
    return out


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--base_dir")
    a = ap.parse_args()
    s = load(a.out_dir)
    res = {"skill": s}
    md = ["| 指标 | Skill | 基线 | 差值 |", "|---|---|---|---|"]
    if a.base_dir:
        b = load(a.base_dir)
        res["base"] = b
        res["delta"] = {}
        for name, k in KEYS:
            sv, bv = s.get(k), b.get(k)
            dv = round(sv - bv, 4) if isinstance(sv, (int, float)) and isinstance(bv, (int, float)) else None
            res["delta"][k] = dv
            md.append(f"| {name} | {fmt(sv)} | {fmt(bv)} | {'—' if dv is None else dv} |")
        res["pass_gap"] = bool(s["pass"] and not b["pass"])
    else:
        for name, k in KEYS:
            md.append(f"| {name} | {fmt(s.get(k))} | — | — |")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()

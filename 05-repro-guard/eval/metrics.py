#!/usr/bin/env python3
"""05 包指标汇总：参数溯源 + 复现清单。

  python metrics.py --out_dir out
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(d):
    d = Path(d)
    a = json.loads((d / "audit.json").read_text(encoding="utf-8"))
    r = json.loads((d / "repro.json").read_text(encoding="utf-8"))
    return {
        "declared_params": a["rates"]["declared_params"],
        "sourced_rate": a["rates"]["sourced_rate"],
        "unsourced": a["rates"]["unsourced"],
        "conflicts": a["rates"]["conflicts"],
        "repro_coverage": r["rates"]["repro_coverage"],
        "step_completeness": r["rates"]["step_completeness"],
        "limitation_specificity": r["rates"]["limitation_specificity"],
        "pass": bool(a["pass"] and r["pass"]),
    }


ROWS = [("声明参数", "declared_params"), ("有源参数率", "sourced_rate"), ("无源数值", "unsourced"),
        ("冲突值", "conflicts"), ("复现九项覆盖", "repro_coverage"),
        ("步骤四要素完整率", "step_completeness"), ("限制具体率", "limitation_specificity")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--base_dir")
    a = ap.parse_args()
    s = load(a.out_dir)
    print(json.dumps({"skill": s}, ensure_ascii=False, indent=2))
    md = ["| 指标 | Skill | 基础 | 差值 |", "|---|---|---|---|"]
    if a.base_dir:
        b = load(a.base_dir)
        for name, k in ROWS:
            md.append("| %s | %s | %s | %s |" % (name, s[k], b[k], round(s[k] - b[k], 4)))
    else:
        for name, k in ROWS:
            md.append("| %s | %s | — | — |" % (name, s[k]))
    print("\n".join(md))


if __name__ == "__main__":
    main()

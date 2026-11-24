#!/usr/bin/env python3
"""04 包指标：把 matrix.json 与 bind.json 汇总成一张可对照的表。

  python metrics.py --out_dir out [--base_dir base]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(d):
    d = Path(d)
    matrix = json.loads((d / "matrix.json").read_text(encoding="utf-8"))
    bind = json.loads((d / "bind.json").read_text(encoding="utf-8"))
    grp = matrix.get("groups") or {}
    sizes = [g["n"] for g in grp.values()]
    fills = list((matrix.get("coverage") or {}).values())
    return {
        "works": matrix.get("works"),
        "group_total": len(grp),
        "groups_with_2plus": len([n for n in sizes if n >= 2]),
        "thin_groups": len(matrix.get("thin_groups") or []),
        "dim_fill_min": (min(fills) if fills else 0),
        "gaps_derived": len(matrix.get("gaps") or []),
        "conflicts_flagged": len(matrix.get("conflicts") or []),
        "claim_citation_rate": bind["rates"]["claim_citation_rate"],
        "gap_support_rate": bind["rates"]["gap_support_rate"],
        "key_work_coverage": bind["rates"]["key_work_coverage"],
        "contribution_evidence_rate": bind["rates"]["contribution_evidence_rate"],
        "pass": bool(bind.get("pass")),
    }


ROWS = [("分组数", "group_total"), ("两篇以上分组", "groups_with_2plus"), ("单篇路线", "thin_groups"),
        ("维度填充率下限", "dim_fill_min"),
        ("推导出的空白", "gaps_derived"), ("标注的冲突", "conflicts_flagged"),
        ("论断挂引用率", "claim_citation_rate"), ("空白支撑率", "gap_support_rate"),
        ("关键文献覆盖", "key_work_coverage"), ("贡献证据率", "contribution_evidence_rate")]


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

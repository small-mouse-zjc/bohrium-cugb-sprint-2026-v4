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
    matrix = json.loads((d / "matrix.json").read_text(encoding="utf-8")) if (d / "matrix.json").exists() else {}
    bind = json.loads((d / "bind.json").read_text(encoding="utf-8")) if (d / "bind.json").exists() else {}
    grp = matrix.get("groups") or {}
    sizes = [g["n"] for g in grp.values()]
    fills = list((matrix.get("coverage") or {}).values())
    rates = bind.get("rates") or {}
    # 没有 matrix/bind 说明这一侧没做矩阵与绑定核对（裸基线），记 None 而不是伪造 0
    return {
        "works": matrix.get("works"),
        "group_total": len(grp) if matrix else None,
        "groups_with_2plus": len([n for n in sizes if n >= 2]) if matrix else None,
        "thin_groups": len(matrix.get("thin_groups") or []) if matrix else None,
        "dim_fill_min": (min(fills) if fills else 0) if matrix else None,
        "gaps_derived": len(matrix.get("gaps") or []) if matrix else None,
        "conflicts_flagged": len(matrix.get("conflicts") or []) if matrix else None,
        "claim_citation_rate": rates.get("claim_citation_rate"),
        "gap_support_rate": rates.get("gap_support_rate"),
        "key_work_coverage": rates.get("key_work_coverage"),
        "recent_work_coverage": rates.get("recent_work_coverage"),
        "contribution_evidence_rate": rates.get("contribution_evidence_rate"),
        "group_style": rates.get("group_style"),
        "pass": bool(bind.get("pass")),
    }


ROWS = [("处理工作数", "works"), ("分组数", "group_total"), ("两篇以上分组", "groups_with_2plus"),
        ("单篇路线", "thin_groups"), ("维度填充率下限", "dim_fill_min"),
        ("推导出的空白", "gaps_derived"), ("标注的冲突", "conflicts_flagged"),
        ("论断挂引用率", "claim_citation_rate"), ("空白支撑率", "gap_support_rate"),
        ("关键文献覆盖", "key_work_coverage"), ("近作覆盖", "recent_work_coverage"),
        ("贡献证据率", "contribution_evidence_rate"), ("写法", "group_style")]


def diff(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return round(a - b, 4)
    return "—"


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
            md.append("| %s | %s | %s | %s |" % (name, s[k], b[k], diff(s[k], b[k])))
    else:
        for name, k in ROWS:
            md.append("| %s | %s | — | — |" % (name, s[k]))
    print("\n".join(md))


if __name__ == "__main__":
    main()

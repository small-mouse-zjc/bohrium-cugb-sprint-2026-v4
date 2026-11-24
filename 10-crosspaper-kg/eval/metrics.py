#!/usr/bin/env python3
"""10 包指标：读取 validation.json 汇总，并与基线对照。

  python eval/metrics.py --out_dir out --base_dir base

缺 validation.json 时该侧字段记 None（不崩溃）；差值只在两侧都有数时计算。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROWS = [("实体提及数", "mentions"), ("归一覆盖率", "mention_coverage"), ("节点数", "nodes"),
        ("跨篇节点数", "cross_paper_nodes"), ("非合并判定", "non_merge"), ("边数", "edges"),
        ("边引文率", "edge_evidence_rate"), ("查询有证据率", "query_provenance_rate")]


def load(d):
    p = Path(d) / "validation.json"
    r = {k: None for _, k in ROWS}
    r["pass"] = False
    r["missing"] = None
    if not p.exists():
        r["missing"] = str(p)
        return r
    v = json.loads(p.read_text(encoding="utf-8"))
    r.update({k: v.get("rates", {}).get(k) for _, k in ROWS})
    r["pass"] = bool(v.get("pass"))
    r["failed_gates"] = v.get("failed_gates", [])
    return r


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
        for n, k in ROWS:
            sv, bv = s.get(k), b.get(k)
            dv = round(sv - bv, 4) if isinstance(sv, (int, float)) and isinstance(bv, (int, float)) else None
            res["delta"][k] = dv
            md.append(f"| {n} | {fmt(sv)} | {fmt(bv)} | {'—' if dv is None else dv} |")
        res["pass_gap"] = bool(s["pass"] and not b["pass"])
        md.append(f"| 判定 pass | {s['pass']} | {b['pass']} | — |")
    else:
        for n, k in ROWS:
            md.append(f"| {n} | {fmt(s.get(k))} | — | — |")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()

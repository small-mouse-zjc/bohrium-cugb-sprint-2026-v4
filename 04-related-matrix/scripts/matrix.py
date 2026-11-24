#!/usr/bin/env python3
"""建"工作×维度"矩阵，并从中推出候选空白与冲突。

  python matrix.py build --works works.json --dims dimensions.json --out out

输出 out/matrix.md、out/matrix.json（含 coverage / gaps / conflicts / gap_cells）。
空白规则：某局限被 >=2 篇列为 limits 且无人 addresses -> 候选空白。
冲突规则：同一 claim_key 同时出现 supports 与 opposes。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(p: str):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def build(works, dims):
    dim_list = dims["dimensions"]
    rows = []
    for w in works:
        rows.append({d["key"]: (w.get(d["key"]) or "").strip() for d in dim_list})

    # 维度填充率
    coverage = {}
    gap_cells = []
    for d in dim_list:
        filled = sum(1 for w in works if (w.get(d["key"]) or "").strip())
        coverage[d["key"]] = round(filled / max(1, len(works)), 4)
        for w in works:
            if not (w.get(d["key"]) or "").strip():
                gap_cells.append({"wid": w["wid"], "dim": d["key"], "label": d["name"]})

    # 空白：共同局限 + 无人覆盖
    limit_count, limit_support = {}, {}
    addressed = set()
    for w in works:
        for lim in (w.get("limits") or []):
            limit_count[lim] = limit_count.get(lim, 0) + 1
            limit_support.setdefault(lim, []).append(w["wid"])
        addressed.update(w.get("addresses") or [])
    gaps = [{"limitation": lim, "support_wids": wids, "support_count": len(wids),
             "reason": f"{len(wids)} 篇均指出「{lim}」，且无一篇覆盖"}
            for lim, wids in limit_support.items()
            if len(wids) >= 2 and lim not in addressed]

    # 冲突
    stance_map = {}
    for w in works:
        for claim, st in (w.get("stance") or {}).items():
            stance_map.setdefault(claim, {"supports": [], "opposes": [], "neutral": []})[st].append(w["wid"])
    conflicts = [{"claim": c, "supports": v["supports"], "opposes": v["opposes"]}
                 for c, v in stance_map.items() if v["supports"] and v["opposes"]]

    # 分组
    groups = {}
    for w in works:
        groups.setdefault((w.get("route") or "未分组"), []).append(w["wid"])

    md = ["# 工作×维度比较矩阵", "", "| 工作 | " + " | ".join(d["name"] for d in dim_list) + " | 来源 |",
          "|" + "---|" * (len(dim_list) + 2)]
    for w, r in zip(works, rows):
        ev = (w.get("evidence") or {}).get("locator", "")
        md.append(f"| {w['wid']} {w.get('label','')} | " + " | ".join(r[d["key"]] or "—" for d in dim_list) + f" | {ev} |")
    md += ["", "## 分组", ""]
    for g, wids in groups.items():
        md.append(f"- **{g}**（{len(wids)} 篇）：" + "、".join(wids))
    md += ["", "## 候选空白（由共同局限推出）", ""]
    if gaps:
        for g in gaps:
            md.append(f"- {g['limitation']}：支撑 " + "、".join(g["support_wids"]) + "；" + g["reason"])
    else:
        md.append("- 无（局限未形成 ≥2 篇的共同缺口，不要硬写空白）")
    md += ["", "## 结论冲突", ""]
    if conflicts:
        for c in conflicts:
            md.append(f"- 「{c['claim']}」：支持 " + "、".join(c["supports"]) + "；反对 " + "、".join(c["opposes"]))
    else:
        md.append("- 无")

    return {"works": len(works), "dimensions": [d["key"] for d in dim_list], "coverage": coverage,
            "gap_cells": gap_cells, "gaps": gaps, "conflicts": conflicts,
            "groups": {k: {"n": len(v), "wids": v} for k, v in groups.items()},
            "thin_groups": [k for k, v in groups.items() if len(v) == 1]}, "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--works", required=True)
    ap.add_argument("--dims", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    works = load(a.works).get("works", [])
    dims = load(a.dims)
    res, md = build(works, dims)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "matrix.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "matrix.md").write_text(md, encoding="utf-8")
    print(json.dumps({"works": res["works"], "groups": len(res["groups"]),
                      "gaps": len(res["gaps"]), "conflicts": len(res["conflicts"]),
                      "gap_cells": len(res["gap_cells"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

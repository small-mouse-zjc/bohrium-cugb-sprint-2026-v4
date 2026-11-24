#!/usr/bin/env python3
"""10 包指标：读取 validation.json + kg.json 汇总。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROWS = [("实体提及数", "mentions"), ("归一覆盖率", "mention_coverage"), ("节点数", "nodes"),
        ("跨篇节点数", "cross_paper_nodes"), ("非合并判定", "non_merge"), ("边数", "edges"),
        ("边引文率", "edge_evidence_rate"), ("查询有证据率", "query_provenance_rate")]


def load(d):
    v = json.loads((Path(d) / "validation.json").read_text(encoding="utf-8"))
    r = dict(v["rates"])
    r["pass"] = bool(v["pass"])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--base_dir")
    a = ap.parse_args()
    s = load(a.out_dir)
    print(json.dumps({"skill": s}, ensure_ascii=False, indent=2))
    md = ["| 指标 | Skill | 基础 |", "|---|---|---|"]
    if a.base_dir:
        b = load(a.base_dir)
        for n, k in ROWS:
            md.append("| %s | %s | %s |" % (n, s[k], b[k]))
    else:
        for n, k in ROWS:
            md.append("| %s | %s | — |" % (n, s[k]))
    print("\n".join(md))


if __name__ == "__main__":
    main()

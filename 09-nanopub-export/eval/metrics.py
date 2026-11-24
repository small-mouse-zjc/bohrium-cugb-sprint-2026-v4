#!/usr/bin/env python3
"""09 包指标：读取 validation.json 汇总。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROWS = [("断言数", "assertions"), ("原子率", "atomic_rate"), ("逐字证据率", "verbatim_rate"),
        ("来源完整率", "provenance_rate"), ("导出回解析", "export_roundtrip")]


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

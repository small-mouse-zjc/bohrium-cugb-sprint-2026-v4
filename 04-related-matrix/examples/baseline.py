#!/usr/bin/env python3
"""04 基线对照：模拟"裸 Agent"——只把 works.json 逐篇摘要，不建矩阵、不做绑定核对。

  python examples/baseline.py --works examples/demo/works.json --out out_base

产物只有 summary.md（故意没有 matrix.json / bind.json），
供 eval/metrics.py --base_dir 对比，得到可复现的差值而不是自说自话。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = json.loads(Path(a.works).read_text(encoding="utf-8"))
    works = data.get("works", data) if isinstance(data, dict) else data
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# 相关工作逐篇摘要（基线：不建矩阵）", ""]
    for w in works:
        lim = "、".join(w.get("limits") or []) or "未标注"
        lines.append(f"- **{w.get('wid')} {w.get('label','')}**（{w.get('year','?')}, {w.get('route','未分组')}）："
                     f"{w.get('summary') or w.get('claim') or ''} 局限：{lim}")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "baseline.json").write_text(json.dumps({"works": len(works), "method": "per-work summary, "
                                                   "no matrix, no claim binding"}, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(json.dumps({"works": len(works), "outputs": ["summary.md"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

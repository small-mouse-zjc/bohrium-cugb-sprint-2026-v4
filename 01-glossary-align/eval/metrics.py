#!/usr/bin/env python3
"""用同一套指标比较两份结果目录（skill 输出 vs 基础 Agent 输出）。

  python metrics.py --skill out_skill --base out_base
  python metrics.py --skill out_skill            # 只报单侧指标

只读取各自目录下的 qc.json；缺文件直接报错，不估算、不补零。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

KEYS = ["coverage", "term_consistency", "number_preservation", "citation_preservation", "uncertain_flagging"]
LABEL = {"coverage": "段落覆盖率", "term_consistency": "术语一致率", "number_preservation": "数字保真率",
         "citation_preservation": "引用保真率", "uncertain_flagging": "未确定标注率"}


def load(p: Path):
    f = p / "qc.json"
    if not f.exists():
        raise SystemExit(f"缺少 {f}，先跑 scripts/qc.py 再比较")
    d = json.loads(f.read_text(encoding="utf-8"))
    return d["rates"], d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True)
    ap.add_argument("--base")
    ap.add_argument("--out")
    a = ap.parse_args()
    s, sd = load(Path(a.skill))
    res = {"skill": s, "skill_pass": sd["pass"], "skill_violations": len(sd["violations"])}
    lines = ["| 指标 | Skill | 基础 | 差值 |", "|---|---|---|---|"]
    if a.base:
        b, bd = load(Path(a.base))
        res["base"] = b
        res["delta"] = {k: round(s[k] - b[k], 4) for k in KEYS}
        for k in KEYS:
            lines.append(f"| {LABEL[k]} | {s[k]:.2%} | {b[k]:.2%} | {s[k]-b[k]:+.2%} |")
        res["gain_items"] = sum(1 for k in KEYS if s[k] > b[k])
    else:
        for k in KEYS:
            lines.append(f"| {LABEL[k]} | {s[k]:.2%} | — | — |")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print("\n".join(lines))
    if a.out:
        Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

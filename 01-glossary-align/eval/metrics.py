#!/usr/bin/env python3
"""01 指标对照：同一套五项比率比较 Skill 输出与基线输出。

  python eval/metrics.py --skill out_skill --base out_base

缺 qc.json 时该侧记为 None（并注明原因），不再直接崩溃；差值只在两侧都有数时计算。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

KEYS = ["coverage", "term_consistency", "number_preservation", "citation_preservation", "uncertain_flagging", "basis_coverage"]
LABEL = {"coverage": "段落覆盖率", "term_consistency": "术语一致率", "number_preservation": "数字保真率",
         "citation_preservation": "引用保真率", "uncertain_flagging": "未确定标注率",
         "basis_coverage": "译法依据覆盖率"}


def load(p: Path):
    f = p / "qc.json"
    if not f.exists():
        return None, {"pass": False, "violations": [], "missing": str(f)}
    d = json.loads(f.read_text(encoding="utf-8"))
    return d.get("rates", {}), d


def pct(v):
    return "—" if v is None else f"{v:.2%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True)
    ap.add_argument("--base")
    ap.add_argument("--out")
    a = ap.parse_args()
    s, sd = load(Path(a.skill))
    s = s if s is not None else {k: None for k in KEYS}
    res = {"skill": s, "skill_pass": sd["pass"], "skill_violations": len(sd["violations"]),
           "skill_missing": sd.get("missing")}
    lines = ["| 指标 | Skill | 基线 | 差值 |", "|---|---|---|---|"]
    if a.base:
        b, bd = load(Path(a.base))
        b = b if b is not None else {k: None for k in KEYS}
        res["base"] = b
        res["base_pass"] = bd["pass"]
        res["base_missing"] = bd.get("missing")
        res["delta"] = {k: (round(s[k] - b[k], 4) if s[k] is not None and b[k] is not None else None) for k in KEYS}
        for k in KEYS:
            dv = res["delta"][k]
            lines.append(f"| {LABEL[k]} | {pct(s[k])} | {pct(b[k])} | {'—' if dv is None else f'{dv:+.2%}'} |")
        res["gain_items"] = sum(1 for k in KEYS if res["delta"][k] is not None and res["delta"][k] > 0)
        res["pass_gap"] = bool(sd["pass"]) and not bd["pass"]
    else:
        for k in KEYS:
            lines.append(f"| {LABEL[k]} | {pct(s[k])} | — | — |")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print("\n".join(lines))
    if a.out:
        Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

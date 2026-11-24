#!/usr/bin/env python3
"""08 包指标：与已知真值对比，可选与朴素基线并列输出。

  python metrics.py --out_dir examples/expected/reflow --truth examples/expected/truth.json \
                    --base_dir examples/expected/baseline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import evaluate  # noqa: E402

ROWS = [("抽出的块", "blocks_extracted"), ("位置命中率", "exact_position_rate"),
        ("逆序对", "inversions"), ("相邻错位", "adjacent_errors"), ("顺序一致", "order_match")]


def load(out_dir, truth):
    t = Path(truth)
    if not t.exists():
        return {"blocks_extracted": None, "exact_position_rate": None, "inversions": None,
                "adjacent_errors": None, "order_match": None, "missing": ["truth.json"], "pass": False}
    r = evaluate(out_dir, truth)
    r["pass"] = bool(r["order_match"]) and r["inversions"] == 0 and not r["missing"]
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
    ap.add_argument("--truth", required=True)
    ap.add_argument("--base_dir")
    a = ap.parse_args()
    s = load(a.out_dir, a.truth)
    res = {"skill": {k: s[k] for k in ("blocks_extracted", "exact_position_rate",
                                       "inversions", "adjacent_errors", "order_match", "pass")}}
    md = ["| 指标 | Skill | 基线 | 差值 |", "|---|---|---|---|"]
    if a.base_dir:
        b = load(a.base_dir, a.truth)
        res["base"] = {k: b[k] for k in ("blocks_extracted", "exact_position_rate",
                                         "inversions", "adjacent_errors", "order_match", "pass")}
        res["delta"] = {}
        for n, k in ROWS:
            sv, bv = s.get(k), b.get(k)
            dv = round(sv - bv, 4) if isinstance(sv, (int, float)) and isinstance(bv, (int, float)) else None
            res["delta"][k] = dv
            md.append(f"| {n} | {fmt(sv)} | {fmt(bv)} | {'—' if dv is None else dv} |")
        md.append(f"| 判定 pass | {s['pass']} | {b['pass']} | {'Skill 过 / 基线不过' if s['pass'] and not b['pass'] else '—'} |")
    else:
        for n, k in ROWS:
            md.append(f"| {n} | {fmt(s.get(k))} | — | — |")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()

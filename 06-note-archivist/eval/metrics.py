#!/usr/bin/env python3
"""06 指标表：真跑结果 vs 基线（同一份 case、同一套审计）。

用法：
  python eval/metrics.py --result /app/output/result.json --case /input/case.json \
      [--base_dir /app/output/baseline]
缺数据记 None，不崩；分母为 0 也记 None，绝不写 1.00。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import audit as auditlib   # noqa: E402
import extract             # noqa: E402

KEYS = ["anchor_resolvability_rate", "section_coverage_rate", "verbatim_support_rate",
        "card_support_rate", "number_sourced_rate"]
HIGHER_BETTER = dict.fromkeys(KEYS, True)


def load(p):
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def rates_for(result, doc):
    if not result or not doc:
        return {k: None for k in KEYS}
    rep = auditlib.audit(result, doc)
    return {k: rep["rates"].get(k) for k in KEYS}


def compare(real, base):
    out = {}
    for k in KEYS:
        r, b = real.get(k), (base or {}).get(k)
        if r is None or b is None:
            out[k] = {"real": r, "baseline": b, "delta": None, "pass": None}
        else:
            out[k] = {"real": r, "baseline": b, "delta": round(r - b, 4), "pass": r >= b}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--case")
    ap.add_argument("--base_dir")
    ap.add_argument("--out")
    args = ap.parse_args()
    case = load(args.case) or {}
    doc = extract.build_doc(case) if case else None
    real = rates_for(load(args.result), doc)
    base = rates_for(load(os.path.join(args.base_dir, "result.json")), doc) if args.base_dir else None
    table = compare(real, base)
    report = {"real": real, "baseline": base, "table": table,
              "pass_gap": (all(v["pass"] for v in table.values() if v["pass"] is not None)
                           if base else None)}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""用已知真值衡量阅读顺序：完全一致率、逆序对数、串栏相邻对数。

  python measure.py --out out_dir --truth truth.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MARK = re.compile(r"\[\[([A-Z]\d+)\]\]")


def evaluate(out_dir, truth_path):
    rows = [json.loads(l) for l in (Path(out_dir) / "paragraphs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    got = []
    for r in rows:
        for m in MARK.finditer(r["text"]):
            got.append(m.group(1))
    truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))["order"]

    common = [x for x in got if x in truth]
    exact = sum(1 for i, x in enumerate(truth) if i < len(got) and got[i] == x)
    pos = {x: i for i, x in enumerate(got)}
    inversions = 0
    for i, x in enumerate(truth):
        if x not in pos:
            continue
        for y in truth[i + 1:]:
            if y in pos and pos[y] < pos[x]:
                inversions += 1
    cross = 0
    for x, y in zip(got, got[1:]):
        if x in truth and y in truth and abs(truth.index(x) - truth.index(y)) > 1:
            cross += 1

    return {"blocks_in_truth": len(truth), "blocks_extracted": len(got),
            "exact_position_rate": round(exact / max(1, len(truth)), 4),
            "inversions": inversions, "adjacent_errors": cross,
            "missing": [x for x in truth if x not in got],
            "order_match": got == truth, "got": got}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth", required=True)
    a = ap.parse_args()
    res = evaluate(a.out, a.truth)
    print(json.dumps({k: res[k] for k in ("blocks_extracted", "exact_position_rate", "inversions", "adjacent_errors", "order_match")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

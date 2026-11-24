#!/usr/bin/env python3
"""02 术语一致性：同一概念只许一种写法（润色最容易顺手换词）。

case.json 的 terms 可以是：
  [{"concept": "dissociation pressure", "canonical": "dissociation pressure",
    "variants": ["disassociation pressure", "dissociation pressures"]}]
或字符串列表（视为 canonical，变体按大小写/复数/连字符生成）。
"""
from __future__ import annotations

import re


def _occurrences(text: str, form: str) -> int:
    if not form or not text:
        return 0
    return len(re.findall(r"(?<![A-Za-z])" + re.escape(form) + r"(?![A-Za-z])",
                          text, flags=re.I))


def check(terms, polished: str) -> dict:
    if not terms:
        return {"rates": {"term_consistency": None, "terms": 0},
                "violations": [], "note": "case 未给 terms，术语一致率记 None（不记 1.0）"}

    violations, rows = [], []
    tot_ok = tot_all = 0
    for t in terms:
        if isinstance(t, str):
            concept, canonical, variants = t, t, []
        else:
            concept = t.get("concept") or t.get("canonical")
            canonical = t.get("canonical") or concept
            variants = t.get("variants") or []
        canon_n = _occurrences(polished, canonical)
        var_hits = []
        for v in variants:
            n = _occurrences(polished, v)
            if n:
                var_hits.append({"variant": v, "count": n})
        rows.append({"concept": concept, "canonical": canonical,
                     "canonical_count": canon_n, "variants_found": var_hits})
        tot_all += canon_n + sum(v["count"] for v in var_hits)
        tot_ok += canon_n
        if var_hits:
            violations.append({"code": "T01", "concept": concept,
                               "variants_found": var_hits,
                               "detail": f"同一概念出现非规范写法，应统一为 '{canonical}'"})
    rate = round(tot_ok / tot_all, 4) if tot_all else None
    return {"rates": {"term_consistency": rate, "terms": len(terms)},
            "violations": violations, "rows": rows}


if __name__ == "__main__":
    import json
    import sys

    case = json.load(open(sys.argv[1], encoding="utf-8"))
    pol = open(sys.argv[2], encoding="utf-8").read()
    print(json.dumps(check(case.get("terms"), pol), ensure_ascii=False, indent=2))

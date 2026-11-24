#!/usr/bin/env python3
"""参数-来源对齐：正文数值 vs 配置/日志/代码；顺带抓"带单位但全库找不到"的数。

  python param_align.py --draft methods.md --params params.json \
      --sources config.yaml train.log model.py --out out
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

NUM = r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?\d+)?"
UNIT = r"(?:%|MPa|GPa|kPa|°C|K|s|ms|h|min|GB|MB|TB|轮|层|维|次|个)"


def parse_num(s: str):
    try:
        return float(s)
    except Exception:
        return None


def same(a: str, b: str) -> bool:
    fa, fb = parse_num(a), parse_num(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) <= 1e-12 * max(1.0, abs(fa))
    return a.strip().lower() == b.strip().lower()


def index_sources(files):
    idx = {}
    generic = []
    for f in files:
        p = Path(f)
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for m in re.finditer(rf"([A-Za-z_][A-Za-z0-9_]{{1,30}})\s*[:=]\s*({NUM})", line):
                idx.setdefault(m.group(1).lower(), []).append((m.group(2), f"{p.name}:{i}"))
            for m in re.finditer(NUM, line):
                generic.append((m.group(0), f"{p.name}:{i}"))
    return idx, generic


def values_in_draft(text, alias):
    out = []
    for m in re.finditer(re.escape(alias), text, re.I):
        tail = text[m.end():m.end() + 30]
        n = re.search(NUM, tail)
        if n:
            # 只接受别名后 12 字符内出现的数值，避免跨句误配
            gap = tail[:n.start()]
            if len(gap) <= 12:
                out.append((n.group(0), m.start()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()

    text = Path(a.draft).read_text(encoding="utf-8")
    params = json.loads(Path(a.params).read_text(encoding="utf-8"))["params"]
    src_idx, generic = index_sources(a.sources)

    rows, viol = [], []
    declared_numbers = set()
    for p in params:
        key = p["key"]
        aliases = [key] + [x for x in p.get("aliases", []) if x]
        found = []
        for al in aliases:
            found += values_in_draft(text, al)
        src_hits = []
        for al in aliases:
            src_hits += src_idx.get(al.lower(), [])
        if not found:
            if src_hits:
                viol.append({"type": "param_omitted", "detail": f"来源有 {key}，正文未写", "key": key})
            continue
        for val, _pos in found:
            declared_numbers.add(val)
            if not src_hits:
                rows.append({"key": key, "value": val, "unit": p.get("unit", ""), "source": "",
                             "source_locator": "", "status": "unsourced", "note": "来源里找不到该参数"})
                viol.append({"type": "param_unsourced", "detail": f"{key}={val} 无来源", "key": key})
                continue
            match = next((h for h in src_hits if same(val, h[0])), None)
            if match:
                rows.append({"key": key, "value": val, "unit": p.get("unit", ""), "source": match[1].split(":")[0],
                             "source_locator": match[1], "status": "sourced", "note": ""})
            else:
                rows.append({"key": key, "value": val, "unit": p.get("unit", ""), "source": src_hits[0][1].split(":")[0],
                             "source_locator": src_hits[0][1], "status": "conflict",
                             "note": f"来源值为 {src_hits[0][0]}"})
                viol.append({"type": "param_conflict", "detail": f"{key}: 正文 {val} vs 来源 {src_hits[0][0]}", "key": key})

    # 带单位的数值：全库找不到即视为无源
    for m in re.finditer(rf"({NUM})\s*{UNIT}", text):
        val = m.group(1)
        if val in declared_numbers:
            continue
        if not any(same(val, g[0]) for g in generic):
            viol.append({"type": "unsourced_number", "detail": f"带单位数值 {m.group(0)} 在全部来源里找不到",
                         "span": [m.start(), m.end()]})

    n_src = sum(1 for r in rows if r["status"] == "sourced")
    rates = {
        "declared_params": len({r["key"] for r in rows}),
        "sourced_rate": round(n_src / max(1, len(rows)), 4) if rows else 1.0,
        "unsourced": sum(1 for r in rows if r["status"] == "unsourced") + sum(1 for v in viol if v["type"] == "unsourced_number"),
        "conflicts": sum(1 for r in rows if r["status"] == "conflict"),
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "params.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["key", "value", "unit", "source", "source_locator", "status", "note"])
        w.writeheader()
        w.writerows(rows)
    audit = {"rates": rates, "rows": rows, "violations": viol,
             "pass": rates["unsourced"] == 0 and rates["conflicts"] == 0 and not any(v["type"] == "param_omitted" for v in viol)}
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pass": audit["pass"], **rates, "violations": len(viol)}, ensure_ascii=False))
    if not a.no_fail and not audit["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

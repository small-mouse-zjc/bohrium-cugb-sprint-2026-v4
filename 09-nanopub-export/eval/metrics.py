#!/usr/bin/env python3
"""09 包指标：读取 validation.json 汇总；基线侧没有 validation.json 时记 None，不崩溃。

  python metrics.py --out_dir out [--base_dir base]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROWS = [("断言数", "assertions"), ("原子率", "atomic_rate"), ("逐字证据率", "verbatim_rate"),
        ("来源完整率", "provenance_rate"), ("导出回解析", "export_roundtrip"), ("通过", "pass")]


def load(d):
    d = Path(d)
    if not (d / "validation.json").exists():
        n = 0
        for p in d.rglob("*.json"):
            try:
                js = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(js, dict) and isinstance(js.get("assertions"), list):
                    n = max(n, len(js["assertions"]))
            except Exception:
                continue
        # 裸基线：只把断言原样转存，没有校验与序列化 → 率一律 None，不伪造 0/1
        return {"assertions": n or None, "atomic_rate": None, "verbatim_rate": None,
                "provenance_rate": None, "export_roundtrip": None, "pass": False}
    v = json.loads((d / "validation.json").read_text(encoding="utf-8"))
    r = dict(v.get("rates") or {})
    r["pass"] = bool(v.get("pass"))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--base_dir")
    a = ap.parse_args()
    s = load(a.out_dir)
    print(json.dumps({"skill": s}, ensure_ascii=False, indent=2))
    md = ["| 指标 | Skill | 基础 | 差值 |", "|---|---|---|---|"]
    if a.base_dir:
        b = load(a.base_dir)
        for n, k in ROWS:
            va, vb = s.get(k), b.get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool):
                dv = round(va - vb, 4)
            else:
                dv = "—"
            md.append("| %s | %s | %s | %s |" % (n, va, vb, dv))
    else:
        for n, k in ROWS:
            md.append("| %s | %s | — | — |" % (n, s.get(k)))
    print("\n".join(md))


if __name__ == "__main__":
    main()

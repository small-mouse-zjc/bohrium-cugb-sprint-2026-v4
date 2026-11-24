#!/usr/bin/env python3
"""03 指标对照：本包 result.json vs 基线，给出真实差值。

  python eval/metrics.py --out_dir out --base_dir base

指标：citation_closure_rate / metadata_verbatim_rate / claim_map_coverage；
缺文件或字段记 None，不冒充 0。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

KEYS = ("citation_closure_rate", "metadata_verbatim_rate", "claim_map_coverage")


def load(p: Path) -> dict:
    f = p / "result.json"
    if not f.exists():
        return {k: None for k in KEYS} | {"missing": "result.json 不存在", "pass": None}
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {k: None for k in KEYS} | {"missing": "result.json 无法解析", "pass": None}
    m = r.get("metrics") or {}
    out = {k: (None if m.get(k) is None else round(float(m.get(k)), 4)) for k in KEYS}
    out["pass"] = m.get("pass")
    out["blocking"] = m.get("blocking")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--base_dir")
    a = ap.parse_args()
    skill = load(Path(a.out_dir))
    base = load(Path(a.base_dir)) if a.base_dir else {k: None for k in KEYS}
    delta = {k: (None if skill.get(k) is None or base.get(k) is None
                 else round(skill[k] - base[k], 4)) for k in KEYS}
    payload = {"skill": skill, "base": base, "delta": delta,
               "below_one": [k for k in KEYS if skill.get(k) is not None and skill[k] < 1.0],
               "pass_gap": bool(skill.get("pass") and base.get("pass") is False)}
    print(json.dumps(payload, ensure_ascii=False))
    lines = ["| 指标 | 本包 | 基线（裸 Agent） | 差值 |", "|---|---|---|---|"]
    for k in KEYS:
        s = "—" if skill.get(k) is None else f"{skill[k]:.4f}"
        b = "—" if base.get(k) is None else f"{base[k]:.4f}"
        d = "—" if delta[k] is None else f"{delta[k]:+.4f}"
        lines.append(f"| {k} | {s} | {b} | {d} |")
    lines.append(f"\n- 本包 pass：{skill.get('pass')}；基线 pass：{base.get('pass')}")
    if base.get("missing"):
        lines.append(f"- 基线缺数据：{base['missing']}（记 None，不当作 0）")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

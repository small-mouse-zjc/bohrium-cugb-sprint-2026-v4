#!/usr/bin/env python3
"""02 指标对照：本包 result.json vs 基线 result.json，给出真实差值表。

  python eval/metrics.py --out_dir out --base_dir base
输出：第一行 JSON（指标/差值/是否过线），之后是 Markdown 表。
缺文件或字段缺失一律记 None，不冒充 0。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

KEYS = ("fact_preservation_rate", "number_retention", "citation_retention",
        "hedge_retention", "negation_retention", "sentence_coverage", "term_consistency")


def load_rates(p: Path) -> dict:
    f = p / "result.json"
    if not f.exists():
        return {k: None for k in KEYS} | {"missing": "result.json 不存在"}
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {k: None for k in KEYS} | {"missing": "result.json 无法解析"}
    m = r.get("metrics") or {}
    res = r.get("result") or {}
    out = {}
    for k in KEYS:
        v = m.get(k)
        if v is None and k in ("number_retention", "citation_retention"):
            v = (res.get("preserved") or {}).get(k)
        out[k] = None if v is None else round(float(v), 4)
    out["pass"] = m.get("pass") if "pass" in m else (r.get("status") == "success")
    out["blocking"] = m.get("blocking")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--base_dir")
    a = ap.parse_args()
    skill = load_rates(Path(a.out_dir))
    base = load_rates(Path(a.base_dir)) if a.base_dir else {k: None for k in KEYS}

    delta = {k: (None if skill.get(k) is None or base.get(k) is None
                 else round(skill[k] - base[k], 4)) for k in KEYS}
    passed = [k for k in KEYS if skill.get(k) is not None and skill[k] < 1.0]
    payload = {"skill": skill, "base": base, "delta": delta,
               "below_one": passed,
               "pass_gap": bool(skill.get("pass") and base.get("pass") is False)}
    print(json.dumps(payload, ensure_ascii=False))

    lines = ["| 指标 | 本包 | 基线（裸 Agent） | 差值 |", "|---|---|---|---|"]
    for k in KEYS:
        s = "—" if skill.get(k) is None else f"{skill[k]:.4f}"
        b = "—" if base.get(k) is None else f"{base[k]:.4f}"
        d = "—" if delta[k] is None else f"{delta[k]:+.4f}"
        lines.append(f"| {k} | {s} | {b} | {d} |")
    lines.append(f"\n- 本包 status pass：{skill.get('pass')}；基线 pass：{base.get('pass')}")
    if base.get("missing"):
        lines.append(f"- 基线缺数据：{base['missing']}（记为 None，不当作 0）")
    if passed:
        lines.append(f"- 低于 1.0 的保留率：{', '.join(passed)}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""07 包指标：模板合规 + 编译诊断 + 构建清单。

  python metrics.py --out_dir out
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(d):
    d = Path(d)
    tf = json.loads((d / "texfit.json").read_text(encoding="utf-8")) if (d / "texfit.json").exists() else {}
    lg = json.loads((d / "logdiag.json").read_text(encoding="utf-8")) if (d / "logdiag.json").exists() else {}
    bm = json.loads((d / "build_manifest.json").read_text(encoding="utf-8")) if (d / "build_manifest.json").exists() else {}
    has_tf = bool(tf)
    return {
        # 没有 texfit.json 说明这一侧没做静态体检（如裸编译基线），记 None 而非 0，
        # 否则"0 违规"会被误读成"体检通过"。
        "template_violations": len(tf.get("violations") or []) if has_tf else None,
        "rules_hit": len(tf.get("counts") or {}) if has_tf else None,
        "errors": len(lg.get("errors") or []),
        "warnings": lg.get("warning_count", 0),
        "converged": bool(lg.get("converged", False)),
        "build_status": bm.get("status", "no_manifest"),
        "rounds": bm.get("rounds", 0),
        "bibtex_runs": bm.get("bibtex_runs", 0),
        "pages": bm.get("pages"),
        # 只有 success（errors=0 且不再需要重编且 PDF 存在）才算通过；
        # partial = 有 PDF 但引文/交叉引用未收敛，不算 pass。
        "pass": has_tf and bool(tf.get("pass")) and bm.get("status") == "success"
        and bool(bm.get("converged")) and (len(lg.get("errors") or []) == 0),
    }


ROWS = [("模板违规", "template_violations"), ("命中规则", "rules_hit"), ("编译错误", "errors"),
        ("编译警告", "warnings"), ("收敛", "converged"), ("构建状态", "build_status"),
        ("编译轮次", "rounds"), ("bib 处理次数", "bibtex_runs"), ("页数", "pages")]


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
        for name, k in ROWS:
            md.append("| %s | %s | %s | %s |" % (name, s[k], b[k], round(s[k] - b[k], 4) if isinstance(s[k], (int, float)) and isinstance(b[k], (int, float)) else "—"))
    else:
        for name, k in ROWS:
            md.append("| %s | %s | — | — |" % (name, s[k]))
    print("\n".join(md))


if __name__ == "__main__":
    main()

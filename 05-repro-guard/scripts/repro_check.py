#!/usr/bin/env python3
"""复现清单九项 + 步骤四要素核对。

  python repro_check.py --manifest manifest.json --steps steps.json --params params.csv --out out
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

COND_WORDS = ["压力", "温度", "规模", "分辨率", "样本", "范围", "条件", "场景", "仅", "低于", "高于", "少于", "大于", "当"]
FAIL_WORDS = ["失效", "不可用", "不适用", "无法", "退化", "波动", "偏差", "溢出", "超出", "误差", "发散", "不可复现",
              "无法复现", "不成立", "需复核", "偏差增大", "精度下降"]
# 不带数值但点名了具体失效机制的说法（SKILL §5 让作者写的「未固定种子 → 结果不可逐位复现」就属这类）
MECH_FAIL = ["不可逐位复现", "无法逐位复现", "不可复现", "无法复现", "不可重现", "逐位复现",
             "发散", "溢出", "结果不可比", "不可比"]


def limitation_is_specific(x: str) -> bool:
    """SKILL §4：每条限制要落到"条件/阈值 + 失效场景"，只含关键词的套话不算。

    判据二选一：(a) 句内有具体数值，且同时点名条件或失效方式；(b) 无数字但点名了具体失效机制
    （"随机种子未固定，结果不可逐位复现"）。只出现"规模/条件/失效"这类泛词而无数值、无机制 → vague。
    """
    if any(m in x for m in MECH_FAIL):
        return True
    if not any(ch.isdigit() for ch in x):
        return False
    return any(w in x for w in COND_WORDS) or any(w in x for w in FAIL_WORDS)


def nonempty(v):
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple)):
        return all(nonempty(x) for x in v) and len(v) > 0
    if isinstance(v, dict):
        return all(nonempty(x) for x in v.values()) and len(v) > 0
    return v is not None


def src_lookup(files, keys, numeric=False):
    """在来源文件里找某个键的值（config 键值 / 日志报告值），用于清单交叉核对。"""
    import re
    out = None
    for f in files or []:
        p = Path(f)
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for k in keys:
                mm = re.search(rf"[\"']?{re.escape(k)}[\"']?\s*[:=]\s*([^\s,#]+)", line)
                if mm:
                    out = out or (mm.group(1), f"{p.name}:{i}")
    return out


def same_val(x, y, numeric=False):
    if numeric:
        try:
            return abs(float(str(x)) - float(str(y))) <= 1e-12 * max(1.0, abs(float(str(y))))
        except ValueError:
            return False
    return str(x).strip().lower() == str(y).strip().lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sources", nargs="*", default=[])
    ap.add_argument("--draft", default=None)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()

    m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    st = json.loads(Path(a.steps).read_text(encoding="utf-8"))["steps"]
    with open(a.params, encoding="utf-8") as f:
        prows = list(csv.DictReader(f))

    checks = {
        "code_version": m.get("code_version"),
        "environment": m.get("env"),
        "dependencies": m.get("deps"),
        "hardware": m.get("hardware"),
        "data_access": (m.get("data") or {}).get("access"),
        "data_version_split": [(m.get("data") or {}).get("name"), (m.get("data") or {}).get("version"),
                               (m.get("data") or {}).get("split")],
        "seed": (m.get("data") or {}).get("seed"),
        "command": m.get("command"),
        "runtime": m.get("runtime"),
    }
    missing = [k for k, v in checks.items() if not nonempty(v)]

    bad_steps = []
    for s in st:
        lack = [k for k in ("input", "operation", "output", "decision") if not nonempty(s.get(k))]
        if lack:
            bad_steps.append({"step": s.get("id"), "name": s.get("name"), "lack": lack})

    limits = m.get("limitations") or []
    vague = [x for x in limits if not limitation_is_specific(x)]

    unsourced = [r for r in prows if r.get("status") != "sourced"]

    # 清单自洽：manifest 里的 seed 必须与正文/配置溯源出的 seed 一致（字段非空不等于说对了）
    seed_mismatch = None
    mseed = (m.get("data") or {}).get("seed")
    prow_seed = next((r for r in prows if (r.get("key") or "").lower() == "seed"), None)
    if prow_seed and nonempty(mseed):
        try:
            mv, pv = float(str(mseed)), float(str(prow_seed.get("value")))
            if abs(mv - pv) > 1e-12 * max(1.0, abs(pv)):
                seed_mismatch = {"manifest": str(mseed), "params": prow_seed.get("value"),
                                 "locator": prow_seed.get("source_locator")}
        except ValueError:
            if str(mseed).strip().lower() != str(prow_seed.get("value")).strip().lower():
                seed_mismatch = {"manifest": str(mseed), "params": prow_seed.get("value"),
                                 "locator": prow_seed.get("source_locator")}
    # 另外三项可比的清单字段也要与来源/正文交叉核对（同样只查非空会把自相矛盾的清单放行）
    xchecks = []
    mv_ver = (m.get("data") or {}).get("version")
    src_ver = src_lookup(a.sources, ["data_version", "dataset_version", "version"])
    if nonempty(mv_ver) and src_ver and not same_val(mv_ver, src_ver[0]):
        xchecks.append({"type": "manifest_version_conflict",
                        "detail": f"manifest data.version={mv_ver}，来源 {src_ver[0]}（{src_ver[1]}）"})
    mv_rounds = (m.get("runtime") or {}).get("rounds")
    src_rounds = src_lookup(a.sources, ["epochs", "num_epochs", "rounds", "max_epochs"])
    if nonempty(mv_rounds) and src_rounds and not same_val(mv_rounds, src_rounds[0], numeric=True):
        xchecks.append({"type": "manifest_rounds_conflict",
                        "detail": f"manifest runtime.rounds={mv_rounds}，来源 {src_rounds[0]}（{src_rounds[1]}）"})
    mv_split = (m.get("data") or {}).get("split")
    if nonempty(mv_split) and a.draft:
        dp = Path(a.draft)
        if dp.exists():
            found = re.search(r"\b\d+\s*:\s*\d+\s*:\s*\d+\b", dp.read_text(encoding="utf-8"))
            if found and not same_val(str(mv_split).replace(" ", ""), found.group(0).replace(" ", "")):
                xchecks.append({"type": "manifest_split_conflict",
                                "detail": f"manifest split={mv_split}，正文为 {found.group(0)}"})

    rates = {
        "repro_coverage": round((9 - len(missing)) / 9, 4),
        "step_completeness": round((len(st) - len(bad_steps)) / max(1, len(st)), 4) if st else None,
        "limitation_specificity": round((len(limits) - len(vague)) / len(limits), 4) if limits else None,
        "unsourced_params": len(unsourced),
    }
    viol = [{"type": "repro_field_missing", "detail": k} for k in missing]
    viol += [{"type": "step_incomplete", "detail": f"步骤 {b['step']} 缺 {b['lack']}"} for b in bad_steps]
    viol += [{"type": "limitation_vague", "detail": x} for x in vague]
    viol += [{"type": "param_not_sourced", "detail": f"{r['key']}={r['value']}"} for r in unsourced]
    if seed_mismatch:
        viol.append({"type": "manifest_seed_conflict",
                     "detail": f"manifest seed={seed_mismatch['manifest']}，正文/来源 seed={seed_mismatch['params']}"
                               f"（{seed_mismatch['locator']}）"})
    viol += xchecks
    if not limits:
        viol.append({"type": "limitation_missing", "detail": "manifest 没有 limitations：无法证明作者知道方法边界"})
    if not st:
        viol.append({"type": "step_missing", "detail": "steps 为空"})

    # pass 显式比对每一条门槛，不让空集或 0.0 混过去
    gates = {
        "repro_coverage": 1.0,
        "step_completeness": 1.0,
        "limitation_specificity": 1.0,
        "unsourced_params": 0,
    }
    failed_gates = [k for k, v in gates.items() if rates[k] is None or rates[k] < v]
    report = {"rates": rates, "missing": missing, "bad_steps": bad_steps, "vague_limits": vague,
              "seed_consistency": (None if not prow_seed else (False if seed_mismatch else True)),
              "manifest_cross_checks": len(xchecks),
              "failed_gates": failed_gates,
              "pass": not viol and not failed_gates, "violations": viol}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "repro.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    def p(x):
        return "—" if x is None else f"{x:.2%}"
    lines = ["# 复现核对", "", f"- 复现九项覆盖 {p(rates['repro_coverage'])}；缺: {', '.join(missing) or '无'}",
             f"- 步骤四要素完整率 {p(rates['step_completeness'])}",
             f"- 限制条件具体率 {p(rates['limitation_specificity'])}（无 limitations 记 —，直接卡 pass）",
             f"- 未溯源参数 {rates['unsourced_params']} 个",
             f"- 清单 seed 与来源一致：{'未核对（无 seed 行）' if not prow_seed else ('是' if not seed_mismatch else '否')}", ""]
    if viol:
        lines += ["| 类型 | 说明 |", "|---|---|"] + [f"| {v['type']} | {v['detail']} |" for v in viol]
    (out / "repro.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], **rates, "violations": len(viol)}, ensure_ascii=False))
    if not a.no_fail and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


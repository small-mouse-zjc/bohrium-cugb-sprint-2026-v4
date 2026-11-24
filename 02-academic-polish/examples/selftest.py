#!/usr/bin/env python3
"""02 自检：正例 + 七类缺陷注入 + 术语 + 平台入口 + 降级 + 基线 + 缺数据容错。

  python examples/selftest.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fact_ledger  # noqa: E402
import polish  # noqa: E402
import term_check  # noqa: E402

DEMO = ROOT / "examples" / "demo"
PY = sys.executable


def run(cmd, cwd=ROOT):
    return subprocess.run([str(x) for x in cmd], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def codes(report):
    return {b["type"] for b in report["blocking"]}


def main():
    case = load(DEMO / "case.json")
    original = case["text"]
    polished, changes, unchanged = polish.polish_text(original)
    good = fact_ledger.audit(original, polished, changes)
    ok = []

    # 1 正例
    assert good["pass"] and good["rates"]["number_retention"] == 1.0, good["rates"]
    assert all(c["original"].strip() in original for c in changes), changes
    ok.append(f"正例：推测语气/数字/单位/引用/否定全守恒，改动 {len(changes)} 条均可回指原文，"
              f"未改动 {len(unchanged)} 句显式列出")

    # 2 数字单位被改：3.5 wt% → 3.5%
    rep = fact_ledger.audit(original, polished.replace("3.5 wt%", "3.5%"), changes)
    assert "number_or_unit_loss" in codes(rep), rep["blocking"]
    ok.append("D1 单位丢失（3.5 wt%→3.5%）→ number_or_unit_loss")

    # 3 凭空加引用
    rep = fact_ledger.audit(original, polished.replace("to salinity.", "to salinity [7]."), changes)
    assert "citation_added" in codes(rep), rep["blocking"]
    ok.append("D2 编造引用 [7] → citation_added")

    # 4 推测改断言
    bad = polished.replace("may form", "proves formation of").replace("may increase", "proves an increase in")
    rep = fact_ledger.audit(original, bad, changes)
    assert {"hedge_loss", "strength_upgrade"} <= codes(rep), rep["blocking"]
    ok.append("D3 may→proves → hedge_loss + strength_upgrade")

    # 5 否定反写
    rep = fact_ledger.audit(original, polished.replace("did not observe", "observed"), changes)
    assert "negation_flip" in codes(rep), rep["blocking"]
    ok.append("D4 did not observe→observed → negation_flip")

    # 6 改了事实却不声明
    changes6 = json.loads(json.dumps(changes))
    changes6[0]["revised"] = changes6[0]["revised"].replace("25 samples", "30 samples")
    rep = fact_ledger.audit(original, polished.replace("25 samples", "30 samples"), changes6)
    assert "undeclared_fact_change" in codes(rep), rep["blocking"]
    ok.append("D5 改动 25→30 未声明 → undeclared_fact_change")

    # 7 无记录的新句子
    rep = fact_ledger.audit(original, polished + " This mechanism is well known in the literature.", changes)
    assert "unlogged_new_sentence" in codes(rep), rep["blocking"]
    ok.append("D6 凭空加句 → unlogged_new_sentence")

    # 8 术语变体
    t = term_check.check(case["terms"],
                         polished.replace("dissociation pressure", "disassociation pressure", 1))
    assert t["violations"] and t["rates"]["term_consistency"] < 1.0, t
    ok.append("D7 术语变体 disassociation pressure → T01 + 一致率<1")

    tmp = Path(tempfile.mkdtemp(prefix="t02-"))
    try:
        # 9 平台入口：无 LLM 稿时用最小编辑引擎
        o1 = tmp / "out_min"
        run([PY, ROOT / "scripts/run.py", "--input", DEMO, "--output", o1])
        rj = load(o1 / "result.json")
        assert rj["status"] == "success" and rj["metrics"]["pass"] is True, rj
        assert (o1 / "audit.json").exists() and (o1 / "diff_audit.md").exists()
        ok.append("平台入口：case.json→result.json（minimal-edit 模式），status=success，台账落盘")

        # 10 LLM 稿模式：审计而非改写
        c2 = dict(case, polished_text=polished, changes=changes)
        d2 = tmp / "in_llm"; d2.mkdir()
        (d2 / "case.json").write_text(json.dumps(c2, ensure_ascii=False), encoding="utf-8")
        o2 = tmp / "out_llm"
        run([PY, ROOT / "scripts/run.py", "--input", d2, "--output", o2])
        rj2 = load(o2 / "result.json")
        assert rj2["status"] == "success" and load(o2 / "audit.json")["mode"] == "llm", rj2
        ok.append("LLM 稿模式：polished_text 只审计不改写，mode=llm")

        # 11 降级路径
        d3 = tmp / "in_empty"; d3.mkdir()
        (d3 / "case.json").write_text(json.dumps({"case_id": "e"}), encoding="utf-8")
        run([PY, ROOT / "scripts/run.py", "--input", d3, "--output", tmp / "out_empty"])
        assert load(tmp / "out_empty" / "result.json")["status"] == "cannot_determine"
        run([PY, ROOT / "scripts/run.py", "--input", tmp / "nope", "--output", tmp / "out_no"])
        assert load(tmp / "out_no" / "result.json")["status"] == "rejected"
        ok.append("降级：无正文→cannot_determine；缺 case.json→rejected")

        # 12 基线对照
        base = tmp / "base"
        run([PY, ROOT / "examples/baseline.py", "--case", DEMO / "case.json", "--out", base])
        m = run([PY, ROOT / "eval/metrics.py", "--out_dir", o1, "--base_dir", base])
        md = json.loads(m.stdout.splitlines()[0])
        assert md["skill"]["pass"] is True and md["base"]["pass"] is False, md
        assert md["delta"]["citation_retention"] == 1.0 and md["delta"]["hedge_retention"] == 1.0, md["delta"]
        assert md["delta"]["negation_retention"] == 1.0 and md["pass_gap"] is True, md
        ok.append("基线对照：引用/限定/否定保留率 1.0 vs 0.0、number 1.0 vs 0.857、pass_gap=true")

        # 13 缺 result.json 的基线：记 None 不崩
        empty = tmp / "base_empty"; empty.mkdir()
        m2 = run([PY, ROOT / "eval/metrics.py", "--out_dir", o1, "--base_dir", empty])
        assert "Traceback" not in m2.stderr, m2.stderr[-300:]
        md2 = json.loads(m2.stdout.splitlines()[0])
        assert md2["base"]["number_retention"] is None and md2["base"]["missing"], md2["base"]
        ok.append("缺基线 result.json：记 None 不崩溃")

        # 14 零事实草稿：保留率记 None
        d4 = tmp / "in_plain"; d4.mkdir()
        (d4 / "case.json").write_text(json.dumps(
            {"case_id": "plain", "text": "This paragraph has no numbers or citations at all."}),
            encoding="utf-8")
        run([PY, ROOT / "scripts/run.py", "--input", d4, "--output", tmp / "out_plain"])
        rj4 = load(tmp / "out_plain" / "result.json")
        assert rj4["metrics"]["number_retention"] is None, rj4["metrics"]
        ok.append("零事实草稿：number_retention=None（不把没数据记成 1.0）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("02 SELFTEST OK")
    for line in ok:
        print("  ✓ " + line)


if __name__ == "__main__":
    main()

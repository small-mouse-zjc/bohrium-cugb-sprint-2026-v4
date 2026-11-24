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
    assert {"number_or_unit_loss", "unit_change"} & codes(rep), rep["blocking"]
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

    # 6b 条目级只删情态词（无数字/引用变化）也必须申报：Salinity may→Salinity raises
    ch6b = [{"original": "Salinity may raise pressure.", "revised": "Salinity raises pressure.",
             "reason": "精简", "fact_changed": False}]
    rep = fact_ledger.audit("Salinity may raise pressure.", "Salinity raises pressure.", ch6b)
    assert "undeclared_fact_change" in codes(rep), rep["blocking"]
    assert "hedge_loss" in codes(rep), rep["blocking"]
    ok.append("D5b 条目级删 may 却声明 fact_changed=false → F10 + hedge_loss（fact_tokens 含限定词）")

    # 6c 情态规范化（maybe can → may）不是事实变化，不许误报 F10
    ch6c = [{"original": "Gas hydrate maybe can form in sediment.", "revised": "Gas hydrate may form in sediment.",
             "reason": "情态词合并", "fact_changed": False}]
    rep = fact_ledger.audit("Gas hydrate maybe can form in sediment.", "Gas hydrate may form in sediment.", ch6c)
    assert "undeclared_fact_change" not in codes(rep), rep["blocking"]
    ok.append("D5c maybe can→may 属情态规范化，不误报 F10")

    # 7 无记录的新句子
    rep = fact_ledger.audit(original, polished + " This mechanism is well known in the literature.", changes)
    assert "unlogged_new_sentence" in codes(rep), rep["blocking"]
    ok.append("D6 凭空加句 → unlogged_new_sentence")

    # 7b 纯加强（中性句塞 clearly）：没有弱词可删，也必须报 F05
    rep = fact_ledger.audit("The hydrate layer thickens over time.",
                            "The hydrate layer clearly thickens over time.", [])
    assert "strength_upgrade" in codes(rep), rep["blocking"]
    ok.append("D6b 中性句塞 clearly（无弱词可删）→ strength_upgrade（不再只看 hedge/weak 减少）")

    # 7c "断言为常识"型升级：We observed → It is well known
    rep = fact_ledger.audit("We observed that pressure rises.",
                            "It is well known that pressure rises.", [])
    assert "strength_upgrade" in codes(rep), rep["blocking"]
    ok.append("D6c We observed→It is well known → strength_upgrade（well known 已入强断言表）")

    # 7d 强→强同义替换仍放行：proved → demonstrated
    rep = fact_ledger.audit("We proved the model at site CUG-3.",
                            "We demonstrated the model at site CUG-3.", [])
    assert "strength_upgrade" not in codes(rep), rep["blocking"]
    ok.append("D6d proved→demonstrated（强→强）仍放行，不误伤同义替换")

    # 8 术语变体
    t = term_check.check(case["terms"],
                         polished.replace("dissociation pressure", "disassociation pressure", 1))
    assert t["violations"] and t["rates"]["term_consistency"] < 1.0, t
    ok.append("D7 术语变体 disassociation pressure → T01 + 一致率<1")

    # 8b 合法归一：3.5 wt% → 3.5 wt %（空格差异）不算丢事实
    norm = polished.replace("3.5 wt%", "3.5 wt %")
    rep = fact_ledger.audit(original, norm, changes)
    assert rep["pass"], rep["blocking"]
    st = {x["token"]: x["status"] for x in rep["facts"] if x["type"] == "number_unit"}
    assert st.get("3.5 wt%") in ("kept", "normalized"), st
    ok.append("合法归一：3.5 wt% ↔ 3.5 wt % 不算丢事实（kept/normalized）")

    # 8d 程度副词被删：significantly higher → higher
    src = "The permeability is significantly higher than that of clay [3]."
    dst = "The permeability is higher than that of clay [3]."
    rep = fact_ledger.audit(src, dst, [])
    assert "intensity_loss" in codes(rep), rep["blocking"]
    assert {x["type"] for x in rep["facts"]} >= {"intensity"}, rep["facts"]
    ok.append("D9 删 significantly → intensity_loss（结论强度不能被悄悄改）")

    # 8e 引用被挪到别的句子
    src = "Salinity rises to 3.5 wt% [4]. Permeability is high [4]."
    dst = "Salinity rises to 3.5 wt%. Permeability is high [4] [4]."
    rep = fact_ledger.audit(src, dst, [])
    assert "citation_moved" in codes(rep), rep["blocking"]
    ok.append("D10 引用挪句 → citation_moved（归属变了）")

    # 8f 比较方向被翻转
    src = "The permeability is higher than that of the clay, and salinity increases with depth."
    dst = "The permeability is lower than that of the clay, and salinity increases with depth."
    rep = fact_ledger.audit(src, dst, [])
    assert "comparative_loss" in codes(rep), rep["blocking"]
    ok.append("D11 higher than → lower than → comparative_loss（F07 回归）")

    # 8g 数值也变的单位换算：0.9 MPa → 900 kPa
    src = "The dissociation pressure is 0.9 MPa at 4 °C."
    dst = "The dissociation pressure is 900 kPa at 4 °C."
    rep = fact_ledger.audit(src, dst, [])
    assert "unit_conversion" in codes(rep), rep["blocking"]
    assert "number_added" not in codes(rep), rep["blocking"]
    ok.append("D12 0.9 MPa→900 kPa → unit_conversion（不误判为编造数字）")

    # 8h 凭空加强程度副词
    src = "The hydrate stability zone is deeper than predicted."
    dst = "The hydrate stability zone is significantly deeper than predicted."
    rep = fact_ledger.audit(src, dst, [])
    assert "intensity_added" in codes(rep), rep["blocking"]
    ok.append("D13 凭空加 significantly → intensity_added（结论强度被抬高）")

    # 8i 限定词紧跟标点：旧实现靠两侧空格计数，会整类漏检
    src = "The result may, however, be wrong under high salinity."
    dst = "The result, however, be wrong under high salinity."
    rep = fact_ledger.audit(src, dst, [])
    assert "hedge_loss" in codes(rep), rep["blocking"]
    ok.append("D14 删「may,」（逗号紧跟）→ hedge_loss（边界计数修正）")

    # 8j 否定词紧跟逗号
    src = "This is not, in fact, proven by the data."
    dst = "This is, in fact, proven by the data."
    rep = fact_ledger.audit(src, dst, [])
    assert "negation_flip" in codes(rep), rep["blocking"]
    ok.append("D15 删「not,」（逗号紧跟）→ negation_flip")

    # 8k 无 hedge 的强弱升级：found → proved
    src = "We found that the permeability increases with depth."
    dst = "We proved that the permeability increases with depth."
    rep = fact_ledger.audit(src, dst, [])
    assert "strength_upgrade" in codes(rep), rep["blocking"]
    ok.append("D16 found→proved（原文无 hedge）→ strength_upgrade，不再静默放行")

    # 8l 强→强同义替换是合法润色，不能误判升级
    rep = fact_ledger.audit("This proves the result.", "This demonstrates the result.", [])
    assert "strength_upgrade" not in codes(rep), rep["blocking"]
    ok.append("D17 proves→demonstrates（强→强同义）→ 不报 strength_upgrade，pass 放行")

    # 8m 两句近义源句删掉一句：不能被同一润色句"顶替"
    src = ("This result is consistent with previous work. "
           "This result is also consistent with earlier studies.")
    dst = "This result is consistent with previous work."
    rep = fact_ledger.audit(src, dst, [])
    assert "sentence_dropped" in codes(rep), rep["blocking"]
    ok.append("D18 近义双句删一句 → sentence_dropped（一对一匹配，不再被顶替）")

    # 8n 两句合法合并成一句：不能被当成整句丢失
    src = ("The hydrate forms in marine sediment. "
           "The hydrate is stable at low temperature.")
    dst = "The hydrate forms in marine sediment and is stable at low temperature."
    rep = fact_ledger.audit(src, dst, [])
    assert "sentence_dropped" not in codes(rep), rep["blocking"]
    assert any(a["type"] == "sentence_merged" for a in rep["advisory"]), rep["advisory"]
    ok.append("D19 两句合并为一句 → A02 sentence_merged，不误判 F08")

    # 8c 编造数字：原文没有 18 MPa
    rep = fact_ledger.audit(original, polished.replace("above 12 MPa", "above 18 MPa"), changes)
    assert {"number_added", "number_or_unit_loss"} & codes(rep), rep["blocking"]
    ok.append("D8 凭空改出 18 MPa → number_added / number_or_unit_loss")

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
        assert md["skill"]["fact_preservation_rate"] == 1.0, md["skill"]
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

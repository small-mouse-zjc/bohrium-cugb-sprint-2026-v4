#!/usr/bin/env python3
"""03 自检：正例 + 引用链十一类注入 + author-year + 平台入口 + 降级 + 基线 + 缺数据容错。

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
import cite_chain  # noqa: E402
import renumber  # noqa: E402

DEMO = ROOT / "examples" / "demo"
PY = sys.executable


def run(cmd):
    return subprocess.run([str(x) for x in cmd], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def codes(rep):
    return {b["code"] for b in rep["blocking"]}


def wrap(data, case_id="t"):
    return {"case_id": case_id, "status": "success", "result": data}


def main():
    case = load(DEMO / "case.json")
    good_data = renumber.renumber(case["manuscript"], case["bibliography"], "numeric")
    good = wrap(good_data)
    rep = cite_chain.audit(good, case)
    ok = []
    assert rep["pass"], rep["blocking"]
    assert rep["rates"]["citation_closure_rate"] == 1.0
    assert rep["rates"]["metadata_verbatim_rate"] == 1.0
    assert rep["rates"]["claim_map_coverage"] == 1.0
    assert good_data["merged_ids"] == ["3"], good_data["merged_ids"]
    assert len(good_data["bibliography"]) == 3, good_data["bibliography"]
    ok.append("正例：同 DOI 重复合并（3→1）、编号按首次出现重排为 1..3、元数据逐字保留、"
              "claim 映射全覆盖、未引用条目录入 unused")

    bad = json.loads(json.dumps(good))
    bad["result"]["editable_manuscript"] += " Another claim [9]."
    assert "C01" in codes(cite_chain.audit(bad, case))
    ok.append("C01 正文 [9] 文献表没有 → dangling_citation")

    bad = json.loads(json.dumps(good))
    bad["result"]["bibliography"][2]["id"] = "5"
    bad["result"]["editable_manuscript"] = bad["result"]["editable_manuscript"].replace("[3]", "[5]")
    assert "C02" in codes(cite_chain.audit(bad, case))
    ok.append("C02 编号 1,2,5 → numbering_gap")

    bad = json.loads(json.dumps(good))
    bad["result"]["editable_manuscript"] = ("Gas hydrate occurs [2]. Salinity raises pressure [1]. "
                                            "Permeability is high [3]. Again [2].")
    assert "C03" in codes(cite_chain.audit(bad, case))
    ok.append("C03 首次出现是 2→1 → order_mismatch")

    bad = json.loads(json.dumps(good))
    bad["result"]["bibliography"].append(dict(bad["result"]["bibliography"][0], id="4", key="smith2020b"))
    assert "C04" in codes(cite_chain.audit(bad, case))
    ok.append("C04 同作者同年的重复条目残留 → duplicate_left")

    bad = json.loads(json.dumps(good))
    bad["result"]["bibliography"][1]["key"] = bad["result"]["bibliography"][0]["key"]
    assert "C05" in codes(cite_chain.audit(bad, case))
    ok.append("C05 两条文献同 key → key_collision")

    bad = json.loads(json.dumps(good))
    bad["result"]["number_mapping"][1]["bib_id"] = "1"
    assert "C06" in codes(cite_chain.audit(bad, case))
    ok.append("C06 mapping bib_id 指错 → mapping_mismatch")

    bad = json.loads(json.dumps(good))
    bad["result"]["bibliography"].append({"id": "4", "key": "fake2024", "author": "Nobody A.",
                                          "year": "2024", "title": "An invented paper",
                                          "source": "Fake Journal", "doi": "10.9999/fake"})
    bad["result"]["editable_manuscript"] += " Invented claim [4]."
    assert "C07" in codes(cite_chain.audit(bad, case))
    ok.append("C07 文献表凭空多一条 → fabricated_entry")

    bad = json.loads(json.dumps(good))
    bad["result"]["bibliography"][2]["doi"] = "10.0000/unknown.4"
    assert "C08" in codes(cite_chain.audit(bad, case))
    ok.append("C08 原始来源缺 DOI 却补占位值 → fabricated_field")

    bad = json.loads(json.dumps(good))
    bad["result"]["bibliography"][0]["volume"] = None
    assert "C09" in codes(cite_chain.audit(bad, case))
    ok.append("C09 原始有 volume 输出却删空 → metadata_loss")

    bib10 = [dict(case["bibliography"][1], id="1", key="li2019"),
             dict(case["bibliography"][4], id="2", key="li2019c")]
    data10 = {"editable_manuscript": "Salinity raises pressure [1].",
              "bibliography": [dict(bib10[0], cited=True)],
              "number_mapping": [{"citation": "[1]", "key": "li2019", "bib_id": "1"}],
              "claim_source_map": [{"claim": "Salinity raises pressure [1].", "source_ids": ["1"],
                                    "source_keys": ["li2019"]}],
              "merged_ids": ["2"], "style": "numeric"}
    rep10 = cite_chain.audit(wrap(data10), {"bibliography": bib10})
    assert "C10" in codes(rep10), rep10["blocking"]
    ok.append("C10 DOI 不同却被并成一条 → merge_conflict")

    bad = json.loads(json.dumps(good))
    bad["result"]["claim_source_map"] = bad["result"]["claim_source_map"][:2]
    assert "C11" in codes(cite_chain.audit(bad, case))
    ok.append("C11 只映射前两句 → claim_map_gap")

    # C12 重排后编号指向另一篇论文（编号在、条目在，但身份变了）
    bad = json.loads(json.dumps(good))
    bad["result"]["number_mapping"][1]["from_id"] = "2"
    bad["result"]["number_mapping"][1]["key"] = "chen2022"
    bad["result"]["bibliography"][1] = dict(bad["result"]["bibliography"][2], id="2", key="chen2022")
    bad["result"]["bibliography"][2] = dict(case["bibliography"][1], id="3", key="li2019", cited=True)
    rep12 = cite_chain.audit(bad, case)
    assert "C12" in codes(rep12), rep12["blocking"]
    ok.append("C12 [2] 重排后指向 chen2022 → renumber_mismatch（保序双射被破坏）")

    # C13 DOI 双前缀
    bad = json.loads(json.dumps(good))
    bad["result"]["bibliography"][0]["doi"] = "urn:doi:urn:doi:10.1000/a1"
    assert "C13" in codes(cite_chain.audit(bad, case))
    ok.append("C13 urn:doi:urn:doi: 双前缀 → doi_format")

    # 身份保持率：删掉第 2 条被引条目后，正文 [3] 的引用不能悄悄指向第 2 条的原论文
    bib_del = [b for b in case["bibliography"] if str(b["id"]) != "2"]
    ms_del = case["manuscript"].replace("[2]", "[9]")
    data_del = renumber.renumber(ms_del, bib_del, "numeric")
    rep_del = cite_chain.audit(wrap(data_del, "del"), {"bibliography": bib_del})
    assert rep_del["rates"]["renumber_identity_rate"] == 1.0, rep_del["rates"]
    assert any(b["type"] in ("dangling_citation",) for b in rep_del["blocking"]) or not data_del["unresolved"], rep_del
    ok.append("删条后重排：身份保持率 1.0，未解析引用原样保留不冒充")

    ay_case = {"case_id": "ay", "style": "author-year", "bibliography": case["bibliography"][:2]}
    ay_ms = "Gas hydrate occurs at CUG-3 (Smith et al., 2020). Salinity raises pressure (Li, 2019)."
    ay = renumber.renumber(ay_ms, ay_case["bibliography"], "author-year")
    ay_rep = cite_chain.audit(wrap(ay, "ay"), ay_case)
    assert ay_rep["pass"], ay_rep["blocking"]
    assert ay["editable_manuscript"].count("(Smith") == 1
    ok.append("author-year：正文与文献表按 作者+年份 对齐，重写后仍可审计")

    tmp = Path(tempfile.mkdtemp(prefix="t03-"))
    try:
        o1 = tmp / "out"
        run([PY, ROOT / "scripts/run.py", "--input", DEMO, "--output", o1])
        rj = load(o1 / "result.json")
        assert rj["status"] == "success" and rj["metrics"]["pass"] is True, rj["notes"]
        assert (o1 / "manuscript.md").exists() and (o1 / "bibliography.json").exists()
        ok.append("平台入口：case.json→result.json（engine 模式），status=success，正文与文献表落盘")

        c2 = dict(case, result=good["result"])
        d2 = tmp / "in_llm"; d2.mkdir()
        (d2 / "case.json").write_text(json.dumps(c2, ensure_ascii=False), encoding="utf-8")
        o2 = tmp / "out_llm"
        run([PY, ROOT / "scripts/run.py", "--input", d2, "--output", o2])
        rj2 = load(o2 / "result.json")
        assert rj2["status"] == "success" and rj2["metrics"]["mode"] == "llm", rj2["metrics"]
        ok.append("LLM 结果模式：result 直通只审计，mode=llm")

        d3 = tmp / "in_no_ms"; d3.mkdir()
        (d3 / "case.json").write_text(json.dumps({"case_id": "e", "bibliography": case["bibliography"]}),
                                      encoding="utf-8")
        run([PY, ROOT / "scripts/run.py", "--input", d3, "--output", tmp / "out_no_ms"])
        assert load(tmp / "out_no_ms" / "result.json")["status"] == "cannot_determine"
        d4 = tmp / "in_no_bib"; d4.mkdir()
        (d4 / "case.json").write_text(json.dumps({"case_id": "e", "manuscript": case["manuscript"]}),
                                      encoding="utf-8")
        run([PY, ROOT / "scripts/run.py", "--input", d4, "--output", tmp / "out_no_bib"])
        assert load(tmp / "out_no_bib" / "result.json")["status"] == "cannot_determine"
        run([PY, ROOT / "scripts/run.py", "--input", tmp / "nope", "--output", tmp / "out_none"])
        assert load(tmp / "out_none" / "result.json")["status"] == "rejected"
        ok.append("降级：无正文/无文献表→cannot_determine；缺 case.json→rejected")

        base = tmp / "base"
        run([PY, ROOT / "examples/baseline.py", "--case", DEMO / "case.json", "--out", base])
        m = run([PY, ROOT / "eval/metrics.py", "--out_dir", o1, "--base_dir", base])
        md = json.loads(m.stdout.splitlines()[0])
        assert md["skill"]["citation_closure_rate"] == 1.0 and md["skill"]["claim_map_coverage"] == 1.0, md
        assert md["base"]["claim_map_coverage"] == 0.0 and md["base"]["metadata_verbatim_rate"] < 1.0, md["base"]
        ok.append(f"基线对照：claim 覆盖 1.0 vs 0.0、元数据逐字率 1.0 vs {md['base']['metadata_verbatim_rate']:.4f}")

        empty = tmp / "base_empty"; empty.mkdir()
        m2 = run([PY, ROOT / "eval/metrics.py", "--out_dir", o1, "--base_dir", empty])
        assert "Traceback" not in m2.stderr, m2.stderr[-300:]
        md2 = json.loads(m2.stdout.splitlines()[0])
        assert md2["base"]["metadata_verbatim_rate"] is None and md2["base"]["missing"], md2["base"]
        ok.append("缺基线 result.json：记 None 不崩溃")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("03 SELFTEST OK")
    for line in ok:
        print("  ✓ " + line)


if __name__ == "__main__":
    main()

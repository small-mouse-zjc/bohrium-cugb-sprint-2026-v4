#!/usr/bin/env python3
"""10 包自检：两篇构造材料归一 + 证据绑定 + 四查询真执行；五类缺陷必须命中。"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
DEMO = ROOT / "examples/demo"


def run(args, rc=(0, 1)):
    r = subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode not in rc:
        raise AssertionError(f"rc={r.returncode} {' '.join(map(str,args))}\n{r.stderr[-700:]}")
    return r


def build_case(tmp, name, corpus, relations, queries):
    d = tmp / name
    cp, rp, qp = d / "corpus.json", d / "relations.json", d / "queries.json"
    d.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    rp.write_text(json.dumps(relations, ensure_ascii=False), encoding="utf-8")
    qp.write_text(json.dumps(queries, ensure_ascii=False), encoding="utf-8")
    out = d / "out"
    run([ROOT / "scripts/kg.py", "build", "--corpus", cp, "--relations", rp,
         "--queries", qp, "--out", out, "--no-fail"])
    v = json.loads((out / "validation.json").read_text(encoding="utf-8"))
    kg = json.loads((out / "kg.json").read_text(encoding="utf-8"))
    qs = json.loads((out / "queries_result.json").read_text(encoding="utf-8"))
    return v, kg, qs


def codes(v):
    return {x["code"] for x in v["violations"]}


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_10_"))
    ok = []
    base = json.loads((DEMO / "corpus.json").read_text(encoding="utf-8"))
    rel = json.loads((DEMO / "relations.json").read_text(encoding="utf-8"))
    qy = json.loads((DEMO / "queries.json").read_text(encoding="utf-8"))
    try:
        v, kg, qs = build_case(tmp, "base", base, rel, qy)
        assert v["pass"], v["violations"]
        gh = [n for n in kg["nodes"] if n["key"] == "gas hydrate"]
        assert len(gh) == 1 and {m["paper_id"] for m in gh[0]["mentions"]} == {"P1", "P2"}
        assert len(kg["non_merge"]) == 1 and kg["non_merge"][0]["key"] == "sediment sample"
        assert all(len(x["evidence"]) > 0 for x in qs), [x["id"] for x in qs if not x["evidence"]]
        assert v["rates"]["query_provenance_rate"] == 1.0
        ok.append("正例：GH/gas hydrate 跨两篇归一；1 条非合并判定带双篇证据；4 查询全部有证据")

        # D1 大小写/连字符变体必须归一，不得裂成两节点
        c1 = copy.deepcopy(base)
        for p in c1["papers"]:
            if p["paper_id"] == "P2":
                for m in p["mentions"]:
                    if m["surface"] == "gas hydrate":
                        m["surface"] = "Gas-Hydrate"
        v1, kg1, _ = build_case(tmp, "D1", c1, rel, qy)
        gh1 = [n for n in kg1["nodes"] if n["key"] == "gas hydrate"]
        assert len(gh1) == 1, f"变体未归一，节点数={len(gh1)}"
        assert "K01" not in codes(v1)
        ok.append("D1_case_hyphen_variant → 仍 1 个 gas hydrate 节点（未触发 K01）")

        # D2 同名不同场地：必须保留为不同节点，绝不能合并
        c2 = copy.deepcopy(base)
        c2["papers"][0]["mentions"].append(
            {"surface": "sediment sample", "type": "material", "paragraph_id": "JATS-3",
             "quote": "Permeability of the sandy layer is one order of magnitude higher than that of the clay at site CUG-3.",
             "attrs": {"site": "CUG-4"}})
        v2, kg2, _ = build_case(tmp, "D2", c2, rel, qy)
        bad = [n for n in kg2["nodes"]
               if len({m["attrs"]["site"] for m in n["mentions"] if "site" in m.get("attrs", {})}) > 1]
        assert not bad, f"冲突场地被并入同一节点：{[n['id'] for n in bad]}"
        ss = [n for n in kg2["nodes"] if n["key"] == "sediment sample"]
        assert len(ss) >= 3, f"同名不同场地未拆分，节点数={len(ss)}"
        assert "K02" not in codes(v2)
        ok.append("D2_same_name_diff_site → 拆为 3 个节点，无冲突字段合并（K02 未触发）")

        # D3 引文改写 → 边不得成立
        r3 = copy.deepcopy(rel)
        r3["relations"][1]["quote"] = "Dissociation pressure decreases with salinity"
        v3, kg3, _ = build_case(tmp, "D3", base, r3, qy)
        assert "K03" in codes(v3), codes(v3)
        assert len(kg3["edges"]) == 5
        ok.append("D3_paraphrased_quote → K03，边数 6→5")

        # D4 查询无结果 → 必须报空而不是编造
        q4 = copy.deepcopy(qy)
        q4["queries"].append({"id": "Q5", "kind": "edges", "predicate": "supports",
                              "question": "有没有 supports 关系？"})
        v4, _, qs4 = build_case(tmp, "D4", base, rel, q4)
        assert any(x["code"] == "K04" and x.get("query") == "Q5" for x in v4["violations"]), v4["violations"]
        q5 = [x for x in qs4 if x["id"] == "Q5"][0]
        assert q5["count"] == 0 and q5["evidence"] == []
        ok.append("D4_empty_query → K04，返回空结果而非编造")

        # D5 缩写无全称 → 必须报未解析
        c5 = copy.deepcopy(base)
        c5["papers"][1]["mentions"].append(
            {"surface": "DM", "type": "method", "paragraph_id": "JATS-2",
             "quote": "Dissociation pressure of the lab hydrate increases by 0.6 MPa between 0 and 3.5 wt% salinity at 4 °C."})
        v5, _, _ = build_case(tmp, "D5", c5, rel, qy)
        assert "K05" in codes(v5), codes(v5)
        ok.append("D5_unresolved_abbr → K05")

        # D6 引文逐字但与本边无关（同段落另一句）→ K03，边不得成立
        r6 = copy.deepcopy(rel)
        r6["relations"][0]["quote"] = "Pore-water salinity is 3.5 wt% NaCl equivalent."
        v6, kg6, _ = build_case(tmp, "D6", base, r6, qy)
        assert any(x["code"] == "K03" and "subject" in (x.get("endpoints") or []) for x in v6["violations"]), v6["violations"]
        assert len(kg6["edges"]) == 5, len(kg6["edges"])
        assert v6["pass"] is False, v6
        ok.append("D6_verbatim_but_irrelevant_quote → K03（引文未含端点写法），边数 6→5")

        # D7 同篇同名多实例：按 relation 的 paragraph_id 消歧，不得静默绑到第一个
        c7 = copy.deepcopy(base)
        p2 = next(p for p in c7["papers"] if p["paper_id"] == "P2")
        p2["paragraphs"] += [
            {"paragraph_id": "JATS-9", "text": "A third sediment sample (S3) was prepared; the clay was removed before use."},
            {"paragraph_id": "JATS-10", "text": "A fourth sediment sample (S4) was prepared; the clay was removed before use."},
        ]
        p2["mentions"] += [
            {"surface": "sediment sample", "type": "material", "paragraph_id": "JATS-9",
             "quote": "A third sediment sample (S3) was prepared; the clay was removed before use.",
             "attrs": {"sample_id": "S3"}},
            {"surface": "sediment sample", "type": "material", "paragraph_id": "JATS-10",
             "quote": "A fourth sediment sample (S4) was prepared; the clay was removed before use.",
             "attrs": {"sample_id": "S4"}},
        ]
        r7 = copy.deepcopy(rel)
        r7["relations"].append({"id": "e7", "paper_id": "P2", "paragraph_id": "JATS-9",
                                "subject": "sediment sample", "predicate": "located_in", "object": "clay",
                                "quote": "A third sediment sample (S3) was prepared; the clay was removed before use."})
        v7, kg7, _ = build_case(tmp, "D7", c7, r7, qy)
        e7 = next(e for e in kg7["edges"] if e["id"] == "e7")
        node7 = next(n for n in kg7["nodes"] if n["id"] == e7["subject"])
        assert node7["attrs"].get("sample_id") == "S3", node7
        ok.append("D7_endpoint_by_paragraph → e7 的 subject 绑到 sample_id=S3（不静默取首个实例）")

        # D8 同篇同名多实例且段落也对不上 → K09 拒绝建边，不许猜
        r8 = copy.deepcopy(r7)
        r8["relations"][-1]["paragraph_id"] = "JATS-99"
        v8, kg8, _ = build_case(tmp, "D8", c7, r8, qy)
        assert "K09" in codes(v8), codes(v8)
        assert not any(e["id"] == "e7" for e in kg8["edges"]), "歧义端点仍建了边"
        ok.append("D8_ambiguous_endpoint → K09，e7 不成立（不静默 pool[0]）")

        # D9 relation 缺 paper_id → 优雅报 K06，不许 KeyError
        r9 = copy.deepcopy(rel)
        r9["relations"][0].pop("paper_id", None)
        v9, kg9, _ = build_case(tmp, "D9", base, r9, qy)
        assert any(x["code"] == "K06" and "paper_id" in x.get("detail", "") for x in v9["violations"]), v9["violations"]
        assert len(kg9["edges"]) == 5
        ok.append("D9_relation_without_paper_id → K06（缺 paper_id），无 KeyError")

        # D10 提及的引文被改写 → K10，且 quote 回退成该段真实句子
        c10 = copy.deepcopy(base)
        for m in c10["papers"][0]["mentions"]:
            if m["surface"] == "Gas hydrate" and m["paragraph_id"] == "JATS-1":
                m["quote"] = "Hydrate was found in the sea floor here."
        v10, kg10, _ = build_case(tmp, "D10", c10, rel, qy)
        assert any(x["code"] == "K10" and x.get("surface") == "Gas hydrate" for x in v10["violations"]), v10["violations"]
        gh = next(n for n in kg10["nodes"] if n["key"] == "gas hydrate")
        q10 = next(m["quote"] for m in gh["mentions"] if m["paper_id"] == "P1" and m["paragraph_id"] == "JATS-1")
        assert "Gas hydrate" in q10 and "sea floor" not in q10, q10
        assert v10["pass"] is False, v10
        ok.append("D10_paraphrased_mention_quote → K10，quote 回退为该段真实句（图谱里不留改写句）")

        # D11 非合并理由为占位 → K11；正例的作者理由 reason_source=author
        r11 = copy.deepcopy(rel)
        r11["non_merge_reasons"] = [{"key": "sediment sample", "reason": "不确定"}]
        v11, kg11, _ = build_case(tmp, "D11", base, r11, qy)
        assert "K11" in codes(v11), codes(v11)
        assert v11["pass"] is False and kg11["non_merge"][0]["reason_source"] == "auto", kg11["non_merge"]
        assert kg["non_merge"][0]["reason_source"] == "author", kg["non_merge"]
        ok.append("D11_vague_nonmerge_reason → K11；删掉人工理由后 reason_source=auto，正例为 author")

        # 平台入口：case.json → result.json
        ein, eout = tmp / "entry_in", tmp / "entry_out"
        ein.mkdir()
        for f in ("corpus.json", "relations.json", "queries.json"):
            shutil.copy(DEMO / f, ein / f)
        (ein / "case.json").write_text(json.dumps({"case_id": "demo-crosspaper-01", "corpus": "corpus.json",
                                                   "relations": "relations.json", "queries": "queries.json"},
                                                  ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/run.py", "--input", ein, "--output", eout])
        rj = json.loads((eout / "result.json").read_text(encoding="utf-8"))
        assert rj["status"] == "success" and rj["metrics"]["pass"] is True, rj
        assert rj["metrics"]["query_only_pass"] is True, rj["metrics"]
        assert (eout / "query_validation.json").exists(), "query 未独立落盘"
        ok.append("平台入口：case.json→result.json，status=success、query-only 独立跑通")

        # query 子命令必须读已建好的 kg.json，而不是重跑 build
        kgp = eout / "kg.json"
        before = kgp.stat().st_mtime_ns
        kg = json.loads(kgp.read_text(encoding="utf-8"))
        kg["nodes"][0]["label"] = "SENTINEL-LABEL"
        kgp.write_text(json.dumps(kg, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/kg.py", "query", "--corpus", ein / "corpus.json", "--relations", ein / "relations.json",
             "--queries", ein / "queries.json", "--out", eout, "--no-fail"])
        qv = json.loads((eout / "query_validation.json").read_text(encoding="utf-8"))
        assert qv.get("mode") == "query-only", qv
        kg_after = json.loads(kgp.read_text(encoding="utf-8"))
        assert kg_after["nodes"][0]["label"] == "SENTINEL-LABEL", "query 覆盖了已建图（说明是重跑 build）"
        ok.append("query 只读 kg.json：图未被重建（哨兵标签保留）")

        # 少于 3 条查询：K07 + pass=false，不许零查询照样过
        q6 = {"queries": [qy["queries"][0]]}
        v6, _, _ = build_case(tmp, "few", base, rel, q6)
        assert "K07" in codes(v6) and v6["pass"] is False, v6
        ok.append("少于 3 条查询 → K07 + pass=false")

        # 三条同类查询：kind 覆盖不足 → K08
        only_node = {"queries": [{"id": f"Q{i}", "kind": "node", "label": "salinity",
                                  "question": f"salinity 出现在哪些段落？（{i}）"} for i in (1, 2, 3)]}
        v8, _, _ = build_case(tmp, "kinds", base, rel, only_node)
        assert "K08" in codes(v8) and v8["pass"] is False, v8
        ok.append("三条都是 node 查询 → K08（kind 覆盖不足）+ pass=false")

        # 查询端必须继承构建端的别名归一：用别名/变体写法也要能查回同一节点
        qa = {"queries": [
            {"id": "Q-a1", "kind": "node", "label": "GH", "question": "缩写写法能否查回节点"},
            {"id": "Q-a2", "kind": "node", "label": "Gas-Hydrate", "question": "连字符变体能否查回节点"},
            {"id": "Q-a3", "kind": "edges", "predicate": "increases", "question": "关系查询占位"}]}
        va, kga, qsa = build_case(tmp, "alias", base, rel, qa)
        gh_id = next(n["id"] for n in kga["nodes"] if n["key"] == "gas hydrate")
        a1 = next(x for x in qsa if x["id"] == "Q-a1")
        a2 = next(x for x in qsa if x["id"] == "Q-a2")
        assert a1["found"] and a1.get("node_id") == gh_id and a1["matched_by"] == "alias", a1
        assert a2["found"] and a2.get("node_id") == gh_id, a2
        assert a1["evidence"] and a2["evidence"], (a1, a2)
        ok.append("查询端认别名：GH / Gas-Hydrate 都查回同一 gas hydrate 节点且带证据")

        # 路径查询不得把同名多实例塌缩成一个：端点候选全交出，且 ambiguous=true
        qp2 = {"queries": [
            {"id": "Q-p1", "kind": "path", "from": "sediment sample", "to": "salinity",
             "question": "同名多实例的路径查询"},
            {"id": "Q-p2", "kind": "node", "label": "gas hydrate", "question": "占位"},
            {"id": "Q-p3", "kind": "edges", "predicate": "increases", "question": "占位"}]}
        vp, kgp, qsp = build_case(tmp, "path", base, rel, qp2)
        ss_ids = {n["id"] for n in kgp["nodes"] if n["key"] == "sediment sample"}
        p1 = next(x for x in qsp if x["id"] == "Q-p1")
        assert len(ss_ids) >= 2, ss_ids
        assert set(p1["from_ids"]) == ss_ids, (p1["from_ids"], ss_ids)
        assert p1["ambiguous"] is True, p1
        ok.append("路径查询端点多实例：from_ids 含全部实例（%d 个）且 ambiguous=true，不静默取一个" % len(ss_ids))

        # cannot_determine 时 notes 不残留下游 query 噪音
        c9 = copy.deepcopy(base)
        for p in c9["papers"]:
            p["mentions"] = []
        e9 = tmp / "empty_mentions"
        e9in = e9 / "in"; e9in.mkdir(parents=True)
        for f in ("relations.json", "queries.json"):
            shutil.copy(DEMO / f, e9in / f)
        (e9in / "corpus.json").write_text(json.dumps(c9, ensure_ascii=False), encoding="utf-8")
        (e9in / "case.json").write_text(json.dumps({"case_id": "empty", "corpus": "corpus.json",
                                                    "relations": "relations.json", "queries": "queries.json"},
                                                   ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/run.py", "--input", e9in, "--output", e9 / "out"])
        rj9 = json.loads((e9 / "out" / "result.json").read_text(encoding="utf-8"))
        assert rj9["status"] == "cannot_determine", rj9
        assert not any("未独立跑通" in n for n in rj9["notes"]), rj9["notes"]
        ok.append("零提及：status=cannot_determine 且 notes 无 query 噪音")

        # 空分母记 None 而非 0.0
        c7 = copy.deepcopy(base)
        c7["papers"] = [p for p in c7["papers"] if p["paper_id"] == "P1"]
        v7, _, _ = build_case(tmp, "one-paper", c7, {"relations": []}, qy)
        assert v7["rates"]["edge_evidence_rate"] is None, v7["rates"]
        ok.append("无边时 edge_evidence_rate=None（不把\u201c没数据\u201d记成 0）")

        # 基线对照：同名即合并 + 不核对引文 + 查询无证据 → pass=false
        bo = tmp / "base_out"
        run([ROOT / "examples/baseline.py", "--corpus", DEMO / "corpus.json", "--relations", DEMO / "relations.json",
             "--queries", DEMO / "queries.json", "--out", bo])
        r = run([ROOT / "eval/metrics.py", "--out_dir", eout, "--base_dir", bo])
        md = json.loads(r.stdout[:r.stdout.index("| 指标")].strip())
        assert md["skill"]["pass"] is True and md["base"]["pass"] is False and md["pass_gap"], md
        assert md["delta"]["edge_evidence_rate"] == 1.0 and md["delta"]["non_merge"] == 1, md["delta"]
        ok.append("基线对照：边引文率 1.0 vs 0.0、非合并 1 vs 0、pass_gap=true")

        # 缺 validation.json 的对照侧：记 None 不崩
        eb = tmp / "empty_dir"; eb.mkdir()
        r = run([ROOT / "eval/metrics.py", "--out_dir", eout, "--base_dir", eb])
        assert "Traceback" not in r.stderr, r.stderr[-300:]
        md2 = json.loads(r.stdout[:r.stdout.index("| 指标")].strip())
        assert md2["base"]["mentions"] is None and md2["base"]["missing"], md2["base"]
        ok.append("缺 validation.json 的基线段：记 None 不崩溃")

        print("SELFTEST OK")
        for line in ok:
            print("  ✓", line)
    except AssertionError as e:
        print("SELFTEST FAIL")
        print("  ✗", e)
        sys.exit(1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

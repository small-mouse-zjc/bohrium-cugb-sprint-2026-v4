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

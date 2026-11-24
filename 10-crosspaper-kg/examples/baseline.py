#!/usr/bin/env python3
"""10 基线：模拟"裸 Agent"——同名即合并（不看限定字段/站点）、引文不核对子串、查询不给证据。

用途：给 eval/metrics.py 提供可复现的 base 目录。不是可交付图谱，只是对照组。

  python examples/baseline.py --corpus examples/demo/corpus.json \
      --relations examples/demo/relations.json --queries examples/demo/queries.json --out base_out
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", s)
    return " ".join(s.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--relations", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    corpus = json.loads(Path(a.corpus).read_text(encoding="utf-8"))
    relations = json.loads(Path(a.relations).read_text(encoding="utf-8")).get("relations", [])
    queries = json.loads(Path(a.queries).read_text(encoding="utf-8"))
    queries = queries.get("queries", []) if isinstance(queries, dict) else queries
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # 同名即合并：不看 site/sample_id/conditions
    nodes, idx = [], {}
    for p in corpus["papers"]:
        for m in p.get("mentions", []):
            k = norm(m["surface"])
            if k not in idx:
                idx[k] = {"id": f"n{len(nodes)+1:02d}", "label": m["surface"], "key": k,
                          "mentions": [], "aliases": [], "attrs": {}, "type": m.get("type", "unknown")}
                nodes.append(idx[k])
            idx[k]["mentions"].append({"paper_id": p["paper_id"], "paragraph_id": m["paragraph_id"],
                                       "surface": m["surface"], "key": k, "attrs": m.get("attrs", {})})
    merged_conflicts = 0
    for nd in nodes:
        sites = {m.get("attrs", {}).get("site") for m in nd["mentions"] if m.get("attrs")}
        if len([x for x in sites if x]) > 1:
            merged_conflicts += 1

    # 边：不核对引文子串，端点按同名直接连
    edges = []
    for i, r in enumerate(relations, start=1):
        s, o = idx.get(norm(r["subject"])), idx.get(norm(r["object"]))
        if not s or not o:
            continue
        edges.append({"id": r.get("id") or f"e{i:02d}", "subject": s["id"], "object": o["id"],
                      "predicate": r["predicate"],
                      "evidence": {"paper_id": r["paper_id"], "paragraph_id": r.get("paragraph_id"),
                                   "quote": r.get("quote", ""), "verified": False}})

    # 查询：只回节点名，不给证据
    results = [{"id": q.get("id"), "kind": q.get("kind"), "question": q.get("question", ""),
                "found": True, "evidence": []} for q in queries]

    rates = {"mentions": sum(len(n["mentions"]) for n in nodes), "mention_coverage": 1.0,
             "nodes": len(nodes), "cross_paper_nodes": sum(1 for n in nodes if len({m["paper_id"] for m in n["mentions"]}) > 1),
             "non_merge": 0, "edges": len(edges), "edge_evidence_rate": 0.0,
             "query_provenance_rate": 0.0, "queries": len(results)}
    valid = {"pass": False, "rates": rates, "failed_gates": ["edge_evidence_rate", "query_provenance_rate"],
             "violations": [{"code": "K02", "detail": f"{merged_conflicts} 个同名节点把不同站点合并进同一实体"},
                            {"code": "K03", "detail": "边引文未做逐字子串核对"},
                            {"code": "K04", "detail": "查询结果没有绑定任何证据"}],
             "mode": "baseline"}
    (out / "kg.json").write_text(json.dumps({"nodes": nodes, "edges": edges, "non_merge": []}, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    (out / "queries_result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "validation.json").write_text(json.dumps(valid, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "pass": valid["pass"], "rates": rates}, ensure_ascii=False))


if __name__ == "__main__":
    main()

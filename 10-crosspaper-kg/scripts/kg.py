#!/usr/bin/env python3
"""跨篇实体归一 + 证据绑定 + 可执行查询（10）。

输入 corpus.json（两篇独立材料，JATS paragraph_id）与 relations.json；
输出 kg.json（节点/边/非合并判定）、queries_result.json、validation.json。
原则：可合并要有依据，不可合并也要留证据；每条边必须逐字引用。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ATTRS = ("site", "sample_id", "model_id", "dataset_id", "conditions")
ABBR_RE = re.compile(r"([A-Z][A-Za-z\u4e00-\u9fff\-]{1,}(?:\s+[A-Za-z\u4e00-\u9fff\-]{1,}){0,4})\s*\(([A-Z]{2,6})\)")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[\u2010-\u2015_]", " ", s)
    s = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", s)
    s = " ".join(s.split())
    return _sing_last(s)


def _sing_last(s: str) -> str:
    if not s:
        return s
    parts = s.split(" ")
    w = parts[-1]
    if len(w) > 3:
        if w.endswith("ies"):
            w = w[:-3] + "y"
        elif w.endswith(("ses", "xes", "ches", "shes")):
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
    parts[-1] = w
    return " ".join(parts)


def squash(s: str) -> str:
    return " ".join((s or "").split())


def is_abbr(surface: str) -> bool:
    t = surface.strip()
    return bool(re.fullmatch(r"[A-Z]{2,6}", t))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(corpus: dict, relations: dict, queries):
    if isinstance(queries, dict):
        queries = queries.get("queries", [])
    papers = {p["paper_id"]: p for p in corpus["papers"]}
    para = {}
    aliases = defaultdict(dict)
    for pid, p in papers.items():
        for pr in p["paragraphs"]:
            para[(pid, pr["paragraph_id"])] = squash(pr["text"])
            for m in ABBR_RE.finditer(pr["text"]):
                full, ab = norm(m.group(1)), norm(m.group(2))
                if full and full != ab:
                    aliases[pid].setdefault(ab, full)

    violations, V = [], lambda c, **k: violations.append({"code": c, **k})
    mentions, unresolved = [], 0
    for pid, p in papers.items():
        for m in p.get("mentions", []):
            n = norm(m["surface"])
            if is_abbr(m["surface"]):
                if n in aliases[pid]:
                    n = aliases[pid][n]
                else:
                    unresolved += 1
                    V("K05", surface=m["surface"], paper_id=pid, paragraph_id=m["paragraph_id"],
                      detail="缩写无全称可解析")
            if (pid, m["paragraph_id"]) not in para:
                V("K06", surface=m["surface"], paper_id=pid, paragraph_id=m["paragraph_id"],
                  detail="段落号不存在")
            mentions.append({**m, "paper_id": pid, "key": n, "type": m.get("type", "unknown")})

    nodes, groups = [], defaultdict(list)
    for m in mentions:
        groups[(m["key"], m["type"])].append(m)
    for (key, typ), ml in groups.items():
        subs = []
        for m in ml:
            placed = False
            for sn in subs:
                ma, sa = m.get("attrs", {}), sn["attrs"]
                shared = {k for k in ATTRS if k in ma and k in sa}
                clash = any(ma[k] != sa[k] for k in shared)
                if not shared and (any(k in ma for k in ATTRS) or any(k in sa for k in ATTRS)):
                    clash = True  # 身份限定字段不重叠，无法证明是同一实例
                if not clash:
                    sn["mentions"].append(m)
                    for k in ATTRS:
                        if k in m.get("attrs", {}):
                            sn["attrs"].setdefault(k, m["attrs"][k])
                    placed = True
                    break
            if not placed:
                subs.append({"attrs": {k: v for k, v in m.get("attrs", {}).items() if k in ATTRS},
                             "mentions": [m]})
        for sn in subs:
            nid = "n%02d" % (len(nodes) + 1)
            counts = defaultdict(int)
            for m in sn["mentions"]:
                counts[m["surface"]] += 1
            surfaces = sorted(counts, key=lambda s: (is_abbr(s), -counts[s], -len(s), s))
            nodes.append({"id": nid, "label": surfaces[0], "key": key, "type": typ,
                          "aliases": [s for s in surfaces if s != surfaces[0]],
                          "attrs": sn["attrs"], "mentions": sn["mentions"]})
        if len(subs) > 1:
            pass  # 同名不同实例 = 应保留为非合并，由 non_merge 记录；此处不判违规

    # 错误合并检测：同一节点内某限定字段出现互相冲突的取值
    for nd in nodes:
        for k in ATTRS:
            vals = {m["attrs"][k] for m in nd["mentions"] if k in m.get("attrs", {})}
            if len(vals) > 1:
                V("K02", node_id=nd["id"], attr=k, values=sorted(vals), detail="冲突限定被合并进同一节点")

    # 非合并判定（带证据）
    non_merge = []
    by_key = defaultdict(list)
    for nd in nodes:
        by_key[(nd["key"], nd["type"])].append(nd)
    for (key, typ), nds in by_key.items():
        if len(nds) < 2:
            continue
        a, b = nds[0], nds[1]
        diff = [(k, a["attrs"].get(k), b["attrs"].get(k)) for k in ATTRS
                if a["attrs"].get(k) != b["attrs"].get(k)]
        if not diff:
            V("K01", key=key, node_ids=[x["id"] for x in nds], detail="同键节点未被合并")
            continue
        non_merge.append({
            "key": key, "type": typ, "node_ids": [x["id"] for x in nds],
            "reason": "同名但限定冲突：" + "；".join(
                f"{k}: {u if u is not None else '未给'} vs {v if v is not None else '未给'}"
                for k, u, v in diff),
            "rule": "相同通用方法/材料术语不等于同一物理样品、模型实例或数据集",
            "evidence": [{"paper_id": m["paper_id"], "paragraph_id": m["paragraph_id"],
                          "doi": papers[m["paper_id"]].get("doi"),
                          "quote": _quote_for(para, m)} for nd in nds for m in nd["mentions"][:1]]
        })

    # 边绑定
    def match(surface, pid):
        n = norm(surface)
        cands = [nd for nd in nodes if any(m["key"] == n for m in nd["mentions"])]
        same = [nd for nd in cands if any(m["paper_id"] == pid for m in nd["mentions"])]
        return (same or cands or [None])[0]

    edges = []
    for r in relations.get("relations", []):
        s, o = match(r["subject"], r["paper_id"]), match(r["object"], r["paper_id"])
        eid = r.get("id") or "e%02d" % (len(edges) + 1)
        if not s or not o:
            V("K06", edge=eid, detail="端点无法解析到节点")
            continue
        text = para.get((r["paper_id"], r.get("paragraph_id")), "")
        q = squash(r.get("quote", ""))
        if not text or not q or q not in text:
            V("K03", edge=eid, detail="引文不是该段落的连续子串或段落缺失")
            continue
        edges.append({"id": eid, "subject": s["id"], "subject_label": s["label"],
                      "predicate": r["predicate"], "object": o["id"], "object_label": o["label"],
                      "evidence": {"paper_id": r["paper_id"], "paragraph_id": r["paragraph_id"],
                                   "doi": papers[r["paper_id"]].get("doi"), "quote": q}})

    # 查询
    def node_result(label):
        n = norm(label)
        nd = next((x for x in nodes if x["key"] == n), None)
        if not nd:
            return {"found": False, "label": label, "evidence": []}
        ev = [{"paper_id": m["paper_id"], "paragraph_id": m["paragraph_id"],
               "doi": papers[m["paper_id"]].get("doi"), "quote": _quote_for(para, m)} for m in nd["mentions"]]
        return {"found": True, "node_id": nd["id"], "label": nd["label"], "type": nd["type"],
                "papers": sorted({m["paper_id"] for m in nd["mentions"]}), "evidence": ev}

    def edges_result(pred):
        es = [e for e in edges if e["predicate"] == pred]
        return {"predicate": pred, "count": len(es), "edges": es,
                "evidence": [e["evidence"] for e in es]}

    def path_result(src, dst):
        s, d = norm(src), norm(dst)
        adj = defaultdict(list)
        for e in edges:
            adj[e["subject"]].append((e["object"], e))
            adj[e["object"]].append((e["subject"], e))
        ids = {x["key"]: x["id"] for x in nodes}
        if s not in ids or d not in ids:
            return {"from": src, "to": dst, "found": False, "evidence": []}
        q, seen, prev = [ids[s]], {ids[s]}, {}
        hit = None
        while q:
            cur = q.pop(0)
            if cur == ids[d]:
                hit = cur
                break
            for nxt, e in adj[cur]:
                if nxt not in seen and len(prev) < 8:
                    seen.add(nxt)
                    prev[nxt] = (cur, e)
                    q.append(nxt)
        if not hit:
            return {"from": src, "to": dst, "found": False, "evidence": []}
        chain, cur = [], hit
        while cur in prev:
            cur, e = prev[cur]
            chain.append(e)
        chain.reverse()
        return {"from": src, "to": dst, "found": True, "hops": len(chain), "edges": chain,
                "evidence": [e["evidence"] for e in chain]}

    results = []
    for qt in queries:
        kind = qt.get("kind")
        if kind == "node":
            r = node_result(qt["label"])
        elif kind == "edges":
            r = edges_result(qt["predicate"])
        elif kind == "path":
            r = path_result(qt["from"], qt["to"])
        elif kind == "nonmerge":
            r = {"count": len(non_merge), "records": non_merge,
                 "evidence": [e for nm in non_merge for e in nm["evidence"]]}
        else:
            r = {"error": "unknown kind", "evidence": []}
        r.update({"id": qt["id"], "kind": kind, "question": qt.get("question", "")})
        if not r.get("evidence"):
            V("K04", query=qt["id"], detail="查询无任何证据支撑（空结果或未绑定来源）")
        results.append(r)

    # 指标
    rate = lambda a, b: round(a / b, 4) if b else 0.0
    return {
        "nodes": nodes, "edges": edges, "non_merge": non_merge, "queries": results,
        "violations": violations,
        "rates": {
            "mentions": len(mentions),
            "unresolved_aliases": unresolved,
            "mention_coverage": rate(len(mentions) - unresolved, len(mentions)),
            "nodes": len(nodes),
            "cross_paper_nodes": sum(1 for n in nodes if len({m["paper_id"] for m in n["mentions"]}) > 1),
            "non_merge": len(non_merge),
            "edges": len(edges),
            "edge_evidence_rate": rate(sum(1 for e in edges if e["evidence"]["quote"]), len(edges)),
            "query_provenance_rate": rate(sum(1 for r in results if r.get("evidence")), len(results)),
        },
        "pass": not violations,
    }


def _quote_for(para, m):
    text = para.get((m["paper_id"], m["paragraph_id"]), "")
    q = squash(m.get("quote", ""))
    if q and q in text:
        return q
    sents = re.split(r"(?<=[。！？.!?])\s+", text)
    return next((s for s in sents if m["surface"].lower() in s.lower()), "")


def main():
    ap = argparse.ArgumentParser(description="跨篇实体归一 + 证据绑定 + 查询")
    ap.add_argument("cmd", choices=["build", "query"])
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--relations", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = build(load(Path(a.corpus)), load(Path(a.relations)), load(Path(a.queries)))
    (out / "kg.json").write_text(json.dumps({"nodes": res["nodes"], "edges": res["edges"],
                                             "non_merge": res["non_merge"]}, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    (out / "queries_result.json").write_text(json.dumps(res["queries"], ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    valid = {"pass": res["pass"], "rates": res["rates"], "violations": res["violations"]}
    (out / "validation.json").write_text(json.dumps(valid, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(valid, ensure_ascii=False))
    if not res["pass"] and not a.no_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()

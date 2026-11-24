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
REQUIRED_KINDS = {"node", "edges", "path"}
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
                continue
            text = para[(pid, m["paragraph_id"])]
            q = squash(m.get("quote", ""))
            if not q or q not in text:
                # 提及的引文同样要逐字：改写句不许原样进图谱，回退成该段真实句子
                real = next((s for s in re.split(r"(?<=[。！？.!?])\s+", text)
                             if m["surface"].lower() in s.lower()), "")
                V("K10", surface=m["surface"], paper_id=pid, paragraph_id=m["paragraph_id"],
                  detail=("提及缺引文" if not q else "提及引文不是该段落连续子串，已回退为真实句子"),
                  given_quote=q, fallback=real)
                m = {**m, "quote": real}
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

    # 非合并判定（带证据 + 人工理由）
    VAGUE_REASONS = {"不确定", "unknown", "待定", "n/a", "无", "无法判断", "存疑"}
    reasons = {}
    for x in (relations.get("non_merge_reasons") or []):
        if isinstance(x, dict) and x.get("key"):
            reasons[norm(x["key"])] = str(x.get("reason", "")).strip()
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
        auto_reason = "同名但限定冲突：" + "；".join(
            f"{k}: {u if u is not None else '未给'} vs {v if v is not None else '未给'}"
            for k, u, v in diff)
        author_reason = reasons.get(key, "")
        if not author_reason or author_reason.strip().lower() in VAGUE_REASONS or len(author_reason) < 12:
            V("K11", key=key, node_ids=[x["id"] for x in nds],
              detail="非合并理由缺失或过泛（须在 relations.json 的 non_merge_reasons 给出一句能说服审稿人的具体理由）",
              auto_reason=auto_reason)
            reason_txt = auto_reason
        else:
            reason_txt = author_reason
        non_merge.append({
            "key": key, "type": typ, "node_ids": [x["id"] for x in nds],
            "reason": reason_txt,
            "reason_source": "author" if reason_txt == author_reason else "auto",
            "rule": "相同通用方法/材料术语不等于同一物理样品、模型实例或数据集",
            "evidence": [{"paper_id": m["paper_id"], "paragraph_id": m["paragraph_id"],
                          "doi": papers[m["paper_id"]].get("doi"),
                          "quote": _quote_for(para, m)} for nd in nds for m in nd["mentions"][:1]]
        })

    # 边绑定：同名多节点时，优先用关系里给的段落/限定字段消歧，避免把边绑到错实例
    def match(surface, pid, hints=None, paragraph_id=None):
        n = norm(surface)
        cands = [nd for nd in nodes if any(m["key"] == n for m in nd["mentions"])]
        same = [nd for nd in cands if any(m["paper_id"] == pid for m in nd["mentions"])]
        pool = same or cands
        if hints:
            pin = [nd for nd in pool
                   if all(nd["attrs"].get(k) == v for k, v in hints.items() if k in ATTRS)]
            if pin:
                pool = pin
        if paragraph_id:
            inpar = [nd for nd in pool if any(m["paper_id"] == pid and m["paragraph_id"] == paragraph_id
                                              for m in nd["mentions"])]
            if inpar:
                pool = inpar
        if len(pool) == 1:
            return pool[0]
        return None  # 0 个 = 无端点；>1 个 = 歧义，交给调用方报错，不静默取第一个

    edges = []
    def surfaces_of(nd, pid):
        return [squash(m["surface"]).lower() for m in nd["mentions"] if m["paper_id"] == pid] or \
               [squash(m["surface"]).lower() for m in nd["mentions"]]

    for r in relations.get("relations", []):
        eid = r.get("id") or "e%02d" % (len(edges) + 1)
        pid = r.get("paper_id")
        if not pid:
            V("K06", edge=eid, detail="关系缺少 paper_id，端点无法归属到任何一篇")
            continue
        prg = r.get("paragraph_id")
        s = match(r["subject"], pid, r.get("subject_attrs"), prg)
        o = match(r["object"], pid, r.get("object_attrs"), prg)
        def n_cands(surface):
            n = norm(surface)
            return len([nd for nd in nodes if any(m["key"] == n and m["paper_id"] == pid for m in nd["mentions"])])
        if not s or not o:
            amb = [rr for rr, got in ((r["subject"], s), (r["object"], o)) if got is None and n_cands(rr) > 1]
            if amb:
                V("K09", edge=eid, detail=f"同名多实例且段落/限定无法唯一确定端点（{amb[0]}），拒绝建边")
            else:
                V("K06", edge=eid, detail="端点无法解析到节点")
            continue
        text = para.get((pid, prg), "")
        q = squash(r.get("quote", ""))
        if not text or not q or q not in text:
            V("K03", edge=eid, detail="引文不是该段落的连续子串或段落缺失")
            continue
        low = q.lower()
        miss = [nm for nm, nd in (("subject", s), ("object", o)) if not any(sf in low for sf in surfaces_of(nd, pid))]
        if miss:
            V("K03", edge=eid, detail=f"引文逐字但未支持 {'/'.join(miss)}：引文里没有端点在本篇的写法",
              endpoints=miss, quote=q)
            continue
        edges.append({"id": eid, "subject": s["id"], "subject_label": s["label"],
                      "predicate": r["predicate"], "object": o["id"], "object_label": o["label"],
                      "evidence": {"paper_id": pid, "paragraph_id": prg,
                                   "doi": papers[pid].get("doi"), "quote": q}})

    # 查询
    results = execute_queries(papers, para, nodes, edges, non_merge, queries, violations)

    # 指标
    def rate(a, b):
        return round(a / b, 4) if b else None

    if len(queries) < 3:
        violations.append({"code": "K07", "detail": f"查询只有 {len(queries)} 条，少于 3 条，图谱结论无法被独立复问"})
    kinds = {q.get("kind") for q in queries}
    missing_kinds = sorted(REQUIRED_KINDS - kinds)
    if missing_kinds:
        violations.append({"code": "K08", "missing_kinds": missing_kinds,
                           "detail": f"查询未覆盖节点/关系/路径三类（缺 {', '.join(missing_kinds)}），三条同类查询不构成独立复问"})
    rates = {
        "mentions": len(mentions),
        "unresolved_aliases": unresolved,
        "mention_coverage": rate(len(mentions) - unresolved, len(mentions)),
        "nodes": len(nodes),
        "cross_paper_nodes": sum(1 for n in nodes if len({m["paper_id"] for m in n["mentions"]}) > 1),
        "non_merge": len(non_merge),
        "edges": len(edges),
        "edge_evidence_rate": rate(sum(1 for e in edges if e["evidence"]["quote"]), len(edges)),
        "query_provenance_rate": rate(sum(1 for r in results if r.get("evidence")), len(results)),
        "queries": len(results),
    }
    gates = [k for k in ("mention_coverage", "edge_evidence_rate", "query_provenance_rate")
             if rates[k] is None or rates[k] < 1.0]
    return {
        "nodes": nodes, "edges": edges, "non_merge": non_merge, "queries": results,
        "violations": violations, "rates": rates,
        "failed_gates": gates,
        "pass": not violations and not gates,
    }


def execute_queries(papers, para, nodes, edges, non_merge, queries, violations):
    """在已建好的图上跑 queries：build 与 query 两条命令共用，query 不再重跑构建。"""

    def _label_hits(label):
        """查询端的归一必须和构建端同口径：key / aliases / 每篇的 surface 任一命中即算命中，
        否则别名归一在查询侧白做（用 GH 查不到 gas hydrate 就等于没归一）。"""
        n = norm(label)
        out = []
        for x in nodes:
            if x["key"] == n or any(norm(a) == n for a in x.get("aliases", [])) \
                    or any(norm(m["surface"]) == n for m in x["mentions"]):
                out.append(x)
        return out

    def node_result(label):
        hits = _label_hits(label)
        if not hits:
            return {"found": False, "label": label, "evidence": []}
        if len(hits) > 1:
            # 同一写法对应多个实例（非合并词）：不静默取第一个，把候选连同证据一并交出
            return {"found": True, "ambiguous": True, "label": label,
                    "candidate_ids": [x["id"] for x in hits],
                    "candidates": [{"node_id": x["id"], "label": x["label"], "attrs": x["attrs"]} for x in hits],
                    "evidence": [{"paper_id": m["paper_id"], "paragraph_id": m["paragraph_id"],
                                  "doi": papers[m["paper_id"]].get("doi"), "quote": _quote_for(para, m)}
                                 for x in hits for m in x["mentions"]]}
        nd = hits[0]
        ev = [{"paper_id": m["paper_id"], "paragraph_id": m["paragraph_id"],
               "doi": papers[m["paper_id"]].get("doi"), "quote": _quote_for(para, m)} for m in nd["mentions"]]
        return {"found": True, "node_id": nd["id"], "label": nd["label"], "type": nd["type"],
                "matched_by": "key" if nd["key"] == norm(label) else "alias",
                "papers": sorted({m["paper_id"] for m in nd["mentions"]}), "evidence": ev}

    def edges_result(pred):
        es = [e for e in edges if e["predicate"] == pred]
        return {"predicate": pred, "count": len(es), "edges": es,
                "evidence": [e["evidence"] for e in es]}

    def path_result(src, dst):
        sh, dh = _label_hits(src), _label_hits(dst)
        if not sh or not dh:
            return {"from": src, "to": dst, "found": False, "evidence": []}
        sids = {x["id"] for x in sh}
        dids = {x["id"] for x in dh}
        adj = defaultdict(list)
        for e in edges:
            adj[e["subject"]].append((e["object"], e))
            adj[e["object"]].append((e["subject"], e))
        # 多源 BFS：起点/终点各自可能对应多个实例（非合并词），全部纳入，不塌缩成最后一个
        q, seen, prev = list(sids), set(sids), {}
        hit = None
        while q:
            cur = q.pop(0)
            if cur in dids:
                hit = cur
                break
            for nxt, e in adj[cur]:
                if nxt not in seen and len(prev) < 8:
                    seen.add(nxt)
                    prev[nxt] = (cur, e)
                    q.append(nxt)
        base = {"from": src, "to": dst, "from_ids": sorted(sids), "to_ids": sorted(dids),
                "ambiguous": len(sids) > 1 or len(dids) > 1}
        if not hit:
            return dict(base, found=False, evidence=[])
        chain, cur = [], hit
        while cur in prev:
            cur, e = prev[cur]
            chain.append(e)
        chain.reverse()
        return dict(base, found=True, hops=len(chain), edges=chain, end_id=hit,
                    evidence=[e["evidence"] for e in chain])

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
            violations.append({"code": "K04", "query": qt["id"],
                               "detail": "查询无任何证据支撑（空结果或未绑定来源）"})
        results.append(r)
    return results


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
    queries = load(Path(a.queries))
    queries = queries.get("queries", []) if isinstance(queries, dict) else queries

    if a.cmd == "build":
        corpus, relations = load(Path(a.corpus)), load(Path(a.relations))
        res = build(corpus, relations, queries)
        kg = {"nodes": res["nodes"], "edges": res["edges"], "non_merge": res["non_merge"],
              "papers": corpus["papers"],
              "para": {f"{k[0]}|{k[1]}": v for k, v in _build_para(corpus).items()}}
        (out / "kg.json").write_text(json.dumps(kg, ensure_ascii=False, indent=2), encoding="utf-8")
        results, valid = res["queries"], {"pass": res["pass"], "rates": res["rates"],
                                         "failed_gates": res["failed_gates"], "violations": res["violations"]}
    else:
        # 真查询：读已建好的 kg.json，只执行查询，不再重跑构建
        kgp = out / "kg.json"
        if not kgp.exists():
            print(json.dumps({"error": f"{kgp} 不存在，先跑 build"}, ensure_ascii=False))
            sys.exit(2)
        kg = load(kgp)
        papers = {p["paper_id"]: p for p in kg.get("papers", [])}
        para = {tuple(k.split("|", 1)): v for k, v in kg.get("para", {}).items()}
        violations = []
        results = execute_queries(papers, para, kg["nodes"], kg["edges"], kg["non_merge"], queries, violations)
        def rate(x, y):
            return round(x / y, 4) if y else None
        rates = {"queries": len(results),
                 "query_provenance_rate": rate(sum(1 for r in results if r.get("evidence")), len(results)),
                 "nodes": len(kg["nodes"]), "edges": len(kg["edges"])}
        if len(queries) < 3:
            violations.append({"code": "K07", "detail": f"查询只有 {len(queries)} 条，少于 3 条"})
        missing_kinds = sorted(REQUIRED_KINDS - {q.get("kind") for q in queries})
        if missing_kinds:
            violations.append({"code": "K08", "missing_kinds": missing_kinds,
                               "detail": f"查询未覆盖节点/关系/路径三类（缺 {', '.join(missing_kinds)}）"})
        gates = [] if rates["query_provenance_rate"] == 1.0 else ["query_provenance_rate"]
        valid = {"pass": not violations and not gates, "rates": rates, "failed_gates": gates,
                 "violations": violations, "mode": "query-only"}

    (out / "queries_result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    vname = "query_validation.json" if a.cmd == "query" else "validation.json"
    (out / vname).write_text(json.dumps(valid, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(valid, ensure_ascii=False))
    if not valid["pass"] and not a.no_fail:
        sys.exit(1)


def _build_para(corpus):
    para = {}
    for p in corpus["papers"]:
        for pr in p["paragraphs"]:
            para[(p["paper_id"], pr["paragraph_id"])] = squash(pr["text"])
    return para


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""断言拆解校验 + JSON-LD / TriG 导出 + 回解析。

  python nanopub.py build --assertions work/assertions.json --sources work/sources.json --out out
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import trig as triglib

VOCAB = ["increases", "decreases", "supports", "contradicts", "uses", "measured_by",
         "located_in", "composed_of", "exceeds", "has_value"]
CONNECT = ["并且", "而且", "以及", "；", ";", " and ", "此外"]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def doi_iri(doi, case_id):
    """把 DOI 统一成一个 IRI：已是 URL/urn 的原样用，纯 DOI 补 https://doi.org/，缺失用 urn:case:。

    旧实现无条件加 urn:doi: 前缀，遇到 doi 本身是 urn:doi:... 就生成 urn:doi:urn:doi:... 的畸形 IRI。
    """
    d = (doi or "").strip()
    if not d:
        return f"urn:case:{case_id}"
    if d.startswith(("http://", "https://", "urn:")):
        return d
    return "https://doi.org/" + d


def lit(s: str) -> str:
    return '"' + esc(s) + '"'


def slug(s: str) -> str:
    """把中文/英文标签压成 IRI 片段；中文按 UTF-8 百分号编码，避免 IRI 里出现裸空格或引号。"""
    from urllib.parse import quote
    t = (s or "").strip().lower()
    t = re.sub(r"\s+", "-", t)
    t = re.sub(r"[\"'<>{}\\\\]", "", t)
    return quote(t, safe="-._~") or "unknown"


def ent_iri(label: str, case_id: str) -> str:
    return f"https://example.org/np/{slug(case_id)}/ent/{slug(label)}"


def rel_iri(relation: str) -> str:
    return f"https://example.org/rel/{slug(relation)}"


def build(assertions, sources, paper):
    src = {s["paragraph_id"]: s for s in sources}
    all_text = {k: norm(v["text"]) for k, v in src.items()}
    viol, seen, out = [], {}, []

    for a in assertions:
        aid = a.get("id") or f"A{len(out)+1}"
        text = norm(a.get("text", ""))
        sub = a.get("subject") or {}
        obj = a.get("object") or {}
        ev = a.get("evidence") or {}
        rel = (a.get("relation") or "").strip()
        pid = ev.get("paragraph_id")

        # N01 原子性
        sentences = [x for x in re.split(r"(?<=[。！？])\s*|(?<=[.!?])\s+", text) if x.strip()]
        if len(sentences) > 1 or any(c in text for c in CONNECT):
            viol.append({"code": "N01", "id": aid, "detail": "非原子：多句或并列/因果连接"})
        if not sub.get("label") or not obj.get("label") or sub.get("label") == obj.get("label"):
            viol.append({"code": "N01", "id": aid, "detail": "主体/客体缺失或相同"})
        if rel not in VOCAB:
            viol.append({"code": "N06", "id": aid, "detail": f"关系 '{rel}' 不在受控词表"})

        # N05 来源
        miss = [k for k in ("title", "year") if not paper.get(k)]
        if not pid or pid not in src:
            miss.append("paragraph_id")
        if not paper.get("doi") and not paper.get("doi_reason"):
            miss.append("doi")
        if miss:
            viol.append({"code": "N05", "id": aid, "detail": f"来源缺 {miss}"})

        # N02/N03/N04 证据
        q = norm(ev.get("quote", ""))
        body = all_text.get(pid, "")
        if not q or q not in body:
            viol.append({"code": "N02", "id": aid, "detail": "证据不是源段落中的逐字片段"})
        elif not (10 <= len(q) <= 400):
            viol.append({"code": "N03", "id": aid, "detail": f"证据长度 {len(q)} 不在 10–400"})
        else:
            key_terms = [sub.get("label", ""), obj.get("label", "")]
            if key_terms and not any(k and k.lower() in q.lower() for k in key_terms):
                viol.append({"code": "N04", "id": aid, "detail": "证据片段不含主体或客体表面形式"})

        # N07 重复
        dup_key = (norm(str(sub.get("label"))).lower(), rel, norm(str(obj.get("label"))).lower(), norm(a.get("qualifier", "")).lower())
        if dup_key in seen:
            viol.append({"code": "N07", "id": aid, "detail": f"与 {seen[dup_key]} 重复"})
        else:
            seen[dup_key] = aid

        out.append({"id": aid, "text": text, "subject": sub, "relation": rel, "object": obj,
                    "qualifier": norm(a.get("qualifier", "")), "evidence": {"quote": q, "paragraph_id": pid,
                    "page": ev.get("page")}, "confidence": a.get("confidence", "medium"),
                    "derivation": a.get("derivation", "direct")})
    return out, viol


def node_of(ent, case_id):
    """JSON-LD 里主体/客体统一写成 IRI 节点，与 TriG 的 ent_iri 完全同一标识。"""
    return {"@id": ent_iri(str(ent.get("label", "")), case_id),
            "@type": "rel:Entity",
            "rel:label": ent.get("label"),
            "rel:entityType": ent.get("type")}


def export_jsonld(asserts, paper, case_id):
    base = f"https://example.org/np/{case_id}/"
    ctx = {"np": "http://www.nanopub.org/nschema#", "rel": "https://example.org/rel/",
           "prov": "http://www.w3.org/ns/prov#", "oa": "http://www.w3.org/ns/oa#"}
    graph = []
    for a in asserts:
        gid = base + a["id"]
        graph.append({"@id": gid, "@type": "np:Nanopublication",
                      "np:hasAssertion": {"@id": gid + "/assertion"},
                      "np:hasProvenance": {"@id": gid + "/provenance"},
                      "np:hasPublicationInfo": {"@id": gid + "/pubinfo"}})
        graph.append({"@id": gid + "/assertion", "@type": "np:Assertion",
                      "rel:subject": node_of(a["subject"], case_id),
                      "rel:relation": {"@id": rel_iri(a["relation"])},
                      "rel:object": node_of(a["object"], case_id),
                      "rel:qualifier": a["qualifier"],
                      "rel:text": a["text"]})
        graph.append({"@id": gid + "/provenance", "@type": "np:Provenance",
                      "prov:wasDerivedFrom": {"@id": doi_iri(paper.get("doi"), case_id)},
                      "rel:sourceTitle": paper.get("title"), "rel:sourceYear": paper.get("year"),
                      "rel:paragraphId": a["evidence"]["paragraph_id"], "rel:quote": a["evidence"]["quote"],
                      "rel:derivation": a["derivation"]})
        graph.append({"@id": gid + "/pubinfo", "@type": "np:PublicationInfo",
                      "rel:caseId": case_id, "rel:creator": "skill:nanopub-assertion-export",
                      "rel:license": "https://creativecommons.org/licenses/by/4.0/"})
    return {"@context": ctx, "@graph": graph}


def export_trig(asserts, paper, case_id):
    base = f"https://example.org/np/{case_id}/"
    head = ("@prefix np: <http://www.nanopub.org/nschema#> .\n"
            "@prefix rel: <https://example.org/rel/> .\n"
            "@prefix prov: <http://www.w3.org/ns/prov#> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n")
    blocks = []
    for a in asserts:
        gid = base + a["id"]
        src = doi_iri(paper.get("doi"), case_id)
        b = (f"<{gid}> {{\n"
             f"  <{gid}> a np:Nanopublication ;\n"
             f"      np:hasAssertion <{gid}/assertion> ;\n"
             f"      np:hasProvenance <{gid}/provenance> ;\n"
             f"      np:hasPublicationInfo <{gid}/pubinfo> .\n"
             f"  <{gid}/assertion> a np:Assertion ;\n"
             f"      rel:relation <{rel_iri(a['relation'])}> ;\n"
             f"      rel:subject <{ent_iri(str(a['subject'].get('label','')), case_id)}> ;\n"
             f"      rel:subjectLabel {lit(str(a['subject'].get('label','')))} ;\n"
             f"      rel:subjectType {lit(str(a['subject'].get('type') or ''))} ;\n"
             f"      rel:object <{ent_iri(str(a['object'].get('label','')), case_id)}> ;\n"
             f"      rel:objectLabel {lit(str(a['object'].get('label','')))} ;\n"
             f"      rel:objectType {lit(str(a['object'].get('type') or ''))} ;\n"
             f"      rel:qualifier {lit(a['qualifier'])} ;\n"
             f"      rel:text {lit(a['text'])} .\n"
             f"  <{gid}/provenance> a np:Provenance ;\n"
             f"      prov:wasDerivedFrom <{esc(str(src))}> ;\n"
             f"      rel:paragraphId {lit(str(a['evidence']['paragraph_id']))} ;\n"
             f"      rel:quote {lit(a['evidence']['quote'])} ;\n"
             f"      rel:derivation {lit(a['derivation'])} .\n"
             f"  <{gid}/pubinfo> a np:PublicationInfo ;\n"
             f"      rel:caseId {lit(case_id)} ;\n"
             f"      rel:creator {lit('skill:nanopub-assertion-export')} .\n"
             f"}}\n")
        blocks.append(b)
    return head + "\n".join(blocks)


def reparse(trig_text, n_asserts):
    """真解析：语法错就 ok=False（不是数出现次数）。"""
    try:
        parsed = triglib.parse(trig_text)
    except triglib.TrigError as exc:
        return {"named_graphs": 0, "assertion_nodes": 0, "quotes": 0, "ok": False,
                "error": exc.msg, "pos": exc.pos}
    s = triglib.summarize(parsed)
    s["ok"] = (s["named_graphs"] == n_asserts and s["assertion_nodes"] == n_asserts
               and s["quotes"] == n_asserts)
    return s


def compare_serializations(jsonld, parsed, asserts, case_id):
    """JSON-LD 与 TriG 必须对同一断言给出同一组 IRI（主/客/关系）。"""
    base = f"https://example.org/np/{case_id}/"
    rel = "https://example.org/rel/"
    ld_nodes = {}
    for node in jsonld.get("@graph", []):
        nid = node.get("@id")
        if isinstance(nid, str) and nid.endswith("/assertion"):
            ld_nodes[nid] = node
    tri = {}
    for t in parsed["triples"]:
        if t["s"].endswith("/assertion") and t["p"].startswith(rel) and t["kind"] == "iri":
            tri.setdefault(t["s"], {})[t["p"][len(rel):]] = t["o"]
    checked, mismatch = 0, []
    for a in asserts:
        nid = base + a["id"] + "/assertion"
        ld, tg = ld_nodes.get(nid), tri.get(nid)
        if not ld or not tg:
            mismatch.append({"id": a["id"], "field": "*", "why": "missing_node_in_one_serialization"})
            continue
        for field, key in (("subject", "subject"), ("object", "object"), ("relation", "relation")):
            checked += 1
            lv = (ld.get("rel:" + field) or {}).get("@id") if isinstance(ld.get("rel:" + field), dict) else None
            if lv != tg.get(key):
                mismatch.append({"id": a["id"], "field": field, "jsonld": lv, "trig": tg.get(key)})
    rate = round((checked - len([m for m in mismatch if m["field"] != "*"])) / checked, 4) if checked else None
    return {"checked": checked, "mismatch": mismatch, "consistency_rate": rate,
            "ok": not mismatch}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--assertions", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()

    payload = json.loads(Path(a.assertions).read_text(encoding="utf-8"))
    sources = json.loads(Path(a.sources).read_text(encoding="utf-8"))["sources"]
    paper = payload.get("paper", {})
    case_id = payload.get("case_id", "case")
    # 词表可扩展：payload 里的 relation_extensions 真的并进受控词表（以前只在文档里说）
    for x in (payload.get("relation_extensions") or []):
        if isinstance(x, str) and x.strip() and x.strip() not in VOCAB:
            VOCAB.append(x.strip())
    asserts, viol = build(payload["assertions"], sources, paper)

    trig = export_trig(asserts, paper, case_id)
    rt = reparse(trig, len(asserts))
    if not rt["ok"]:
        viol.append({"code": "N08", "detail": f"导出回解析失败: {rt}"})

    jsonld = export_jsonld(asserts, paper, case_id)
    try:
        parsed = triglib.parse(trig)
        ser = compare_serializations(jsonld, parsed, asserts, case_id)
    except triglib.TrigError as exc:
        ser = {"checked": 0, "mismatch": [], "consistency_rate": None, "ok": False,
               "error": exc.msg}
    if not ser["ok"] and asserts:
        viol.append({"code": "N09", "detail": f"JSON-LD 与 TriG 标识不一致: {ser['mismatch'][:3]}",
                     "rate": ser["consistency_rate"]})

    # 按"受影响的断言 id"算比率，而不是按违规条数（一条断言可能同时触发 2 条 N01，
    # 旧写法 1 - 条数/断言数 会算出负数或把 0 断言记成 1.00）
    n = len(asserts)
    def bad_ids(codes):
        return {v["id"] for v in viol if v.get("code") in codes and v.get("id")}
    atomic_bad = bad_ids(("N01", "N06"))
    verbatim_bad = bad_ids(("N02", "N03", "N04"))   # N04（证据不含主客表面形式）也必须拉低逐字率
    prov_bad = bad_ids(("N05",))
    if n == 0:
        viol.append({"code": "N00", "detail": "断言文件里没有断言，无法导出（比率记 null，不记 1.00）"})
        rates = {"assertions": 0, "atomic_rate": None, "verbatim_rate": None, "provenance_rate": None,
                 "export_roundtrip": False, "serialization_consistency_rate": None, "violations": len(viol)}
        trig = ""
        rt = {"named_graphs": 0, "assertion_nodes": 0, "quotes": 0, "ok": False}
    else:
        rates = {"assertions": n,
                 "atomic_rate": round((n - len(atomic_bad)) / n, 4),
                 "verbatim_rate": round((n - len(verbatim_bad)) / n, 4),
                 "provenance_rate": round((n - len(prov_bad)) / n, 4),
                 "export_roundtrip": rt["ok"],
                 "serialization_consistency_rate": ser["consistency_rate"],
                 "violations": len(viol)}

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "assertions.json").write_text(json.dumps({"case_id": case_id, "paper": paper, "assertions": asserts}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "nanopub.jsonld").write_text(json.dumps(export_jsonld(asserts, paper, case_id), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "nanopub.trig").write_text(trig, encoding="utf-8")
    (out / "validation.json").write_text(json.dumps({"rates": rates, "roundtrip": rt,
                                                     "serialization": ser, "violations": viol,
                                                     "pass": not viol}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"assertions": len(asserts), "violations": len(viol), "roundtrip": rt["ok"],
                      "codes": sorted({v["code"] for v in viol})}, ensure_ascii=False))
    if not a.no_fail and viol:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""10 平台入口：/input/case.json → 建图 → 查询 → /app/output/result.json

  python scripts/run.py                      # 默认 /input → /app/output
  python scripts/run.py --input examples/demo --output out

case.json 字段（容错）：
  corpus / corpus_path        corpus.json（papers[].paragraphs/mentions）
  materials / papers          直接给材料列表（无 corpus 时装配成 corpus.json）
  relations / relations_path  关系与逐字引文
  queries / queries_path      查询（至少 3 条）
输出：corpus.json（装配过才有）/ kg.json / queries_result.json / validation.json / result.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def pick(d, names):
    for n in names:
        v = d.get(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def pick_list(d, names):
    for n in names:
        v = d.get(n)
        if isinstance(v, list) and v:
            return v
    return None


def resolve(base: Path, p: str | None):
    if not p:
        return None
    q = Path(p)
    if q.is_absolute():
        return q
    cand = base / q
    return cand if cand.exists() else q


def call(args):
    return subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")


def write(out: Path, payload: dict, rc: int):
    (out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    a = ap.parse_args()
    inp, out = Path(a.input), Path(a.output)
    out.mkdir(parents=True, exist_ok=True)

    case_p = inp / "case.json"
    if not case_p.exists():
        return write(out, {"case_id": "unknown", "status": "rejected", "metrics": {"pass": False},
                           "notes": [f"缺少 {case_p}"], "artifacts": []}, 2)
    case = json.loads(case_p.read_text(encoding="utf-8"))
    case_id = case.get("case_id") or case.get("id") or "unknown"

    corpus = resolve(inp, pick(case, ["corpus", "corpus_path"]))
    materials = pick_list(case, ["materials", "papers", "corpus_materials"])
    relations = resolve(inp, pick(case, ["relations", "relations_path"]))
    queries = resolve(inp, pick(case, ["queries", "queries_path"]))

    if (not corpus or not corpus.exists()) and materials:
        corpus = out / "corpus.json"
        corpus.parent.mkdir(parents=True, exist_ok=True)
        corpus.write_text(json.dumps({"papers": materials}, ensure_ascii=False, indent=2), encoding="utf-8")

    if not corpus or not corpus.exists():
        return write(out, {"case_id": case_id, "status": "rejected", "metrics": {"pass": False},
                           "notes": [f"缺少 corpus/materials: {corpus}"], "artifacts": []}, 2)
    if not relations or not relations.exists() or not queries or not queries.exists():
        return write(out, {"case_id": case_id, "status": "rejected", "metrics": {"pass": False},
                           "notes": ["缺少 relations.json 或 queries.json"], "artifacts": []}, 2)

    rb = call([ROOT / "scripts/kg.py", "build", "--corpus", corpus, "--relations", relations,
               "--queries", queries, "--out", out, "--no-fail"])
    if not (out / "validation.json").exists():
        return write(out, {"case_id": case_id, "status": "rejected", "metrics": {"pass": False, "step": "build"},
                           "notes": [rb.stdout[-300:], rb.stderr[-300:]], "artifacts": []}, 2)
    v = json.loads((out / "validation.json").read_text(encoding="utf-8"))

    # 真查询：在已建好的图上单独跑一次，校验 query 子命令不是空操作
    rq = call([ROOT / "scripts/kg.py", "query", "--corpus", corpus, "--relations", relations,
               "--queries", queries, "--out", out, "--no-fail"])
    vq = json.loads((out / "query_validation.json").read_text(encoding="utf-8")) if (out / "query_validation.json").exists() else {}
    query_ok = bool(vq.get("mode") == "query-only" and vq.get("pass"))

    rates = v.get("rates", {})
    metrics = {k: rates.get(k) for k in ("mentions", "mention_coverage", "nodes", "cross_paper_nodes",
                                          "non_merge", "edges", "edge_evidence_rate", "query_provenance_rate")}
    metrics.update({"queries": rates.get("queries"), "query_only_pass": query_ok})
    notes = []
    if not query_ok and rates.get("mentions") not in (0, None):
        notes.append("query 子命令未独立跑通（可能缺 kg.json 或查询无证据）")
    if rates.get("mentions") in (0, None):
        status = "cannot_determine"
        notes = ["材料里没有任何实体提及，图谱无法构建；query 失败是零节点的下游结果，不是独立故障"]
    elif v.get("pass") and query_ok:
        status = "success"
    else:
        status = "partial"
        if v.get("failed_gates"):
            notes.append("未达门槛: " + ",".join(v["failed_gates"]))
        if v.get("violations"):
            notes.append(f"违规 {len(v['violations'])} 条，见 validation.json")

    metrics["pass"] = status == "success"
    artifacts = ["kg.json", "queries_result.json", "validation.json", "query_validation.json"]
    if (out / "corpus.json").exists() and str(corpus).startswith(str(out)):
        artifacts.insert(0, "corpus.json")
    payload = {"case_id": case_id, "status": status, "metrics": metrics, "notes": notes,
               "artifacts": artifacts, "input_mode": "platform" if str(inp) == "/input" else "local"}
    return write(out, payload, 0 if status == "success" else 1)


if __name__ == "__main__":
    sys.exit(main())

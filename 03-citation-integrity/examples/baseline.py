#!/usr/bin/env python3
"""03 基线：模拟"裸 Agent 引用整理"——看起来整齐，但编号、去重、元数据都坏。

坏习惯（可复现）：
  1) 删掉未引用条目但不重排编号 → 正文出现缺号/悬空；
  2) 按标题相似度合并，不看 DOI → 会议版与期刊版被并成一条；
  3) 原始来源缺 DOI 就"补一个占位 DOI" → 编造字段；
  4) number_mapping 只写被引用的前几条，claim_source_map 留空。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cite_chain  # noqa: E402
import renumber  # noqa: E402


def naive(ms: str, bib: list) -> dict:
    # 1) 按标题粗合并（忽略 DOI），保留第一条
    keep, merged = [], []
    for b in bib:
        for k in keep:
            if renumber.similar_title(b.get("title", ""), k.get("title", "")) > 0.8:
                merged.append(str(b.get("id")))
                break
        else:
            keep.append(b)

    # 2) 只保留被引用的条目，但不重排编号
    cited = set()
    for m in renumber.NUM_CITE.finditer(ms):
        cited.update(renumber.expand(m.group(1)))
    kept_cited = [b for b in keep if str(b.get("id")) in cited] or keep

    out_bib = []
    for b in kept_cited:
        out_bib.append({
            "id": str(b.get("id")),
            "key": b.get("key"),
            "author": b.get("author"),
            "year": b.get("year"),
            "title": b.get("title"),
            "source": b.get("source"),
            "doi": b.get("doi") or f"10.0000/unknown.{b.get('id')}",   # 编造占位 DOI
            # 卷期页码被"排版精简"掉 → 元数据丢失
            "volume": None, "pages": None,
        })
    mapping = [{"citation": f"[{b['id']}]", "key": b.get("key"), "bib_id": b["id"]}
               for b in out_bib]
    return {"editable_manuscript": ms, "bibliography": out_bib,
            "number_mapping": mapping, "claim_source_map": [],
            "merged_ids": merged, "unresolved": [], "uncertainty": [], "style": "numeric"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = naive(case.get("manuscript") or case.get("text") or "", case.get("bibliography") or [])
    result = {"case_id": case.get("case_id", "baseline"), "status": "success",
              "result": {**data, "artifacts": {}}, "mode": "baseline-naive"}
    report = cite_chain.audit(result, case)
    result["metrics"] = {**report["rates"], "blocking": len(report["blocking"]),
                         "pass": report["pass"], "mode": "baseline-naive"}
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"bib": len(data["bibliography"]), "merged": data["merged_ids"],
                      "blocking": [b["code"] for b in report["blocking"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

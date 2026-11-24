#!/usr/bin/env python3
"""03 引用链审计：正文 ↔ 文献表 ↔ 编号映射 ↔ 原始来源，四方闭环。

  python scripts/cite_chain.py --result /app/output/result.json --case /input/case.json \
        --out /app/output/cite_chain.md

阻断码：
  C01 dangling_citation     正文编号在文献表里没有
  C02 numbering_gap         新编号不连续（不是 1..N）
  C03 order_mismatch        编号顺序与正文首次出现顺序不一致
  C04 duplicate_left        仍有可合并重复条目（作者+年份+标题>0.9 且 DOI 不冲突）
  C05 key_collision         两条文献 key 相同
  C06 mapping_mismatch      number_mapping 与正文/文献表不符
  C07 fabricated_entry      文献表出现原始来源里没有的条目
  C08 fabricated_field      条目字段在原始来源里为空却被填了值（编造 DOI/卷期/页码）
  C09 metadata_loss         原始来源有值，输出却被删空
  C10 merge_conflict        标题相似但 DOI 不同却被合并（会议版/期刊版被并）
  C11 claim_map_gap         claim_source_map 没覆盖正文里的引用
提示码：
  A01 listed_not_cited / A02 partial_metadata
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import renumber

FIELDS = renumber.FIELDS
CODES = {
    "dangling_citation": "C01", "numbering_gap": "C02", "order_mismatch": "C03",
    "duplicate_left": "C04", "key_collision": "C05", "mapping_mismatch": "C06",
    "fabricated_entry": "C07", "fabricated_field": "C08", "metadata_loss": "C09",
    "merge_conflict": "C10", "claim_map_gap": "C11",
    "renumber_mismatch": "C12", "doi_format": "C13",
    "listed_not_cited": "A01", "partial_metadata": "A02",
}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def rate(a, b):
    return round(a / b, 4) if b else None


def original_bib(case: dict) -> list:
    for k in ("bibliography", "references", "sources", "bib"):
        v = case.get(k)
        if isinstance(v, list) and v:
            return v
    return []


def _match_original(entry: dict, orig: list):
    """先按"作者+年份+标题相似"匹配；匹配不上再退回 DOI。

    DOI 是比标题强得多的身份信号：只改标题时若按标题匹配失败，就会被误诊成
    "凭空造条目(C07)"并跳过逐字段比对，改动也漏进逐字率分母。所以两边 DOI 都非空
    且归一后相等、且作者/年份也对得上时，认为就是同一篇，让标题改动走到 C08。
    """
    for o in orig:
        if (renumber.author_norm(o) == renumber.author_norm(entry)
                and str(o.get("year")) == str(entry.get("year"))
                and renumber.similar_title(o.get("title", ""), entry.get("title", "")) > 0.9):
            return o
    d = renumber.doi_norm(entry.get("doi"))
    if d:
        hit = [o for o in orig if renumber.doi_norm(o.get("doi")) == d
               and renumber.author_norm(o) == renumber.author_norm(entry)]
        if len(hit) == 1:
            return hit[0]
    return None


def audit(result: dict, case: dict) -> dict:
    res = result.get("result") or {}
    ms = str(res.get("editable_manuscript", ""))
    bib = res.get("bibliography") or []
    mapping = res.get("number_mapping") or []
    claim_map = res.get("claim_source_map") or []
    style = res.get("style") or case.get("style") or "numeric"
    orig = original_bib(case)
    blocking, advisory = [], []

    # 1 悬空引用 + 首次出现顺序
    cited, first_order, occ = set(), [], 0
    pattern = renumber.NUM_CITE if style == "numeric" else renumber.AUTH_YEAR
    for m in pattern.finditer(ms):
        occ += 1
        if style == "numeric":
            for i in renumber.expand(m.group(1)):
                cited.add(i)
                if i not in first_order:
                    first_order.append(i)
        else:
            cited.add(m.group(0))
    bib_ids = {str(b.get("id")) for b in bib}
    ay_resolved, ay_unresolved = set(), []
    if style != "numeric":
        for m in renumber.AUTH_YEAR.finditer(ms):
            surname, year = renumber.surname_key(m.group(1)), m.group(2)
            hit = next((b for b in bib if renumber.surname_key(b.get("author")) == surname
                        and str(b.get("year")) == year), None)
            if hit:
                ay_resolved.add(str(hit.get("id")))
            else:
                ay_unresolved.append({"token": m.group(0), "surname": m.group(1), "year": year})
        if ay_unresolved:
            blocking.append({"type": "dangling_citation", "tokens": [u["token"] for u in ay_unresolved],
                             "hint": "作者-年份引用在文献表里找不到同姓同年条目"})

    dangling = sorted(cited - bib_ids, key=lambda x: (len(x), x)) if style == "numeric" else []
    if dangling:
        blocking.append({"type": "dangling_citation", "ids": dangling})

    if style == "numeric":
        nums = sorted(int(i) for i in bib_ids if str(i).isdigit())
        if nums != list(range(1, len(nums) + 1)):
            blocking.append({"type": "numbering_gap", "ids": nums,
                             "hint": "新编号必须是连续的 1..N"})
        if first_order and [str(i) for i in first_order] != [str(i) for i in nums]:
            blocking.append({"type": "order_mismatch", "first_appearance": first_order,
                             "bib_ids": nums, "hint": "编号须按正文首次出现顺序"})

    # 2 重复残留 / key 冲突 / 误合并
    groups, conflicts, advisories = renumber.merge_candidates(bib)
    if groups:
        blocking.append({"type": "duplicate_left", "groups": groups})
    keys = [b.get("key") for b in bib if b.get("key")]
    coll = sorted({k for k in keys if keys.count(k) > 1})
    if coll:
        blocking.append({"type": "key_collision", "keys": coll})
    if conflicts:
        blocking.append({"type": "merge_conflict", "pairs": conflicts})
    if advisories:
        advisory.append({"type": "possible_same_year_pair", "pairs": advisories})

    # 2c 重排身份保持：from_id 指向的原论文必须与 bib 条目同一篇（DOI+标题）
    orig_by_id2 = {str(o.get("id")): o for o in orig}
    identity_ok = identity_checked = 0
    for m in mapping:
        fid, bid = str(m.get("from_id")), str(m.get("bib_id"))
        o = orig_by_id2.get(fid)
        b = next((x for x in bib if str(x.get("id")) == bid), None)
        if not o or not b:
            continue
        identity_checked += 1
        d1, d2 = renumber.doi_norm(o.get("doi")), renumber.doi_norm(b.get("doi"))
        same_doi = bool(d1) and d1 == d2   # 两边都没 DOI 不算"同 DOI"，否则改标题永远抓不到 C12
        same_title = renumber.similar_title(o.get("title", ""), b.get("title", "")) > 0.9
        # 身份只要一个强信号成立即可：DOI 相同而标题改了 = 标题被改写（C08 会报），
        # 不是"编号指向另一篇"。两个信号都变才算指错篇。原写法用 and，改标题必然误报 C12。
        if same_doi or same_title:
            identity_ok += 1
        else:
            blocking.append({"type": "renumber_mismatch", "from_id": fid, "bib_id": bid,
                             "hint": "重排后编号指向了另一篇论文（DOI/标题变了）",
                             "doi": [o.get("doi"), b.get("doi")],
                             "title": [o.get("title"), b.get("title")]})

    # 2d DOI 格式：双前缀/重复前缀
    bad_doi = [{"id": b.get("id"), "doi": b.get("doi")} for b in bib
               if b.get("doi") and renumber.doi_format_bad(b.get("doi"))]
    if bad_doi:
        blocking.append({"type": "doi_format", "items": bad_doi,
                         "hint": "DOI 出现 urn:doi:urn:doi: 之类的重复前缀"})
    orig_by_id = {str(o.get("id")): o for o in orig}
    for mid in res.get("merged_ids") or []:
        o = orig_by_id.get(str(mid))
        if not o:
            continue
        survivor = next((b for b in bib
                         if renumber.author_norm(b) == renumber.author_norm(o)
                         and str(b.get("year")) == str(o.get("year")
                                                       )), None)
        if not survivor:
            continue
        d1, d2 = (o.get("doi") or "").lower(), (survivor.get("doi") or "").lower()
        if d1 and d2 and d1 != d2:
            blocking.append({"type": "merge_conflict", "merged_id": mid,
                             "survivor": survivor.get("id"),
                             "doi_a": o.get("doi"), "doi_b": survivor.get("doi"),
                             "hint": "标题相似但 DOI 不同，属于会议版/期刊版，不能合并"})

    # 3 映射一致
    for m in mapping:
        b = str(m.get("bib_id"))
        if b not in bib_ids:
            blocking.append({"type": "mapping_mismatch", "entry": m, "note": "bib_id 不存在"})
        if style == "numeric" and m.get("citation"):
            want = m.get("citation").strip("[]")
            if str(b) not in renumber.expand(want):
                blocking.append({"type": "mapping_mismatch", "entry": m,
                                 "note": "citation 与 bib_id 不符"})
        if not m.get("key") or m.get("key") not in {x.get("key") for x in bib}:
            blocking.append({"type": "mapping_mismatch", "entry": m, "note": "key 不在文献表"})

    # 4 元数据零编造 / 零丢失（逐字段比对原始来源）
    verbatim_ok = 0
    checked = 0
    for b in bib:
        o = _match_original(b, orig)
        if not o:
            blocking.append({"type": "fabricated_entry", "id": b.get("id"), "title": b.get("title")})
            continue
        for f in FIELDS:
            checked += 1
            ov, bv = o.get(f), b.get(f)
            if bv and not ov:
                blocking.append({"type": "fabricated_field", "id": b.get("id"), "field": f, "value": bv})
            elif ov and not bv:
                blocking.append({"type": "metadata_loss", "id": b.get("id"), "field": f, "value": ov})
            elif (ov or "").strip() != (bv or "").strip():
                blocking.append({"type": "fabricated_field", "id": b.get("id"), "field": f,
                                 "input": ov, "output": bv, "hint": "字段被改写"})
            else:
                verbatim_ok += 1

    # 5 claim_source_map 覆盖正文每处引用
    mapped_ids = set()
    for c in claim_map:
        mapped_ids.update(str(i) for i in c.get("source_ids", []))
    if style == "numeric":
        if cited - mapped_ids:
            blocking.append({"type": "claim_map_gap", "ids": sorted(cited - mapped_ids)})
    else:
        mapped_keys = {k for c in claim_map for k in c.get("source_keys", [])}
        mapped_ids_ay = set()
        for c in claim_map:
            mapped_ids_ay.update(str(i) for i in c.get("source_ids", []))
        missing_ay = ay_resolved - mapped_ids_ay
        if occ and not mapped_keys:
            blocking.append({"type": "claim_map_gap", "hint": "author-year 正文有引用但 claim_source_map 为空"})
        elif missing_ay:
            blocking.append({"type": "claim_map_gap", "ids": sorted(missing_ay),
                             "hint": "author-year 有引用未被 claim_source_map 覆盖"})

    unused = [str(b.get("id")) for b in bib if not b.get("cited", True)]
    if unused:
        advisory.append({"type": "listed_not_cited", "ids": unused})

    totals = {
        "cited": len(cited), "bib": len(bib), "mapping": len(mapping),
        "claim_map": len(claim_map), "occurrences": occ,
        "citation_closure_rate": (rate(len(cited) - len(dangling), len(cited)) if style == "numeric" and cited
                                  else rate(occ - len(ay_unresolved), occ) if occ else None),
        "metadata_verbatim_rate": rate(verbatim_ok, checked),
        "claim_map_coverage": (rate(len(mapped_ids & cited), len(cited)) if style == "numeric" and cited
                               else rate(len(ay_resolved) - len(ay_resolved - mapped_ids_ay), len(ay_resolved))
                               if ay_resolved else None),
        "dedup_groups": len(groups),
        "renumber_identity_rate": rate(identity_ok, identity_checked),
    }
    for item in blocking + advisory:
        item.setdefault("code", CODES.get(item["type"], "A00"))
    return {"blocking": blocking, "advisory": advisory, "rates": totals,
            "pass": not blocking}


def render(result: dict, report: dict) -> str:
    res = result.get("result") or {}
    r = report["rates"]
    lines = ["# 引用链审计", "",
             f"- 正文引用 {r['occurrences']} 处 / 文献表 {r['bib']} 条 / 映射 {r['mapping']} 条", ""]
    lines += ["## 保留率", "", "| 指标 | 值 |", "|---|---|"]
    for k in ("citation_closure_rate", "metadata_verbatim_rate", "claim_map_coverage"):
        v = r.get(k)
        lines.append(f"| {k} | {'—（无此项）' if v is None else v} |")
    lines += ["", "## 文献表", "", "| id | key | 作者 | 年份 | 来源 | DOI |", "|---|---|---|---|---|---|"]
    for b in res.get("bibliography") or []:
        lines.append(f"| {b.get('id','')} | {b.get('key','')} | {b.get('author','')} | "
                     f"{b.get('year','')} | {b.get('source','')} | {b.get('doi','') or '—'} |")
    lines += ["", "## 结论", ""]
    if not report["blocking"]:
        lines.append("- 引用闭环，编号连续且与首次出现顺序一致，元数据逐字来自原始来源。")
    for b in report["blocking"]:
        lines.append(f"- **阻断** `{b['code']}` {b['type']}：{json.dumps(b, ensure_ascii=False)}")
    for a in report["advisory"]:
        lines.append(f"- 提示 `{a['code']}` {a['type']}：{json.dumps(a, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--case")
    ap.add_argument("--out")
    a = ap.parse_args()
    result = load(a.result)
    case = load(a.case) if a.case else {}
    report = audit(result, case)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(render(result, report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

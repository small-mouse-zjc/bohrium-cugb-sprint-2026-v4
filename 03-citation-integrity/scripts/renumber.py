#!/usr/bin/env python3
"""03 引用重排引擎：编号连锁更新、去重合并、元数据零编造。

输入：manuscript（含 [n] 或 (Author, Year) 引用）、bibliography（原始文献表）、
     style（numeric / author-year）
输出：重排后的正文、新编号的文献表、number_mapping、claim_source_map、uncertainty

原则：
  1. 新编号按"首次出现顺序"，不复用被删号；
  2. 合并只认三条同时成立（作者姓+首字母、年份、标题相似度>0.9），DOI 不同不合并；
  3. 输出条目的元数据逐字来自输入，缺什么就 null + uncertainty，绝不补全。
"""
from __future__ import annotations

import difflib
import re

NUM_CITE = re.compile(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]")
AUTH_YEAR = re.compile(r"\(([A-Z][A-Za-z\-]+)(?: et al\.| (?:&|and) [A-Z][A-Za-z\-]+)?,\s*(\d{4})\)")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

FIELDS = ("author", "year", "title", "source", "doi", "volume", "pages", "publisher", "url")


def expand(spec: str) -> list:
    out = []
    for part in re.split(r"[,;]", spec):
        part = part.strip()
        if re.fullmatch(r"\d+", part):
            out.append(part)
        elif re.fullmatch(r"\d+\s*[-–]\s*\d+", part):
            a, b = re.split(r"[-–]", part)
            out.extend(str(i) for i in range(int(a), int(b) + 1))
    return out


def author_norm(entry: dict) -> str:
    a = str(entry.get("author") or "")
    a = a.split(",")[0].split(" and ")[0].split(" & ")[0]
    a = re.sub(r"[^A-Za-z\- ]", "", a).strip().split(" ")[0]
    return a.lower()


def title_norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower()).strip()


def similar_title(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, title_norm(a), title_norm(b)).ratio()


def merge_candidates(bib: list) -> tuple:
    """返回 (merge_groups, version_conflicts)。"""
    groups, conflicts = [], []
    used = set()
    for i, a in enumerate(bib):
        if i in used:
            continue
        group = [i]
        for j in range(i + 1, len(bib)):
            if j in used:
                continue
            b = bib[j]
            same_author = author_norm(a) and author_norm(a) == author_norm(b)
            same_year = str(a.get("year")) == str(b.get("year"))
            sim = similar_title(a.get("title", ""), b.get("title", ""))
            if same_author and same_year and sim > 0.9:
                doi_a, doi_b = (a.get("doi") or "").lower(), (b.get("doi") or "").lower()
                if doi_a and doi_b and doi_a != doi_b:
                    conflicts.append({"a": a.get("id"), "b": b.get("id"), "similarity": round(sim, 3),
                                      "doi_a": a.get("doi"), "doi_b": b.get("doi")})
                    continue
                group.append(j)
                used.add(j)
        if len(group) > 1:
            groups.append(group)
    return groups, conflicts


def richer(a: dict, b: dict) -> dict:
    """保留信息更全的一条：非空字段多者胜；字段值逐字来自输入。"""
    def filled(e):
        return sum(1 for f in FIELDS if e.get(f))
    return a if filled(a) >= filled(b) else b


def renumber(manuscript: str, bib: list, style: str = "numeric") -> dict:
    merge_groups, conflicts = merge_candidates(bib)
    merged_into, merged_ids = {}, []
    canonical = {}
    for group in merge_groups:
        best = bib[group[0]]
        for idx in group[1:]:
            best = richer(best, bib[idx])
            merged_into[str(bib[idx].get("id"))] = str(bib[group[0]].get("id"))
            merged_ids.append(str(bib[idx].get("id")))
        canonical[str(bib[group[0]].get("id"))] = best

    key_index = {}
    for i, b in enumerate(bib):
        cid = merged_into.get(str(b.get("id")), str(b.get("id")))
        key_index.setdefault(str(b.get("key") or ""), cid)

    def resolve(token: str, context: str = "") -> str | None:
        if token.isdigit():
            cid = merged_into.get(token, token)
            return cid if cid in {str(b.get("id")) for b in bib} else None
        return key_index.get(token)

    def resolve_author_year(m: re.Match) -> str | None:
        surname, year = m.group(1).lower(), m.group(2)
        for b in bib:
            if author_norm(b) == surname and str(b.get("year")) == year:
                return merged_into.get(str(b.get("id")), str(b.get("id")))
        return None

    order, unresolved, occurrences = [], [], []
    pattern = NUM_CITE if style == "numeric" else AUTH_YEAR

    def scan(text: str) -> str:
        def repl(m):
            if style == "numeric":
                ids = expand(m.group(1))
                resolved = [resolve(i, text) for i in ids]
            else:
                resolved = [resolve_author_year(m)]
            good = [r for r in resolved if r]
            for r in good:
                if r not in order:
                    order.append(r)
                occurrences.append({"token": m.group(0), "id": r, "sentence": sentence_of(text, m.start())})
            if len(good) != len(resolved) or not good:
                unresolved.append({"token": m.group(0), "context": text[max(0, m.start() - 20):m.start() + 20]})
                return m.group(0)
            if style == "numeric":
                return "[" + ",".join(str(order.index(r) + 1) for r in good) + "]"
            first = [b for b in bib if merged_into.get(str(b.get("id")), str(b.get("id"))) == good[0]]
            e = first[0] if first else {}
            surname = str(e.get("author") or "Unknown").split(",")[0].split(" ")[0]
            etal = " et al." if (" et al" in str(e.get("author")) or len([x for x in str(e.get("author")).split(",") if x.strip()]) > 1) else ""
            return f"({surname}{etal}, {e.get('year')})"
        return pattern.sub(repl, text)

    new_manuscript = scan(manuscript)

    new_bib, mapping = [], []
    for n, cid in enumerate(order, 1):
        entry = canonical.get(cid) or next(b for b in bib if str(b.get("id")) == cid)
        out = {f: entry.get(f) for f in FIELDS}
        out["id"] = str(n)
        out["key"] = entry.get("key")
        out["cited"] = True
        new_bib.append(out)
        mapping.append({"citation": f"[{n}]" if style == "numeric" else None, "key": entry.get("key"),
                        "bib_id": str(n), "from_id": cid})

    unused = []
    for b in bib:
        cid = merged_into.get(str(b.get("id")), str(b.get("id")))
        if cid not in order:
            unused.append({"id": b.get("id"), "key": b.get("key"),
                           "title": b.get("title"), "reason": "listed_not_cited"})

    claim_map = []
    for sent in [s for s in SENT_SPLIT.split(manuscript) if s.strip()]:
        ids = []
        if style == "numeric":
            for m in NUM_CITE.finditer(sent):
                ids += [resolve(i, sent) for i in expand(m.group(1))]
        else:
            for m in AUTH_YEAR.finditer(sent):
                ids.append(resolve_author_year(m))
        ids = [i for i in ids if i]
        if ids:
            new_ids = sorted({str(order.index(i) + 1) for i in ids if i in order})
            claim_map.append({"claim": sent.strip(), "source_ids": new_ids,
                              "from_ids": sorted(set(ids)),
                              "source_keys": sorted({str(next(b.get("key") for b in bib
                                                            if str(b.get("id")) == i)) for i in ids})})

    uncertainty = []
    for u in unresolved:
        uncertainty.append({"issue": f"引用 {u['token']} 在文献表找不到，保持原样未改", "context": u["context"]})
    for c in conflicts:
        uncertainty.append({"issue": f"{c['a']} 与 {c['b']} 标题相似但 DOI 不同，按会议版/期刊版分列不合并",
                            "doi": [c["doi_a"], c["doi_b"]]})
    for u in unused:
        uncertainty.append({"issue": f"文献表条目 {u['id']} 未被正文引用，保留并标注 listed_not_cited"})
    for b in new_bib:
        missing = [f for f in ("doi", "volume", "pages", "source") if not b.get(f)]
        if missing:
            uncertainty.append({"issue": f"条目 {b['id']} 缺 {','.join(missing)}：按原样留空，不补全"})

    return {"editable_manuscript": new_manuscript, "bibliography": new_bib,
            "number_mapping": mapping, "claim_source_map": claim_map,
            "merged_ids": merged_ids, "merge_groups": merge_groups,
            "version_conflicts": conflicts, "unused": unused,
            "unresolved": unresolved, "uncertainty": uncertainty,
            "style": style, "cited_order": order}


def sentence_of(text: str, pos: int) -> str:
    start = max(text.rfind(".", 0, pos), text.rfind("!", 0, pos), text.rfind("?", 0, pos))
    end = min([x for x in (text.find(".", pos), text.find("!", pos), text.find("?", pos)) if x != -1] or [len(text)])
    return text[start + 1:end + 1].strip()

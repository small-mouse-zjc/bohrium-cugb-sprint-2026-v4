#!/usr/bin/env python3
"""06 逐节笔记：从句子里抽"原文句 + 精确偏移"，不做改写，因此每句都能反查。

只做采选与归类，不生成新表述——这是本题"找得回"的硬约束。
"""
import re

ROLE_MARKERS = {
    "problem": ["we investigate", "this study", "aim of", "objective", "we ask", "research question",
                "hypothes", "purpose", "here we", "we examine"],
    "data": ["sample", "samples", "dataset", "core", "cores", "specimen", "collected",
             "collected from", "n =", "g wet", "specimens"],
    "method": ["method", "procedure", "using", "performed", "experiment", "simulation", "model",
               "analys", "measured by", "instrument", "protocol", "we used", "was carried out"],
    "finding": ["we find", "results show", "result shows", "indicat", "suggest", "observed",
                "increase", "decrease", "higher", "lower", "compared", "correlat", "reveal"],
    "limitation": ["limitation", "caveat", "uncertain", "not account", "cannot", "does not",
                   "further work", "remains unclear", "constrain"],
    "premise": ["if ", "assuming", "assume", "assum", "under ", "provided that", "condition",
                "only when", "requires", "prerequisite"],
}

# 角色歧义时的偏好序：条件/局限/方法优先，data 最容易被单位词误触发，放最后
ROLE_ORDER = ["premise", "limitation", "method", "finding", "problem", "data"]

PRIORITY_SECTION = {           # 键必须与 ROLE_MARKERS / ROLE_ORDER 同一口径（单数角色名）
    "problem": ["abstract", "introduction", "summary"],
    "data": ["method", "material", "experiment", "result"],
    "method": ["method", "material", "experiment"],
    "finding": ["result", "discussion", "abstract", "conclusion"],
    "limitation": ["limitation", "discussion", "conclusion"],
    "premise": ["method", "discussion", "introduction"],
}

SENT_RE = re.compile(r"[^\n]{15,400}?(?:[.!?。！？](?=\s|$)|$)")
MIN_LEN, MAX_LEN = 30, 240
ABBREV_TAIL = re.compile(
    r"(?:Fig|Figs|Eq|Eqs|Ref|Refs|No|Sect|Sec|Tab|vs|cf|ca|approx|al|e\.g|i\.e|etc|vol|pp|p)\.$",
    re.I)


def _abbrev_end(seg):
    """句尾是缩写（Fig./et al./e.g.）或以数字+点结尾（3.5 / 0.7）→ 不该在此切句。"""
    tail = seg.strip()
    if not tail:
        return True
    if ABBREV_TAIL.search(tail):
        return True
    if re.search(r"\d\.$", tail):
        return True
    return False


def sentences(para_text, base):
    """返回 [(sent_text, start, end)]，start/end 是全局偏移，sent_text 是原文切片。

    切句后做一次合并：遇到缩写尾巴或小数点的"句"与下一段拼接，避免把
    `Fig. 3 shows ...` 切成 `Fig.` + `3 shows ...` 两个残句。
    """
    raw = [(m.start(), m.end()) for m in SENT_RE.finditer(para_text)]
    merged = []
    for s, e in raw:
        if merged and _abbrev_end(para_text[merged[-1][0]:merged[-1][1]]):
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    out = []
    for s, e in merged:
        seg = para_text[s:e].strip()
        if len(seg) < MIN_LEN or len(seg) > MAX_LEN:
            continue
        lead = len(para_text[s:e]) - len(para_text[s:e].lstrip())
        out.append((seg, base + s + lead, base + s + lead + len(seg)))
    return out


def _roles(sent_low):
    hits = {}
    for role, keys in ROLE_MARKERS.items():
        n = sum(1 for k in keys if k in sent_low)
        if n:
            hits[role] = n
    return hits


def _score(sent, roles):
    nums = len(re.findall(r"\d+(?:\.\d+)?", sent))
    return sum(roles.values()) * 2 + min(nums, 3) + min(len(sent), 200) / 200.0


def _section_bonus(sec_heading, role):
    h = (sec_heading or "").lower()
    return 2 if any(k in h for k in PRIORITY_SECTION.get(role, [])) else 0


def build_notes(doc, per_section=3):
    """逐节抽句；返回 (notes, section_notes, warnings)。

    notes 每项含 quote（原文切片）、span、section_index、role、anchor。
    """
    notes, warnings = [], []
    for sec in doc["sections"]:
        cands = []
        for p in doc["paras"]:
            if p["section"] != sec["index"]:
                continue
            para_no = 1 + sum(1 for q in doc["paras"]
                              if q["section"] == sec["index"] and q["start"] < p["start"])
            for sent, s, e in sentences(p["text"], p["start"]):
                cands.append({"sent": sent, "start": s, "end": e, "para": para_no})
        if not cands:
            warnings.append({"issue": "section_without_sentences", "section": sec["heading"]})
            continue
        ranked = []
        for c in cands:
            roles = _roles(c["sent"].lower())
            if not roles:
                roles = {"background": 1}
            role = min(roles, key=lambda r: (-roles[r], ROLE_ORDER.index(r) if r in ROLE_ORDER else 99))
            ranked.append(dict(c, role=role, roles=roles,
                               score=_score(c["sent"], roles) + _section_bonus(sec["heading"], role)))
        ranked.sort(key=lambda x: -x["score"])

        chosen, seen_roles, used_spans = [], set(), []

        def take(c):
            chosen.append(c)
            seen_roles.add(c["role"])
            used_spans.append(c["start"])

        # 第一遍优先覆盖不同角色（同一节只来一条同角色），第二遍再补高分句
        for c in ranked:
            if len(chosen) >= per_section:
                break
            if c["role"] in seen_roles:
                continue
            if any(abs(c["start"] - s) < 20 for s in used_spans):
                continue
            take(c)
        for c in ranked:
            if len(chosen) >= per_section:
                break
            if any(abs(c["start"] - s) < 20 for s in used_spans):
                continue
            take(c)
        chosen.sort(key=lambda x: x["start"])

        for k, c in enumerate(chosen, 1):
            page = None
            for p in doc["paras"]:
                if p["start"] <= c["start"] < p["end"]:
                    page = p.get("page")
                    break
            anchor = f"§{sec['index']+1} ¶{c['para']}"
            if page:
                anchor += f" / p.{page}"
            anchor += f" [{c['start']}-{c['end']}]"
            notes.append({
                "note_id": f"S{sec['index']+1}-N{k}",
                "section": sec["heading"],
                "section_index": sec["index"],
                "role": c["role"],
                "quote": c["sent"],
                "anchor": anchor,
                "span": [c["start"], c["end"]],
                "page": page,
                "para": c["para"],
            })
    return notes, warnings


def render_sections(doc, notes):
    """section_alignment：每节一条，notes 字段由该节 note_id 引用的原文句组成。"""
    out = []
    for sec in doc["sections"]:
        mine = [n for n in notes if n["section_index"] == sec["index"]]
        out.append({
            "section": sec["heading"],
            "section_index": sec["index"],
            "notes": " ".join(n["quote"] for n in mine),
            "note_ids": [n["note_id"] for n in mine],
            "anchor": mine[0]["anchor"] if mine else "",
        })
    return out

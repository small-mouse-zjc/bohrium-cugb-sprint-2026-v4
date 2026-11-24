#!/usr/bin/env python3
"""06 阅读卡片：六字段从"角色匹配 + 小节优先级最高"的笔记里取，取不到就 not_reported。

卡片不生成新句子：值必须是某条笔记的原文句，并挂 support（note_id 列表）。
"""
import re

ROLE_TO_FIELD = {
    "problem": "problem",
    "data": "data",
    "method": "method",
    "finding": "findings",
    "limitation": "limitations",
    "premise": "premises",
}
FIELDS = ["problem", "data", "method", "findings", "limitations", "premises"]
NOT_REPORTED = "not_reported"

SECTION_PRIORITY = {
    "problem": ["abstract", "introduction", "summary", "背景"],
    "data": ["method", "material", "experiment", "result"],
    "method": ["method", "material", "experiment"],
    "findings": ["result", "discussion", "abstract", "conclusion"],
    "limitations": ["limitation", "discussion", "conclusion"],
    "premises": ["method", "discussion", "introduction"],
}


def _sec_rank(heading, field):
    h = str(heading or "").lower()
    for i, k in enumerate(SECTION_PRIORITY.get(field, [])):
        if k in h:
            return i
    return 99


def build_card(notes):
    card, support, gaps = {}, {}, []
    for f in FIELDS:
        roles = {r for r, v in ROLE_TO_FIELD.items() if v == f}
        mine = [n for n in notes if n["role"] in roles]
        if not mine:
            card[f] = NOT_REPORTED
            support[f] = []
            gaps.append({"field": f, "issue": "field_not_reported_in_source"})
            continue
        mine.sort(key=lambda n: (_sec_rank(n.get("section"), f),
                                 -len(re.findall(r"\d+(?:\.\d+)?", n["quote"])))
                 )
        best = mine[0]
        card[f] = best["quote"]
        support[f] = [best["note_id"]]
        other = next((n for n in mine[1:] if n["section_index"] != best["section_index"]), None)
        if other:
            support[f].append(other["note_id"])
    return card, support, gaps

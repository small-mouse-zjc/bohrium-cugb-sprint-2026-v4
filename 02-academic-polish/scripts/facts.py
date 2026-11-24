#!/usr/bin/env python3
"""02 事实标记抽取：数字+单位、引用、限定词、否定、比较级、强断言。

润色的红线是"改表达不改事实"。这里把可机器核对的标记抽成计数，
供 fact_ledger（改写前后比对）与 metrics（算比率）共用。
"""
from __future__ import annotations

import re

NUM_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9_.])(\d+(?:\.\d+)?)\s*([A-Za-zµμ%°][A-Za-z0-9µμ%°/·\-]*)")
CITE_RE = re.compile(r"\[\d+(?:\s*[-,–]\s*\d+)*\]|\([A-Z][A-Za-z.\-]+(?: et al\.)?,\s*\d{4}\)")

HEDGES = ["may", "might", "could", "possibly", "likely", "probably", "apparently",
          "suggest", "suggests", "suggested", "appear", "appears", "appeared",
          "seem", "seems", "seemed", "tend to", "tends to", "presumably", "arguably",
          "roughly", "approximately", "about", "around", "up to", "at most"]
NEGATIONS = ["not", "no ", "never", "none", "neither", "nor", "cannot", "can't",
             "isn't", "aren't", "wasn't", "weren't", "doesn't", "don't", "didn't",
             "without", "lack", "lacks", "lacked", "fail", "fails", "failed",
             "unable", "hardly", "barely", "rarely"]
COMPARATIVES = ["more than", "less than", "higher than", "lower than", "greater than",
                "fewer", "larger", "smaller", "increase", "increases", "increased",
                "decrease", "decreases", "decreased", "rise", "rises", "rose",
                "decline", "declines", "declined", "exceed", "exceeds", "exceeded",
                "below", "above", "twice", "twofold", "threefold", "fold",
                "rather than", "compared with", "compared to"]
STRONG = ["prove", "proves", "proved", "demonstrate", "demonstrates", "demonstrated",
          "confirm", "confirms", "confirmed", "establish", "establishes", "established",
          "significant", "significantly", "definitively", "clearly", "undoubtedly",
          "always", "certainly", "conclusively"]

# 数字后面紧跟的普通词不是单位（避免 "0 to" 被当成 "0 to" 这个标记）
UNIT_STOP = {"to", "and", "of", "in", "at", "by", "from", "with", "for", "is", "are",
             "was", "were", "as", "the", "a", "an", "than", "that", "which", "we",
             "it", "this", "these", "those", "on", "or", "per", "each", "every"}


def _count(text: str, vocab) -> dict:
    low = " " + (text or "").lower() + " "
    out = {}
    for w in vocab:
        key = w.strip()
        n = low.count(" " + key + " ") if key and " " not in key else low.count(" " + key + " ")
        if key in ("no ", "no"):
            n = len(re.findall(r"\bno\b", low))
        if n:
            out[key] = n
    return out


def numbers(text: str) -> list:
    """数字+单位配对。'3.5 wt%' 与 '3.5%' 是不同标记，改单位会被抓到。"""
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(wt|vol|mol|at)\s*%", r"\1 \2%", text or "", flags=re.I)
    out = []
    for m in NUM_UNIT_RE.finditer(t):
        num, unit = m.group(1), m.group(2)
        if unit.lower() in UNIT_STOP:
            out.append(num)
            continue
        out.append(f"{num} {unit}".strip().lower())
    return out


def bare_numbers(text: str) -> list:
    return [m.group(1) for m in NUM_UNIT_RE.finditer(text or "")]


def citations(text: str) -> list:
    return [m.group(0).replace(" ", "") for m in CITE_RE.finditer(text or "")]


def extract(text: str) -> dict:
    return {
        "number_units": numbers(text),
        "citations": citations(text),
        "hedges": _count(text, HEDGES),
        "negations": _count(text, NEGATIONS),
        "comparatives": _count(text, COMPARATIVES),
        "strong_claims": _count(text, STRONG),
    }


def fact_tokens(text: str) -> set:
    """用于 change 条目级比对的最小事实集合（数字+单位、引用）。"""
    return set(numbers(text)) | set(citations(text))


FACT_TYPES = ("number_units", "citations", "hedges", "negations", "comparatives")

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
INTENSITY = ["significantly", "slightly", "markedly", "substantially", "considerably",
             "marginally", "somewhat", "strongly", "weakly", "greatly", "moderately", "sharply"]

# 单位家族（用于识别"数值也变的等价换算"，如 0.9 MPa → 900 kPa）
UNIT_FAMILIES = {
    "pa": ("pressure", 1.0, 0.0), "kpa": ("pressure", 1e3, 0.0),
    "mpa": ("pressure", 1e6, 0.0), "gpa": ("pressure", 1e9, 0.0),
    "bar": ("pressure", 1e5, 0.0), "atm": ("pressure", 101325.0, 0.0),
    "k": ("temperature", 1.0, 0.0), "°c": ("temperature", 1.0, 273.15),
    "c": ("temperature", 1.0, 273.15),
    "mg": ("mass", 1e-3, 0.0), "µg": ("mass", 1e-6, 0.0), "ug": ("mass", 1e-6, 0.0),
    "g": ("mass", 1.0, 0.0), "kg": ("mass", 1e3, 0.0),
}
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
    """按单词边界计数，不靠两侧空格。

    旧实现 low.count(" may ") 只在词两侧都是空格时命中，于是 "may," / "not;"
    / "significantly." 这类紧跟标点的限定词、否定词、程度副词全被漏计，
    删掉它们不会触发 hedge_loss / negation_flip / intensity_loss。
    改用 (?<!\w)…(?!\w) 边界（多词短语内部空格放宽为 \s+）。
    """
    low = (text or "").lower()
    out = {}
    for w in vocab:
        key = w.strip()
        if not key:
            continue
        pat = r"(?<!\w)" + re.escape(key).replace(r"\ ", r"\s+") + r"(?!\w)"
        n = len(re.findall(pat, low))
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


def equivalent(token_a: str, token_b: str) -> bool:
    """判断两个数字+单位是否数值等价（允许单位换算，如 0.9 MPa ↔ 900 kPa）。"""
    def parse(tok):
        parts = tok.split(" ")
        if len(parts) != 2:
            return None
        raw, unit = parts
        fam = UNIT_FAMILIES.get(unit.lower())
        if not fam:
            return None
        try:
            return fam[0], float(raw) * fam[1] + fam[2]
        except ValueError:
            return None
    a, b = parse(token_a), parse(token_b)
    if not a or not b or a[0] != b[0]:
        return False
    return abs(a[1] - b[1]) <= 1e-6 * max(1.0, abs(a[1]), abs(b[1]))


def citations(text: str) -> list:
    return [m.group(0).replace(" ", "") for m in CITE_RE.finditer(text or "")]


def extract(text: str) -> dict:
    return {
        "number_units": numbers(text),
        "citations": citations(text),
        "hedges": _count(text, HEDGES),
        "negations": _count(text, NEGATIONS),
        "comparatives": _count(text, COMPARATIVES),
        "intensity": _count(text, INTENSITY),
        "strong_claims": _count(text, STRONG),
    }


def fact_tokens(text: str) -> set:
    """用于 change 条目级比对的最小事实集合（数字+单位、引用）。"""
    return set(numbers(text)) | set(citations(text))


FACT_TYPES = ("number_units", "citations", "hedges", "negations", "comparatives", "intensity")

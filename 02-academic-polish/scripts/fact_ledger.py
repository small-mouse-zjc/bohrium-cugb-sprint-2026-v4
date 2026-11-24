#!/usr/bin/env python3
"""02 事实台账：逐句对齐 + 逐条改动核验，回答"事实有没有被润色改掉"。

输出：
  blocking  阻断项（数字/引用/限定/否定/比较级丢失、编造引用、未声明的改事实、整句丢失、未记录的改写）
  advisory  提示项（改动与原文对不上、改写幅度大、改动幅度比）
  ledger    逐句对齐表（原句 → 润色句、相似度、事实差异）
  rates     可复算的保留率（分母为 0 记 None，不记 1.00）
"""
from __future__ import annotations

import difflib
import re

import facts

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

# 阻断项编号（文档里逐条对应，便于评委按码复现）
CODES = {
    "number_or_unit_loss": "F01",
    "citation_loss": "F02",
    "citation_added": "F03",
    "hedge_loss": "F04",
    "strength_upgrade": "F05",
    "negation_flip": "F06",
    "comparative_loss": "F07",
    "sentence_dropped": "F08",
    "unlogged_new_sentence": "F09",
    "undeclared_fact_change": "F10",
    "change_unmatched": "A01",
    "sentence_rewritten": "A02",
    "edit_ratio": "A03",
    "revised_not_in_polished": "A04",
    "fact_flag_false_positive": "A05",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def sentences(text: str) -> list:
    return [s.strip() for s in SENT_SPLIT.split(_norm(text)) if s.strip()]


def _rate(a, b):
    return round(a / b, 4) if b else None


def _count_map_diff(before: dict, after: dict) -> dict:
    return {k: {"before": v, "after": after.get(k, 0)} for k, v in before.items()
            if after.get(k, 0) < v}


def audit(original: str, polished: str, changes=None) -> dict:
    changes = changes or []
    orig_f = facts.extract(original)
    pol_f = facts.extract(polished)
    blocking, advisory = [], []

    # 1) 数字+单位：逐条比对，单位变了也算丢
    miss = {}
    for tok in set(orig_f["number_units"]):
        if orig_f["number_units"].count(tok) > pol_f["number_units"].count(tok):
            miss[tok] = {"before": orig_f["number_units"].count(tok),
                         "after": pol_f["number_units"].count(tok)}
    if miss:
        hints = []
        for tok in miss:
            num = tok.split(" ")[0]
            if num in facts.bare_numbers(polished):
                hints.append(f"{tok} → 数字还在但单位/后缀变成别的写法")
        blocking.append({"type": "number_or_unit_loss", "tokens": miss, "hint": hints})

    # 2) 引用：丢一条阻断，凭空多一条也阻断
    lost_cite = [c for c in set(orig_f["citations"])
                 if orig_f["citations"].count(c) > pol_f["citations"].count(c)]
    new_cite = [c for c in set(pol_f["citations"]) if c not in orig_f["citations"]]
    if lost_cite:
        blocking.append({"type": "citation_loss", "tokens": lost_cite})
    if new_cite:
        blocking.append({"type": "citation_added", "tokens": new_cite,
                         "hint": "原文没有的引用不许出现"})

    # 3) 限定词减少 / 强断言增加
    hedge_drop = _count_map_diff(orig_f["hedges"], pol_f["hedges"])
    if hedge_drop:
        blocking.append({"type": "hedge_loss", "tokens": hedge_drop,
                         "hint": "推测语气被删，主张强度被抬高"})
    strong_new = {k: v for k, v in pol_f["strong_claims"].items()
                  if v > orig_f["strong_claims"].get(k, 0)}
    if strong_new and (hedge_drop or any(
            h in original.lower() for h in ("may", "might", "could", "suggest", "likely"))):
        blocking.append({"type": "strength_upgrade", "tokens": strong_new})

    # 4) 否定与比较级
    neg_drop = _count_map_diff(orig_f["negations"], pol_f["negations"])
    if neg_drop:
        blocking.append({"type": "negation_flip", "tokens": neg_drop})
    cmp_drop = _count_map_diff(orig_f["comparatives"], pol_f["comparatives"])
    if cmp_drop:
        blocking.append({"type": "comparative_loss", "tokens": cmp_drop})

    # 5) 逐句对齐：整句丢了 / 改写没记录
    orig_sents, pol_sents = sentences(original), sentences(polished)
    ledger = []
    if orig_sents and pol_sents:
        for i, o in enumerate(orig_sents):
            best, best_r = None, 0.0
            for j, p in enumerate(pol_sents):
                r = difflib.SequenceMatcher(None, o, p).ratio()
                if r > best_r:
                    best, best_r = j, r
            rec = {"i": i, "original": o, "polished_index": best,
                   "polished": pol_sents[best] if best is not None else None,
                   "similarity": round(best_r, 3),
                   "facts_before": sorted(facts.fact_tokens(o)),
                   "facts_after": sorted(facts.fact_tokens(pol_sents[best]) if best is not None else [])}
            ledger.append(rec)
            if best_r < 0.45:
                blocking.append({"type": "sentence_dropped", "index": i, "original": o[:80]})
            elif best_r < 0.85:
                advisory.append({"type": "sentence_rewritten", "index": i,
                                 "similarity": round(best_r, 3)})

        changed_revised = " ".join(_norm(str(c.get("revised", ""))) for c in changes)
        for j, p in enumerate(pol_sents):
            r = max(difflib.SequenceMatcher(None, p, o).ratio() for o in orig_sents)
            if r < 0.6 and _norm(p) not in changed_revised:
                blocking.append({"type": "unlogged_new_sentence", "index": j, "polished": p[:80]})

    # 6) 逐条改动：可回指 + 事实变化必须显式声明
    unmatched, undeclared, over_declared = [], [], []
    for k, c in enumerate(changes):
        o, r = _norm(str(c.get("original", ""))), _norm(str(c.get("revised", "")))
        if o and o not in _norm(original):
            unmatched.append({"index": k, "original": o[:60]})
        if r and r not in _norm(polished):
            advisory.append({"type": "revised_not_in_polished", "index": k, "revised": r[:60]})
        if o and r:
            fb, fa = facts.fact_tokens(o), facts.fact_tokens(r)
            changed = fb != fa
            if changed and not c.get("fact_changed"):
                undeclared.append({"index": k, "before": sorted(fb), "after": sorted(fa)})
            elif c.get("fact_changed") and not changed:
                over_declared.append({"index": k})
    if unmatched:
        advisory.append({"type": "change_unmatched", "items": unmatched})
    if undeclared:
        blocking.append({"type": "undeclared_fact_change", "items": undeclared})
    if over_declared:
        advisory.append({"type": "fact_flag_false_positive", "items": over_declared})

    orig_n, pol_n = len(orig_f["number_units"]), len(pol_f["number_units"])
    c_n0, c_n1 = len(orig_f["citations"]), len(pol_f["citations"])
    h_n0 = sum(orig_f["hedges"].values())
    g_n0 = sum(orig_f["negations"].values())
    rates = {
        "number_retention": _rate(orig_n - sum(1 for t in set(orig_f["number_units"])
                                               if orig_f["number_units"].count(t) >
                                               pol_f["number_units"].count(t)), orig_n),
        "citation_retention": _rate(c_n0 - len(lost_cite), c_n0) if c_n0 else None,
        "hedge_retention": _rate(h_n0 - sum(v["before"] - v["after"] for v in hedge_drop.values()), h_n0) if h_n0 else None,
        "negation_retention": _rate(g_n0 - sum(v["before"] - v["after"] for v in neg_drop.values()), g_n0) if g_n0 else None,
        "sentence_coverage": _rate(sum(1 for x in ledger if x["similarity"] >= 0.45), len(ledger))
        if ledger else None,
        "changes": len(changes),
        "stray_citations": len(new_cite),
        "strong_claims_after": sum(pol_f["strong_claims"].values()),
        "original_chars": len(original or ""),
        "polished_chars": len(polished or ""),
    }
    ratio = round(len(polished or "") / max(1, len(original or "")), 2) if original else None
    rates["length_ratio"] = ratio
    if ratio is not None and (ratio < 0.7 or ratio > 1.4):
        advisory.append({"type": "edit_ratio", "ratio": ratio,
                         "hint": "改动幅度过大，确认是润色还是重写"})

    for item in blocking + advisory:
        item.setdefault("code", CODES.get(item.get("type"), "A00"))

    return {"blocking": blocking, "advisory": advisory, "ledger": ledger, "rates": rates,
            "pass": not blocking}

def render(report, polished_note: str = "") -> str:
    lines = ["# 润色事实台账", "", polished_note, ""]
    r = report["rates"]
    lines += ["## 保留率", "", "| 指标 | 值 |", "|---|---|"]
    for k in ("number_retention", "citation_retention", "hedge_retention",
              "negation_retention", "sentence_coverage", "changes", "length_ratio"):
        v = r.get(k)
        lines.append(f"| {k} | {'—（无此项）' if v is None else v} |")
    lines += ["", "## 逐句对齐", "", "| # | 原句 | 润色后 | 相似度 | 事实标记变化 |", "|---|---|---|---|---|"]
    for x in report["ledger"]:
        fb, fa = set(x["facts_before"]), set(x["facts_after"])
        delta = "同一组" if fb == fa else f"{sorted(fb)} → {sorted(fa)}"
        lines.append(f"| {x['i']+1} | {x['original'][:36]} | {str(x['polished'])[:36]} | "
                     f"{x['similarity']} | {delta} |")
    lines += ["", "## 结论", ""]
    if not report["blocking"]:
        lines.append("- 数字/单位、引用、限定词、否定、比较级全部守恒，无未声明的事实改动。")
    for b in report["blocking"]:
        lines.append(f"- **阻断** `{b['type']}`：{b}")
    for a in report["advisory"]:
        lines.append(f"- 提示 `{a['type']}`：{a}")
    return "\n".join(lines) + "\n"

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
    "unit_change": "F01b",
    "number_added": "F11",
    "intensity_loss": "F12",
    "intensity_added": "F12b",
    "unit_conversion": "F01c",
    "citation_moved": "F13",
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


# 只认"写法归一"，不认"数值换算"：3.5 wt% → 3.5 wt % 放行；3.5 wt% → 3.5% 报 unit_change
UNIT_ALIAS = {
    "℃": "°c", "ºc": "°c", "° c": "°c", "oc": "°c",
    "wt %": "wt%", "weight%": "wt%", "wt pct": "wt%",
    "percent": "%", "pct": "%", "per cent": "%",
    "×": "x", "μ": "µ",
}


def _canon_token(tok: str) -> str:
    s = tok.lower().replace("  ", " ").strip()
    for a, b in UNIT_ALIAS.items():
        s = s.replace(a, b)
    return s.replace(" ", "")


def _normalized_variant(tok: str, polished_tokens: list):
    """同一数字+同一单位的另一种写法（空格/符号/大小写）→ normalized。"""
    key = _canon_token(tok)
    for t in polished_tokens:
        if _canon_token(t) == key and t != tok:
            return t
    return None


def _count_map_diff(before: dict, after: dict) -> dict:
    return {k: {"before": v, "after": after.get(k, 0)} for k, v in before.items()
            if after.get(k, 0) < v}


def _content_cover(src: str, merged: str) -> float:
    """源句的实词有多少比例能在合并句里找到（用于区分"合并"与"整句丢失"）。"""
    toks = {w for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", (src or "").lower())}
    if not toks:
        return 0.0
    low = (merged or "").lower()
    hit = sum(1 for w in toks if w in low)
    return hit / len(toks)


def audit(original: str, polished: str, changes=None) -> dict:
    changes = changes or []
    orig_f = facts.extract(original)
    pol_f = facts.extract(polished)
    blocking, advisory = [], []

    # 1) 数字+单位：逐条判定 kept / normalized / changed / removed / added
    fact_rows = []
    miss, unit_changed, normalized, converted = {}, {}, {}, {}
    converted_tokens = set()
    for tok in set(orig_f["number_units"]):
        before, after = orig_f["number_units"].count(tok), pol_f["number_units"].count(tok)
        if after >= before:
            fact_rows.append({"type": "number_unit", "token": tok, "status": "kept"})
            continue
        num = tok.split(" ")[0]
        equiv = _normalized_variant(tok, pol_f["number_units"])
        conv = next((t for t in pol_f["number_units"] if t not in orig_f["number_units"]
                     and facts.equivalent(tok, t)), None)
        if equiv:
            normalized[tok] = equiv
            fact_rows.append({"type": "number_unit", "token": tok, "status": "normalized",
                              "as": equiv})
        elif conv:
            converted[tok] = conv
            converted_tokens.add(conv)
            fact_rows.append({"type": "number_unit", "token": tok, "status": "changed",
                              "as": conv, "note": "数值等价换算，需人工确认是否保留原单位"})
        elif num in facts.bare_numbers(polished):
            unit_changed[tok] = {"number": num, "polished_forms": [t for t in pol_f["number_units"]
                                                                   if t.split(" ")[0] == num]}
            fact_rows.append({"type": "number_unit", "token": tok, "status": "changed",
                              "as": unit_changed[tok]["polished_forms"]})
        else:
            miss[tok] = {"before": before, "after": after}
            fact_rows.append({"type": "number_unit", "token": tok, "status": "removed"})
    if miss:
        blocking.append({"type": "number_or_unit_loss", "tokens": miss})
    if converted:
        blocking.append({"type": "unit_conversion", "tokens": converted,
                         "hint": "数值等价但单位换了（如 0.9 MPa→900 kPa），需人工确认"})
    if unit_changed:
        blocking.append({"type": "unit_change", "tokens": unit_changed,
                         "hint": "数值还在但单位/基准变了（wt%→% 不是同义改写）"})
    orig_nums = {t.split(" ")[0] for t in orig_f["number_units"]}
    added_nums = [t for t in set(pol_f["number_units"]) if t not in orig_f["number_units"]
                  and t.split(" ")[0] not in orig_nums and t not in converted_tokens]
    if added_nums:
        blocking.append({"type": "number_added", "tokens": added_nums,
                         "hint": "原文没有的数字不许出现（编造数据）"})
        fact_rows += [{"type": "number_unit", "token": t, "status": "added"} for t in added_nums]

    # 2) 引用：丢一条阻断，凭空多一条也阻断
    lost_cite = [c for c in set(orig_f["citations"])
                 if orig_f["citations"].count(c) > pol_f["citations"].count(c)]
    new_cite = [c for c in set(pol_f["citations"]) if c not in orig_f["citations"]]
    if lost_cite:
        blocking.append({"type": "citation_loss", "tokens": lost_cite})
    if new_cite:
        blocking.append({"type": "citation_added", "tokens": new_cite,
                         "hint": "原文没有的引用不许出现"})
    fact_rows += [{"type": "citation", "token": c,
                   "status": "removed" if c in lost_cite else "kept"} for c in set(orig_f["citations"])]
    fact_rows += [{"type": "citation", "token": c, "status": "added"} for c in new_cite]

    # 3) 限定词减少 / 强断言增加
    hedge_drop = _count_map_diff(orig_f["hedges"], pol_f["hedges"])
    if hedge_drop:
        blocking.append({"type": "hedge_loss", "tokens": hedge_drop,
                         "hint": "推测语气被删，主张强度被抬高"})
    fact_rows += [{"type": "hedge", "token": k,
                   "status": "removed" if k in hedge_drop else "kept"} for k in orig_f["hedges"]]
    strong_new = {k: v for k, v in pol_f["strong_claims"].items()
                  if v > orig_f["strong_claims"].get(k, 0)}
    strong_drop = _count_map_diff(orig_f.get("strong_claims", {}), pol_f.get("strong_claims", {}))
    # 强弱升级判方向：新增强断言、且没有任何强断言被换成别的强断言，就算抬高。
    # 只要求 hedge_drop/weak_drop 会漏掉两种最典型的升级：往中性句里塞 clearly
    # （没有弱词可删），以及 "We observed" → "It is well known"（弱词还在别处）。
    weak_drop = _count_map_diff(orig_f.get("weak_claims", {}), pol_f.get("weak_claims", {}))
    if strong_new and (hedge_drop or weak_drop or not strong_drop):
        blocking.append({"type": "strength_upgrade", "tokens": strong_new,
                         "hint": "新增强断言而原文没有对应的强断言被替换，主张强度被抬高"})

    # 4) 否定与比较级
    neg_drop = _count_map_diff(orig_f["negations"], pol_f["negations"])
    if neg_drop:
        blocking.append({"type": "negation_flip", "tokens": neg_drop})
    cmp_drop = _count_map_diff(orig_f["comparatives"], pol_f["comparatives"])
    if cmp_drop:
        blocking.append({"type": "comparative_loss", "tokens": cmp_drop})
    fact_rows += [{"type": "negation", "token": k,
                   "status": "removed" if k in neg_drop else "kept"} for k in orig_f["negations"]]
    fact_rows += [{"type": "comparative", "token": k,
                   "status": "removed" if k in cmp_drop else "kept"} for k in orig_f["comparatives"]]

    # 4b) 程度副词（significantly/slightly/markedly…）被删 = 强度被改
    int_drop = _count_map_diff(orig_f["intensity"], pol_f["intensity"])
    if int_drop:
        blocking.append({"type": "intensity_loss", "tokens": int_drop,
                         "hint": "significantly/slightly/markedly 等程度被改，结论强度变了"})
    int_new = {k: v for k, v in pol_f["intensity"].items()
               if v > orig_f["intensity"].get(k, 0)}
    if int_new:
        blocking.append({"type": "intensity_added", "tokens": int_new,
                         "hint": "原文没有的程度副词被加上，结论强度被抬高"})
    fact_rows += [{"type": "intensity", "token": k,
                   "status": "removed" if k in int_drop else "kept"} for k in orig_f["intensity"]]

    # 5) 逐句对齐：整句丢了 / 改写没记录
    orig_sents, pol_sents = sentences(original), sentences(polished)
    ledger = []
    if orig_sents and pol_sents:
        # 一对一匹配：每个源句最多占一个润色句，每个润色句也只能被一个源句认领。
        # 旧实现每句独立找最大相似度，两句近义源句会同时指向同一润色句，
        # 被删掉的那句因"有人顶替"而 similarity 虚高，F08 整句丢失被掩盖。
        cand = [(difflib.SequenceMatcher(None, o, p).ratio(), i, j)
                for i, o in enumerate(orig_sents) for j, p in enumerate(pol_sents)]
        cand.sort(reverse=True)
        pick, used_pol = {}, set()
        for r, i, j in cand:
            if i in pick or j in used_pol:
                continue
            pick[i] = (j, r)
            used_pol.add(j)
        for i, o in enumerate(orig_sents):
            if i in pick:
                best, best_r = pick[i]
            else:
                best, best_r = None, 0.0
            rec = {"i": i, "original": o, "polished_index": best,
                   "polished": pol_sents[best] if best is not None else None,
                   "similarity": round(best_r, 3),
                   "facts_before": sorted(facts.fact_tokens(o)),
                   "facts_after": sorted(facts.fact_tokens(pol_sents[best]) if best is not None else [])}
            ledger.append(rec)
        # 第二遍判定：此时全部匹配已知，才能区分"合并"与"整句丢失"
        for i, rec in enumerate(ledger):
            best_r = rec["similarity"]
            if best_r < 0.45:
                # 未被认领不必然是丢失：两句合法合并成一句时，合并句应同时覆盖两句实词。
                # 只按"一对一无主"就阻断会把合并误判成 F08。
                merged_into = None
                for k, rec2 in enumerate(ledger):
                    if k == i:
                        continue
                    p = rec2.get("polished") or ""
                    if not p:
                        continue
                    if _content_cover(rec["original"], p) >= 0.6 and _content_cover(rec2["original"], p) >= 0.6:
                        merged_into = k
                        break
                if merged_into is not None:
                    rec["merged_into"] = merged_into
                    advisory.append({"type": "sentence_merged", "index": i, "into": merged_into,
                                     "hint": "两句合并为一句，按 A02 提示而非整句丢失"})
                else:
                    blocking.append({"type": "sentence_dropped", "index": i, "original": rec["original"][:80],
                                     "hint": "源句没有被任何润色句一对一认领，也未被合并覆盖"})
            elif best_r < 0.85:
                advisory.append({"type": "sentence_rewritten", "index": i,
                                 "similarity": round(best_r, 3)})

        changed_revised = " ".join(_norm(str(c.get("revised", ""))) for c in changes)
        for j, p in enumerate(pol_sents):
            r = max(difflib.SequenceMatcher(None, p, o).ratio() for o in orig_sents)
            if r < 0.6 and _norm(p) not in changed_revised:
                blocking.append({"type": "unlogged_new_sentence", "index": j, "polished": p[:80]})

        # 5b) 引用挪到别的句子：原句里的引用必须还在对应的润色句里
        for i, rec in enumerate(ledger):
            orig_cites = facts.citations(rec["original"])
            if not orig_cites:
                continue
            pol_cites = facts.citations(rec["polished"] or "")
            moved = [c for c in orig_cites if c not in pol_cites]
            if moved and all(c in facts.citations(polished) for c in moved):
                blocking.append({"type": "citation_moved", "index": i, "citations": moved,
                                 "hint": "引用被挪到别的句子，归属变了"})

    # 6) 逐条改动：可回指 + 事实变化必须显式声明
    unmatched, undeclared, over_declared = [], [], []
    for k, c in enumerate(changes):
        o, r = _norm(str(c.get("original", ""))), _norm(str(c.get("revised", "")))
        if o and o not in _norm(original):
            unmatched.append({"index": k, "original": o[:60]})
        if r and r not in _norm(polished):
            advisory.append({"type": "revised_not_in_polished", "index": k, "revised": r[:60]})
        if o and r:
            dd = facts.fact_delta(o, r)
            if dd["changed"] and not c.get("fact_changed"):
                undeclared.append({"index": k, "lost": sorted(dd["lost"]), "gained": sorted(dd["gained"])})
            elif c.get("fact_changed") and not dd["changed"]:
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

    fact_total = len([x for x in fact_rows if x["status"] != "added"])
    fact_ok = len([x for x in fact_rows if x["status"] in ("kept", "normalized")])
    rates["fact_preservation_rate"] = _rate(fact_ok, fact_total)
    rates["facts_total"] = fact_total
    rates["facts_by_status"] = {s: sum(1 for x in fact_rows if x["status"] == s)
                                for s in ("kept", "normalized", "changed", "removed", "added")}
    for item in blocking + advisory:
        item.setdefault("code", CODES.get(item.get("type"), "A00"))

    return {"blocking": blocking, "advisory": advisory, "ledger": ledger, "facts": fact_rows,
            "rates": rates, "fact_unchanged": not any(
                x["status"] in ("changed", "removed", "added") for x in fact_rows),
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

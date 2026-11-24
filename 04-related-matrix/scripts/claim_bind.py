#!/usr/bin/env python3
"""核对引言草稿：论断是否挂引用、引用是否悬空、空白是否有 >=2 篇支撑、贡献是否有图表证据。

  python claim_bind.py --draft intro.md --works works.json --manuscript manuscript.json --out out

输出 bind.json / bind_report.md；硬项不达标退出码 1。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CITE = re.compile(r"\[([^\]]+)\]")
EVID = re.compile(r"(?:§|Sec\.?|Section)\s*(\d+(?:\.\d+)*)|(?:Fig|Figure|图)\s*\.?\s*(\d+)|(?:Table|表)\s*\.?\s*(\d+)|(?:Eq|Equation|式)\s*\.?\s*\(\s*(\d+)\s*\)")
CLAIM_WORDS = ["首次", "表明", "说明", "证明", "显示", "优于", "低于", "高于", "提升", "降低", "增加", "减少",
               "导致", "因此", "然而", "相比", "差异", "空白", "尚未", "未覆盖", "缺乏", "缺少", "没有", "均未", "未能"]
GAP_WORDS = ["空白", "尚未", "未覆盖", "缺乏", "缺少", "没有", "均未", "未能", "局限"]


def parse_cites(text: str, label2wid: dict):
    out, bad = [], []
    for m in CITE.finditer(text):
        inner = m.group(1)
        for part in re.split(r"[，,;；、]", inner):
            t = part.strip()
            if not t:
                continue
            if re.fullmatch(r"W\d+", t, re.I):
                out.append(t.upper())
            elif re.fullmatch(r"\d+", t):
                out.append(label2wid.get(f"[{t}]", f"[{t}]"))
            elif re.fullmatch(r"\d+\s*[–\-]\s*\d+", t):
                a, b = re.split(r"[–\-]", t)
                for i in range(int(a), int(b) + 1):
                    out.append(label2wid.get(f"[{i}]", f"[{i}]"))
            else:
                bad.append(t)
    return out, bad


def sentences(line: str):
    parts = re.split(r"(?<=[。！？；!?;])\s*", line.strip())
    return [p.strip() for p in parts if p.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", required=True)
    ap.add_argument("--works", required=True)
    ap.add_argument("--manuscript", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()

    works = json.loads(Path(a.works).read_text(encoding="utf-8"))["works"]
    ms = json.loads(Path(a.manuscript).read_text(encoding="utf-8"))
    draft = Path(a.draft).read_text(encoding="utf-8")
    by_wid = {w["wid"].upper(): w for w in works}
    label2wid = {(w.get("label") or "").strip(): w["wid"].upper() for w in works if w.get("label")}
    gaps = json.loads(Path(a.out, "matrix.json").read_text(encoding="utf-8")).get("gaps", []) \
        if Path(a.out, "matrix.json").exists() else []

    viol, cited_all = [], set()
    claims = 0
    claim_cited = 0
    gap_sents = 0
    gap_ok = 0
    contrib = 0
    contrib_ok = 0
    bullet_sections = []
    in_contrib = False

    for raw in draft.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            in_contrib = "贡献" in line
            continue
        if line.startswith(("-", "*")) and in_contrib:
            bullet_sections.append(line.lstrip("-* ").strip())
            continue

        wids, bad = parse_cites(line, label2wid)
        cited_all.update(wids)
        for t in bad:
            viol.append({"type": "dangling_citation", "detail": f"无法解析的引用标记 [{t}]", "text": line[:80]})
        for w in wids:
            if w not in by_wid and not w.startswith("["):
                viol.append({"type": "dangling_citation", "detail": f"引用了不存在的 {w}", "text": line[:80]})

        for s in sentences(line):
            is_claim = any(k in s for k in CLAIM_WORDS) and not s.startswith("本文")
            is_gap = any(k in s for k in GAP_WORDS) and ("覆盖" in s or "研究" in s or "工作" in s)
            if is_claim:
                claims += 1
                ss, _ = parse_cites(s, label2wid)
                if ss:
                    claim_cited += 1
                else:
                    viol.append({"type": "claim_uncited", "detail": "论断没有引用", "text": s[:90]})
            if is_gap:
                gap_sents += 1
                ss, _ = parse_cites(s, label2wid)
                support = set(ss) & cited_all
                need = 2
                ok = len(set(ss)) >= need
                if ok and gaps:
                    # 若句子对应某个已知空白，要求引用里至少 2 篇是该空白的支撑文献
                    for g in gaps:
                        if g["limitation"] in s or any(k in s for k in g["limitation"].split("、")):
                            ok = len(set(ss) & set(g["support_wids"])) >= 2
                            break
                if ok:
                    gap_ok += 1
                else:
                    viol.append({"type": "gap_unsupported", "detail": "空白未获 >=2 篇限制支撑", "text": s[:90]})

    # 贡献证据
    def has_ev(tok):
        m = EVID.finditer(tok)
        for x in m:
            if x.group(1) and x.group(1) in (ms.get("sections") or {}):
                return True
            if x.group(2) and str(x.group(2)) in (ms.get("figures") or {}):
                return True
            if x.group(3) and str(x.group(3)) in (ms.get("tables") or {}):
                return True
            if x.group(4) and str(x.group(4)) in (ms.get("equations") or {}):
                return True
        return False

    for b in bullet_sections:
        contrib += 1
        if not EVID.search(b):
            viol.append({"type": "contribution_no_evidence", "detail": "贡献条目未指向章节/图表", "text": b[:90]})
        elif has_ev(b):
            contrib_ok += 1
        else:
            viol.append({"type": "contribution_evidence_missing", "detail": "指向的章节/图表在材料中不存在", "text": b[:90]})

    # 关键文献与近作覆盖
    key_uncovered = [w["wid"] for w in works if w.get("key") and w["wid"].upper() not in cited_all]
    for w in key_uncovered:
        viol.append({"type": "key_work_uncited", "detail": f"关键文献 {w} 未被引用", "text": ""})
    recent = [w for w in works if int(w.get("year") or 0) >= 2022]
    recent_uncited = [w["wid"] for w in recent if w["wid"].upper() not in cited_all]
    for w in recent_uncited:
        viol.append({"type": "recent_work_uncited", "detail": f"近作 {w} 未被引用（warning）", "text": ""})

    # 罗列式写法：同段连续 3 句以文献编号/作者开头
    list_style = 0
    for para in [p for p in draft.split("\n\n") if p.strip()]:
        seq = 0
        for s in sentences(para):
            if re.match(r"^\[|\bW\d+\b", s.strip()):
                seq += 1
                if seq >= 3:
                    list_style += 1
                    break
            else:
                seq = 0

    rates = {
        "claim_citation_rate": round(claim_cited / max(1, claims), 4) if claims else 1.0,
        "gap_support_rate": round(gap_ok / max(1, gap_sents), 4) if gap_sents else 1.0,
        "key_work_coverage": round((len(works) - len(key_uncovered)) / max(1, len(works)), 4),
        "contribution_evidence_rate": round(contrib_ok / max(1, contrib), 4) if contrib else 1.0,
    }
    hard = [v for v in viol if v["type"] in ("claim_uncited", "dangling_citation", "gap_unsupported",
                                             "contribution_no_evidence", "contribution_evidence_missing", "key_work_uncited")]
    report = {"claims": claims, "claim_cited": claim_cited, "gap_sentences": gap_sents, "gap_supported": gap_ok,
              "contributions": contrib, "contributions_with_evidence": contrib_ok,
              "cited_wids": sorted(cited_all), "rates": rates, "pass": not hard,
              "violations": viol}

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bind.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 论断-引用绑定核对", "",
             f"- 论断 {claims} 条，挂引用 {claim_cited} 条（{rates['claim_citation_rate']:.2%}）",
             f"- 空白句 {gap_sents} 条，支撑充分 {gap_ok} 条（{rates['gap_support_rate']:.2%}）",
             f"- 贡献 {contrib} 条，有可解析证据 {contrib_ok} 条（{rates['contribution_evidence_rate']:.2%}）",
             f"- 关键文献覆盖 {rates['key_work_coverage']:.2%}", ""]
    if viol:
        lines += ["| 类型 | 说明 | 文本 |", "|---|---|---|"]
        lines += [f"| {v['type']} | {v['detail']} | {v['text']} |" for v in viol]
    (out / "bind_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "rates": rates, "violations": len(viol)}, ensure_ascii=False))
    if not a.no_fail and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

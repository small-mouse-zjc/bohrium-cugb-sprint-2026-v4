#!/usr/bin/env python3
"""译文质检：段落覆盖率 / 术语一致率 / 数字保真 / 引用标记保真 / 未确定标注。

  python qc.py --paras work/paras.jsonl --bi out/bilingual.json --glossary out/glossary.csv --out out
输出 out/qc.json 与 out/qc_report.md；不达标退出码 1。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

NUM = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)*")
UNITS = ["%", "‰", "°C", "MPa", "GPa", "kPa", "mM", "μM", "µm", "μm", "nm", "mm", "cm", "km",
         "kg", "mg", "mL", "Ma", "ka", "eV", "keV", "MeV", "wt%", "mol%", "ppm"]
CITE = [
    re.compile(r"\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\]"),
    re.compile(r"\([A-Z][A-Za-z\.\-']*(?:\s+(?:et al\.?|and|&)\s*[A-Za-z\.\-']*)*,?\s*(?:19|20)\d{2}[a-z]?\)"),
    re.compile(r"\b(?:Fig|Figure|Table|Eq|Equation|Section|Sec)\.?\s*\(?\d+(?:\.\d+)?"),
]
THRESH = {"coverage": 0.98, "term_consistency": 1.0, "number_preservation": 0.95,
          "citation_preservation": 1.0, "uncertain_flagging": 1.0}


def norm_mark(s: str) -> str:
    """统一全半角括号与空白，避免中文排版把英文标记判成丢失。"""
    table = str.maketrans({"（": "(", "）": ")", "，": ",", "：": ":", "　": " "})
    return re.sub(r"\s+", " ", s.translate(table))


def norm_num(s: str) -> str:
    s = s.replace("，", ",").replace("．", ".")
    return s.replace(",", "")


def load_glossary(p: Path):
    rows = []
    for r in csv.DictReader(p.open(encoding="utf-8")):
        if (r.get("translation") or "").strip():
            rows.append({"source": r["source"].strip(), "target": r["translation"].strip()})
    return rows


def find_term(text: str, term: str) -> bool:
    if re.search(r"[\u4e00-\u9fa5]", term):
        return term in text
    return re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text, re.I) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paras", required=True)
    ap.add_argument("--bi", required=True)
    ap.add_argument("--glossary", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()

    src = {p["id"]: p for p in (json.loads(l) for l in Path(a.paras).read_text(encoding="utf-8").splitlines() if l.strip())}
    bi_raw = json.loads(Path(a.bi).read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in bi_raw.get("paragraphs", [])}
    glos = load_glossary(Path(a.glossary))

    viol = []

    # 1 覆盖与编号一致性
    missing = [i for i in src if i not in rows]
    extra = [i for i in rows if i not in src]
    for i in missing:
        viol.append({"id": i, "type": "missing_para", "detail": "源段落未出现在译文"})
    for i in extra:
        viol.append({"id": i, "type": "unknown_id", "detail": "译文出现源中不存在的段落编号"})
    covered = 0
    for i, s in src.items():
        r = rows.get(i)
        if not r:
            continue
        tgt = (r.get("target") or "").strip()
        if not tgt:
            viol.append({"id": i, "type": "empty_target", "detail": "段落无译文"})
            continue
        if r.get("status") == "untranslatable":
            continue
        covered += 1

    # 2 术语一致（锁定术语只在出现于源段时要求）
    checks = hits = 0
    for i, s in src.items():
        r = rows.get(i) or {}
        if not r:
            continue
        for g in glos:
            if not find_term(s["text"], g["source"]):
                continue
            checks += 1
            if find_term((r.get("target") or ""), g["target"]):
                hits += 1
            else:
                viol.append({"id": i, "type": "term_drift", "detail": f"'{g['source']}' 未按术语表译为 '{g['target']}'"})

    # 3 数字与单位保真
    num_checks = num_hits = 0
    for i, s in src.items():
        r = rows.get(i) or {}
        if not r:
            continue
        tgt = norm_num((r.get("target") or ""))
        for m in NUM.finditer(s["text"]):
            tok = m.group(0)
            num_checks += 1
            if norm_num(tok) in tgt:
                num_hits += 1
            else:
                viol.append({"id": i, "type": "number_lost", "detail": f"数字 {tok} 未原样保留"})
        for u in UNITS:
            pat = r"\d\s?" + re.escape(u) + (r"(?![A-Za-z])" if re.match(r"[A-Za-z%‰°]", u) else "")
            if re.search(pat, s["text"]) and u not in tgt:
                viol.append({"id": i, "type": "unit_lost", "detail": f"单位 {u} 缺失"})

    # 4 引用/图表标记
    cite_checks = cite_hits = 0
    for i, s in src.items():
        r = rows.get(i) or {}
        if not r:
            continue
        tgt_raw = (r.get("target") or "")
        for pat in CITE:
            for m in pat.finditer(s["text"]):
                tok = norm_mark(m.group(0))
                cite_checks += 1
                if tok in norm_mark(tgt_raw):
                    cite_hits += 1
                else:
                    viol.append({"id": i, "type": "citation_lost", "detail": f"标记 '{tok}' 未保留"})

    # 5 未确定标注 + 重复译文
    flagged = need_flag = 0
    seen_tgt = {}
    for i, r in rows.items():
        if r.get("status") in ("uncertain", "untranslatable"):
            need_flag += 1
            if (r.get("risk") or []):
                flagged += 1
            else:
                viol.append({"id": i, "type": "unflagged_uncertain", "detail": "非 ok 段落缺少 risk 说明"})
        tgt = (r.get("target") or "").strip()
        if len(tgt) >= 20:
            if tgt in seen_tgt:
                viol.append({"id": i, "type": "dup_target", "detail": f"与 {seen_tgt[tgt]} 译文完全相同，疑似漏译占位"})
            seen_tgt[tgt] = i

    # 6 长度异常（中文/英文）
    for i, s in src.items():
        r = rows.get(i) or {}
        tgt = (r.get("target") or "").strip()
        words = max(1, len(s["text"].split()))
        ratio = len(tgt) / words
        if tgt and (ratio < 0.6 or ratio > 4.5):
            viol.append({"id": i, "type": "length_ratio", "detail": f"字符/词比 {ratio:.2f} 异常，需人工看"})

    rates = {
        "coverage": round(covered / max(1, len(src)), 4),
        "term_consistency": round(hits / max(1, checks), 4),
        "number_preservation": round(num_hits / max(1, num_checks), 4),
        "citation_preservation": round(cite_hits / max(1, cite_checks), 4),
        "uncertain_flagging": round(1.0 if need_flag == 0 else flagged / need_flag, 4),
    }
    failed = [k for k, v in THRESH.items() if rates[k] < v]
    report = {
        "case_id": bi_raw.get("case_id"),
        "counts": {"source_paras": len(src), "translated_paras": len(rows), "glossary_terms": len(glos),
                   "term_checks": checks, "number_checks": num_checks, "citation_checks": cite_checks},
        "rates": rates, "thresholds": THRESH, "failed": failed,
        "pass": not failed and not any(v["type"] in ("missing_para", "empty_target") for v in viol),
        "violations": viol[:400],
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "qc.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 译文质检", "", f"- 源段落 {len(src)} / 有译文 {len(rows)} / 术语 {len(glos)}",
             f"- 覆盖率 {rates['coverage']:.2%} | 术语一致率 {rates['term_consistency']:.2%} | "
             f"数字保真 {rates['number_preservation']:.2%} | 引用保真 {rates['citation_preservation']:.2%}",
             f"- 结论: {'通过' if report['pass'] else '未通过: ' + ','.join(failed) if failed else '未通过: 覆盖率类问题'}", ""]
    if viol:
        lines.append("| 段落 | 类型 | 说明 |")
        lines.append("|---|---|---|")
        for v in viol[:120]:
            lines.append(f"| {v['id']} | {v['type']} | {v['detail']} |")
    (out / "qc_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "failed": failed, "rates": rates,
                      "violations": len(viol), "out": str(out)}, ensure_ascii=False))
    if not a.no_fail and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

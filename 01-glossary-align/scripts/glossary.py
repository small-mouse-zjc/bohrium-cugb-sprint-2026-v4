#!/usr/bin/env python3
"""术语表：候选抽取 + 锁定校验。

  python glossary.py extract --paras work/paras.jsonl --out work/glossary_candidates.csv --top 60
  python glossary.py lock    --in work/glossary_filled.csv --out out/glossary.csv

extract 只给候选与出现位置，译名一栏留空，由人或 Agent 填写。
lock 强制三条规则：译名非空；同一源术语只能一个译名；同一译名不得对应两个源术语（同义合并须在 note 写明理由）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

STOP = set("""a an the of and or in on at to for from with by as is are was were be been being this that these those
it its their our we you they he she his her not no can could may might should would will shall do does did done
have has had such than then there here which who whom whose what when where why how more most less least very
using used use based between within during after before under over into out up down also both each other same
study studies paper article result results method methods figure table section data show shown shows found
however therefore thus although while because since about above below two one three first second""".split())

STOP_JA = set("""の は が を に で と も から まで より への による として について""".split())


def load_paras(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def tokens(text: str):
    out = []
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9\-]{1,}|[\u4e00-\u9fa5]{2,8}", text):
        t = m.group(0)
        out.append(t)
    return out


def extract(paras, top=60):
    freq = Counter()
    where = defaultdict(set)
    surface = defaultdict(Counter)
    for p in paras:
        toks = tokens(p["text"])
        low = [t.lower() for t in toks]
        for i, t in enumerate(low):
            if t in STOP or len(t) < 3:
                continue
            freq[t] += 1
            where[t].add(p["id"])
            surface[t][toks[i]] += 1
        for n in (2, 3):
            for i in range(len(low) - n + 1):
                gram = low[i:i + n]
                if any(g in STOP for g in gram):
                    continue
                if any(len(g) < 2 for g in gram):
                    continue
                key = " ".join(gram)
                freq[key] += 1
                where[key].add(p["id"])
                surface[key][" ".join(toks[i:i + n])] += 1
    rows = []
    for term, f in freq.items():
        if f < 2:
            continue
        spread = len(where[term])
        acronym = 1 if re.fullmatch(r"[A-Z][A-Z0-9\-]{1,6}s?", surface[term].most_common(1)[0][0]) else 0
        # 排序分：频次 + 跨段分布 + 多词术语加权 + 缩写加权
        score = f * 0.6 + spread * 1.2 + (term.count(" ") + 1) * 0.8 + acronym * 1.5
        rows.append({"source": surface[term].most_common(1)[0][0], "freq": f, "paragraphs": spread,
                     "acronym": acronym, "score": round(score, 2),
                     "paragraph_ids": ",".join(sorted(where[term])[:12])})
    rows.sort(key=lambda r: (-r["score"], r["source"].lower()))
    seen, out = set(), []
    for r in rows:
        key = r["source"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out[:top]


HEADER = ["source", "translation", "pos", "acronym", "freq", "paragraphs", "paragraph_ids", "note", "lock"]


def lock(inp: Path, out: Path):
    rows = list(csv.DictReader(inp.open(encoding="utf-8")))
    errors, warns, clean = [], [], []
    by_source, by_target = {}, {}
    for i, r in enumerate(rows, start=2):
        src = (r.get("source") or "").strip()
        tgt = (r.get("translation") or "").strip()
        if not src:
            continue
        if not tgt:
            errors.append(f"第{i}行 源术语 '{src}' 未填译名")
            continue
        src_k, tgt_k = src.lower(), tgt.lower()
        if src_k in by_source and by_source[src_k] != tgt_k:
            errors.append(f"第{i}行 '{src}' 出现第二个译名: {by_source[src_k]} vs {tgt_k}")
            continue
        if tgt_k in by_target and by_target[tgt_k] != src_k:
            note = (r.get("note") or "").strip()
            if "同义" not in note and "synonym" not in note.lower():
                errors.append(f"第{i}行 译名 '{tgt}' 同时对应 '{by_target[tgt_k]}' 与 '{src}'，需在 note 写明同义合并理由")
                continue
        by_source[src_k] = tgt_k
        by_target[tgt_k] = src_k
        if len(tgt) > 24 and re.search(r"[A-Za-z]", tgt) == None:
            warns.append(f"第{i}行 '{src}' 译名偏长({len(tgt)}字)，核对是否为解释而非译名")
        clean.append({"source": src, "translation": tgt, "pos": (r.get("pos") or "").strip(),
                      "acronym": (r.get("acronym") or "0").strip(), "freq": (r.get("freq") or "").strip(),
                      "paragraphs": (r.get("paragraphs") or "").strip(),
                      "paragraph_ids": (r.get("paragraph_ids") or "").strip(),
                      "note": (r.get("note") or "").strip(), "lock": "locked"})
    clean.sort(key=lambda r: (-int(float(r["freq"] or 0)), r["source"].lower()))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(clean)
    return {"status": "ok" if not errors else "error", "locked": len(clean),
            "errors": errors, "warnings": warns, "out": str(out)}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--paras", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--top", type=int, default=60)
    lk = sub.add_parser("lock")
    lk.add_argument("--in", dest="inp", required=True)
    lk.add_argument("--out", required=True)
    a = ap.parse_args()

    if a.cmd == "extract":
        rows = extract(load_paras(Path(a.paras)), a.top)
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADER)
            w.writeheader()
            for r in rows:
                w.writerow({**{k: "" for k in HEADER}, **r})
        print(json.dumps({"status": "ok", "candidates": len(rows), "out": str(out)}, ensure_ascii=False))
    else:
        res = lock(Path(a.inp), Path(a.out))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        raise SystemExit(0 if res["status"] == "ok" else 1)


if __name__ == "__main__":
    main()

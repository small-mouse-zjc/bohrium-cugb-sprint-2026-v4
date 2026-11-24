#!/usr/bin/env python3
"""01 平台入口：/input/case.json → 取段 → 术语锁定 → 质检 → /app/output/result.json

  python scripts/run.py                      # 默认读 /input，写 /app/output
  python scripts/run.py --input examples/demo --output out

输入约定（case.json 里字段名容错，取第一个命中的）：
  source / pdf / txt / manuscript   原文 PDF/TXT/MD 路径
  glossary / terms / glossary_path  术语表 CSV
  bilingual / draft / translation   已翻译稿（模型按 SKILL 产出；缺失时只做取段+术语表，status=partial）
输出：paras.jsonl / glossary.csv / bilingual.json / qc.json / qc_report.md / result.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
KEYS = ["coverage", "term_consistency", "number_preservation", "citation_preservation", "uncertain_flagging"]
HARD = {"missing_para", "empty_target", "term_drift", "number_lost", "citation_lost",
        "unit_lost", "dup_target", "unknown_id", "unflagged_uncertain"}


def pick(d, names):
    for n in names:
        v = d.get(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            for k in ("path", "file", "href"):
                if isinstance(v.get(k), str) and v[k].strip():
                    return v[k].strip()
    return None


def resolve(base: Path, p: str | None):
    if not p:
        return None
    q = Path(p)
    if q.is_absolute():
        return q
    cand = base / q
    if cand.exists():
        return cand
    return q


def call(args):
    r = subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    a = ap.parse_args()
    inp, out = Path(a.input), Path(a.output)
    out.mkdir(parents=True, exist_ok=True)

    case_p = inp / "case.json"
    if not case_p.exists():
        (out / "result.json").write_text(json.dumps({
            "case_id": "unknown", "status": "rejected", "metrics": {"pass": False},
            "notes": [f"缺少 {case_p}"], "artifacts": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2
    case = json.loads(case_p.read_text(encoding="utf-8"))
    case_id = case.get("case_id") or case.get("id") or "unknown"

    src = resolve(inp, pick(case, ["source", "pdf", "txt", "manuscript", "source_path", "input"]))
    glo = resolve(inp, pick(case, ["glossary", "terms", "glossary_path", "termbase"]))
    draft = resolve(inp, pick(case, ["bilingual", "draft", "translation", "bilingual_path"]))

    artifacts, notes = [], []
    if not src or not src.exists():
        (out / "result.json").write_text(json.dumps({
            "case_id": case_id, "status": "rejected",
            "metrics": {"pass": False, "step": "source"},
            "notes": [f"原文不存在: {src}"], "artifacts": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    # 1 取段
    paras = out / "paras.jsonl"
    r = call([ROOT / "scripts/pdf_to_paras.py", "--in", src, "--out", paras])
    if r.returncode != 0 or not paras.exists():
        (out / "result.json").write_text(json.dumps({
            "case_id": case_id, "status": "rejected",
            "metrics": {"pass": False, "step": "extract"},
            "notes": [r.stdout.strip()[-300:], r.stderr.strip()[-300:]], "artifacts": []},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return 2
    meta_p = Path(str(paras) + ".meta.json")
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    artifacts += ["paras.jsonl"]

    # 2 术语表（缺失则记 warning，继续跑）
    glos = out / "glossary.csv"
    if glo and glo.exists():
        call([ROOT / "scripts/glossary.py", "lock", "--in", glo, "--out", glos])
    else:
        glos.write_text("source,translation\n", encoding="utf-8")
        notes.append("未提供术语表：术语一致率按空表计，仅供参考")
    artifacts += ["glossary.csv"]

    # 3 译文：有草稿就对齐，没有就只交前半段
    bi_p = out / "bilingual.json"
    if draft and draft.exists():
        shutil.copyfile(draft, bi_p)
        artifacts += ["bilingual.json"]
        qo = out
        rq = call([ROOT / "scripts/qc.py", "--paras", paras, "--bi", bi_p, "--glossary", glos,
                   "--out", qo, "--no-fail"])
        qc = json.loads((out / "qc.json").read_text(encoding="utf-8"))
        artifacts += ["qc.json", "qc_report.md"]
        rates = qc.get("rates", {})
        hard = sum(v for k, v in qc.get("violation_counts", {}).items() if k in HARD)
        metrics = {k: rates.get(k) for k in KEYS}
        metrics.update({"paragraphs": len([1 for l in paras.read_text(encoding="utf-8").splitlines() if l.strip()]),
                        "headings": qc.get("counts", {}).get("headings", 0),
                        "hard_violations": hard, "pass": bool(qc.get("pass"))})
        failed = qc.get("failed", [])
        status = "success" if qc.get("pass") else "partial"
        if failed:
            notes.append("未达阈值: " + ",".join(failed))
        if hard:
            notes.append(f"硬违规 {hard} 条，见 qc.json")
    else:
        metrics = {"paragraphs": len([1 for l in paras.read_text(encoding="utf-8").splitlines() if l.strip()]),
                   "pass": False}
        status = "partial"
        notes.append("未提供译文草稿：已交付 paras.jsonl 与 glossary.csv，翻译需由模型按 SKILL 完成后重跑本脚本")

    if meta.get("status") == "no_text_layer":
        status = "cannot_determine"
        notes.append("原文疑似无文字层（扫描件），需 OCR 后重试")

    result = {"case_id": case_id, "status": status, "metrics": metrics, "notes": notes,
              "artifacts": artifacts, "input_mode": "platform" if str(inp) == "/input" else "local"}
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "metrics": metrics, "out": str(out)}, ensure_ascii=False))
    return 0 if status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

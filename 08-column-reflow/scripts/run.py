#!/usr/bin/env python3
"""08 平台入口：/input/case.json → 双栏重排 → 真值复算 → /app/output/result.json

  python scripts/run.py                      # 默认 /input → /app/output
  python scripts/run.py --input examples/demo --output out

case.json 字段（容错）：
  pdf / source / paper    待重排 PDF
  truth / expected        真值阅读顺序（可选；没有就只交重排结果，status=partial）
输出：paragraphs.jsonl / reflow.json / reflow.md / measure.json（有真值时）/ result.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def pick(d, names):
    for n in names:
        v = d.get(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def resolve(base: Path, p: str | None):
    if not p:
        return None
    q = Path(p)
    if q.is_absolute():
        return q
    cand = base / q
    return cand if cand.exists() else q


def call(args):
    return subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")


def write(out: Path, payload: dict, rc: int):
    (out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    a = ap.parse_args()
    inp, out = Path(a.input), Path(a.output)
    out.mkdir(parents=True, exist_ok=True)

    case_p = inp / "case.json"
    if not case_p.exists():
        return write(out, {"case_id": "unknown", "status": "rejected", "metrics": {"pass": False},
                           "notes": [f"缺少 {case_p}"], "artifacts": []}, 2)
    case = json.loads(case_p.read_text(encoding="utf-8"))
    case_id = case.get("case_id") or case.get("id") or "unknown"
    pdf = resolve(inp, pick(case, ["pdf", "source", "paper", "pdf_path"]))
    truth = resolve(inp, pick(case, ["truth", "expected", "truth_path"]))

    if not pdf or not pdf.exists():
        return write(out, {"case_id": case_id, "status": "rejected", "metrics": {"pass": False},
                           "notes": [f"缺少 PDF: {pdf}"], "artifacts": []}, 2)

    r = call([ROOT / "scripts/reflow.py", "--pdf", pdf, "--out", out, "--audit"])
    audit_failed = r.returncode == 3  # 重排已产出，但 audit 门未过：照样交付，不许判 success
    if r.returncode not in (0, 3) or not (out / "reflow.json").exists():
        return write(out, {"case_id": case_id, "status": "rejected", "metrics": {"pass": False, "step": "reflow"},
                           "notes": [r.stdout[-300:], r.stderr[-300:]], "artifacts": []}, 2)
    info = json.loads((out / "reflow.json").read_text(encoding="utf-8"))
    artifacts = ["paragraphs.jsonl", "reflow.json", "reflow.md"]
    notes = []
    if audit_failed:
        notes.append("audit 门未过：" + "；".join((info.get("audit") or {}).get("fail", [])) + "（重排已交付，需人工复核）")

    metrics = {"pages": info.get("pages"), "paragraphs": info.get("paragraphs"),
               "layout": info.get("layout"), "dropped_headers_footers": len(info.get("dropped_headers_footers", [])),
               "suspicious": len(info.get("suspicious", [])),
               "coverage": info.get("coverage"),
               "audit_fail": len((info.get("audit") or {}).get("fail", []))}
    if truth and truth.exists():
        rm = call([ROOT / "eval/measure.py", "--out", out, "--truth", truth])
        mp = out / "measure.json"
        m = None
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
        elif rm.returncode == 0 and rm.stdout.strip().startswith("{"):
            try:
                m = json.loads(rm.stdout.strip())
                mp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
            except json.JSONDecodeError:
                m = None
        if m is not None:
            metrics.update({"exact_position_rate": m.get("exact_position_rate"),
                            "inversions": m.get("inversions"), "adjacent_errors": m.get("adjacent_errors"),
                            "order_match": m.get("order_match"), "missing": len(m.get("missing", []))})
            artifacts += ["measure.json"]
            ok = (bool(m.get("order_match")) and m.get("inversions") == 0 and not m.get("missing")
                  and len(info.get("suspicious", [])) == 0
                  and (info.get("coverage") is None or info["coverage"] >= 0.95))
            status = "success" if ok else "partial"
            if not ok:
                notes.append(f"与真值不一致：逆序 {m.get('inversions')}、相邻错位 {m.get('adjacent_errors')}、缺失 {len(m.get('missing', []))}；"
                             f"串栏疑似 {len(info.get('suspicious', []))}、覆盖率 {info.get('coverage')}")
        else:
            metrics["order_match"] = None
            status = "partial"
            notes.append("measure.py 未产出 measure.json")
    else:
        metrics["order_match"] = None
        status = "partial"
        notes.append("未提供真值 truth.json：重排已交付，但顺序无法机器校验（不宣称通过）")
        if info.get("suspicious"):
            notes.append(f"另有串栏疑似 {len(info['suspicious'])} 处，必须人工复核")

    if info.get("paragraphs", 0) == 0:
        status = "cannot_determine"
        notes.append("PDF 未抽出任何文本块，疑似扫描件，需 OCR")

    metrics["pass"] = status == "success"
    payload = {"case_id": case_id, "status": status, "metrics": metrics, "notes": notes,
               "artifacts": artifacts, "input_mode": "platform" if str(inp) == "/input" else "local"}
    return write(out, payload, 0 if status == "success" else 1)


if __name__ == "__main__":
    sys.exit(main())

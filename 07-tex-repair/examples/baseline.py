#!/usr/bin/env python3
"""基线对照：模拟"不带 Skill 的裸 Agent"——单轮 pdflatex、不跑 bibtex、不做静态体检。

  python examples/baseline.py --project examples/demo/fixed --out out_base

产物只有 build_manifest.json 与 logdiag.json（故意没有 texfit.json），
供 eval/metrics.py --base_dir 对比，得到的是可复现的差值，不是编的。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from logdiag import parse_log  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--main", default="main.tex")
    a = ap.parse_args()
    proj, out = Path(a.project).resolve(), Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    eng = shutil.which("pdflatex")
    m = {"project": proj.name, "engine": eng or "none", "rounds": 0, "bibtex_runs": 0,
         "status": "static_only", "baseline": "single-pass pdflatex, no bibtex, no checks",
         "converged": False, "errors": None, "pages": None, "pdf": None}
    if not eng:
        m["note"] = "无 pdflatex，基线也未编译"
        (out / "build_manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(m, ensure_ascii=False))
        return
    cmd = [eng, "-interaction=nonstopmode", "-file-line-error", "-output-directory=" + str(out), a.main]
    r = subprocess.run(cmd, cwd=str(proj), capture_output=True, text=True, encoding="utf-8", errors="replace")
    m["rounds"] = 1
    log = out / (Path(a.main).stem + ".log")
    text = (r.stdout or "") + (r.stderr or "") + ("\n" + log.read_text(encoding="utf-8", errors="replace") if log.exists() else "")
    (out / "run.log").write_text(text[-200000:], encoding="utf-8")
    d = parse_log(text)
    (out / "logdiag.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    pdf = out / (Path(a.main).stem + ".pdf")
    if pdf.exists():
        m["pdf"] = {"path": pdf.name, "bytes": pdf.stat().st_size}
        pi = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
        mm = re.search(r"Pages:\s+(\d+)", pi.stdout or "")
        if mm:
            m["pages"] = int(mm.group(1))
    m["errors"] = len(d["errors"])
    m["converged"] = (not d["errors"]) and (not d["rerun_required"]) and pdf.exists()
    m["status"] = "success" if (pdf.exists() and not d["errors"] and not d["rerun_required"]) else (
        "partial" if pdf.exists() else "failed")
    (out / "build_manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("status", "rounds", "bibtex_runs", "errors", "converged", "pages")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

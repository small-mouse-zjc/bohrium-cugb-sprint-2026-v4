#!/usr/bin/env python3
"""编译到收敛，并写构建清单；没有 TeX 时明确报 static_only。

  python build.py --project paper --out out --rounds 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logdiag import parse_log  # noqa: E402


def sha(p: Path):
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()[:16]


def find_engine():
    for e in ("latexmk", "pdflatex", "xelatex"):
        w = shutil.which(e)
        if w:
            return e, w
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--main", default="main.tex")
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()

    proj = Path(a.project).resolve()
    main_tex = proj / a.main
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not main_tex.exists():
        (out / "build_manifest.json").write_text(json.dumps(
            {"status": "rejected", "reason": f"缺少 {a.main}"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "rejected"}))
        raise SystemExit(2)

    engine, path = find_engine()
    inputs = {str(p.relative_to(proj)): sha(p) for p in list(proj.rglob("*.tex")) + list(proj.rglob("*.bib"))
              if "build" not in p.parts}
    manifest = {"project": proj.name, "main": a.main, "inputs_sha256": inputs,
                "engine": engine or "none", "command": [], "rounds": 0, "status": "static_only",
                "note": "", "pdf": None, "log": None}

    if not engine:
        manifest["note"] = "本机无 latexmk/pdflatex/xelatex，未执行真实编译；只做静态检查，不得声称编译通过"
        (out / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "static_only", "engine": "none"}, ensure_ascii=False))
        return

    if engine == "latexmk":
        cmd = [path, "-pdf", "-interaction=nonstopmode", "-halt-on-error=false", "-outdir=" + str(out), a.main]
    else:
        cmd = [path, "-interaction=nonstopmode", "-file-line-error", "-output-directory=" + str(out), a.main]
    manifest["command"] = [c.replace(str(out), "<OUT>") for c in cmd]

    log_path = out / (Path(a.main).stem + ".log")
    rounds, log_text = 0, ""
    for i in range(1, a.rounds + 1):
        r = subprocess.run(cmd, cwd=str(proj), capture_output=True, text=True, encoding="utf-8", errors="replace")
        rounds += 1
        log_text = r.stdout + "\n" + r.stderr
        if log_path.exists():
            log_text += "\n" + log_path.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"Rerun to get|Label\(s\) may have changed|undefined references", log_text):
            break
        if engine != "latexmk" and not shutil.which("bibtex"):
            break

    diag = parse_log(log_text)
    (out / "logdiag.json").write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "run.log").write_text(log_text[-200000:], encoding="utf-8")
    manifest["rounds"] = rounds
    manifest["log"] = "run.log"
    pdf = out / (Path(a.main).stem + ".pdf")
    if pdf.exists():
        manifest["pdf"] = {"path": pdf.name, "bytes": pdf.stat().st_size}
    manifest["status"] = "compiled" if (not diag["errors"] and pdf.exists()) else "failed"
    manifest["errors"] = len(diag["errors"])
    try:
        ver = subprocess.run([path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        manifest["engine_version"] = (ver.stdout or "").splitlines()[0][:120]
    except Exception:
        pass
    if pdf.exists():
        try:
            pi = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
            m = re.search(r"Pages:\s+(\d+)", pi.stdout or "")
            if m:
                manifest["pdf"]["pages"] = int(m.group(1))
        except Exception:
            pass
    (out / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "engine": engine, "rounds": rounds,
                      "errors": len(diag["errors"]), "warnings": diag["warning_count"],
                      "converged": diag["converged"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

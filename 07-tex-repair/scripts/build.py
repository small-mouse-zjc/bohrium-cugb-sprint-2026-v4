#!/usr/bin/env python3
"""编译到收敛，并写构建清单；没有 TeX 时明确报 static_only。

  python build.py --project paper --out out --rounds 3
  python build.py --project paper --out out --engine latexmk   # 显式指定才走 latexmk

status 语义（下游只看 status 也不会误判）：
  success      errors=0 且 rerun_required=false 且 PDF 存在
  partial      PDF 存在，但仍有错误或需要再编（如引文未解析）
  failed       没有产出 PDF
  static_only  本机无 TeX，只做静态检查（绝不等于通过）
  rejected     缺 main.tex
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


def sha_full(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


DEFAULT_EPOCH = 1577836800   # 2020-01-01T00:00:00Z


def repro_env(epoch: int) -> dict:
    """让 pdfTeX 输出可字节复现：固定 CreationDate/ModDate 与 \\today 的来源时间。

    pdfTeX 自 2016 起读 SOURCE_DATE_EPOCH，配合 FORCE_SOURCE_DATE=1 才会
    同时改写 \\today 与 PDF 里的时间戳；否则同一输入两次编译的 PDF 字节不同。
    """
    return {"SOURCE_DATE_EPOCH": str(epoch), "FORCE_SOURCE_DATE": "1"}


def pick_epoch(proj: Path, cli_value) -> int:
    if isinstance(cli_value, int) and cli_value > 0:
        return cli_value
    for name in ("template.yaml", "case.json", "task.yaml"):
        p = proj / name
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?:source_date_epoch|epoch)\s*:\s*(\d+)", txt)
        if m:
            return int(m.group(1))
    return DEFAULT_EPOCH


def find_engine(prefer: str | None = None):
    """默认优先 pdflatex/xelatex；latexmk 只在显式 --engine latexmk 时使用。

    latexmk 对 pdflatex 专用旗标（-halt-on-error=false 等）会直接报
    "Bad options specified"，所以不能排在默认第一位。
    """
    order = [prefer] if prefer else []
    order += [e for e in ("pdflatex", "xelatex", "lualatex", "latexmk") if e != prefer]
    for e in order:
        w = shutil.which(e)
        if w:
            return e, w
    return None, None


def run(cmd, cwd, env=None):
    import os
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=e)


def needs_bib(proj: Path, main_tex: Path) -> bool:
    txt = main_tex.read_text(encoding="utf-8", errors="replace")
    if re.search(r"\\(bibliography|addbibresource)\s*\{", txt):
        return True
    return any(True for _ in proj.rglob("*.bib"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--main", default="main.tex")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--engine", default=None, choices=["pdflatex", "xelatex", "lualatex", "latexmk"])
    ap.add_argument("--time-budget", type=int, default=900, help="总编译预算秒数，超过就停手并如实降级")
    ap.add_argument("--no-bibtex", action="store_true",
                    help="跳过 bibtex/biber（用于证明'引文未解析时确实降级为 partial'，不用于正常交付）")
    ap.add_argument("--epoch", type=int, default=None,
                    help="SOURCE_DATE_EPOCH；缺省从 template.yaml 的 source_date_epoch 取，再缺省 2020-01-01")
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

    engine, path = find_engine(a.engine)
    epoch = pick_epoch(proj, a.epoch)
    renv = repro_env(epoch)
    inputs = {str(p.relative_to(proj)): sha(p) for p in list(proj.rglob("*.tex")) + list(proj.rglob("*.bib"))
              if "build" not in p.parts}
    manifest = {"project": proj.name, "main": a.main, "inputs_sha256": inputs,
                "engine": engine or "none", "command": [], "rounds": 0, "bibtex_runs": 0,
                "status": "static_only", "note": "", "pdf": None, "log": None,
                "converged": False, "rerun_required": None, "errors": None,
                "compile_env": {"SOURCE_DATE_EPOCH": epoch, "FORCE_SOURCE_DATE": "1",
                                "reproducible": True},
                "bibtex_enabled": not a.no_bibtex}

    if not engine:
        manifest["note"] = "本机无 pdflatex/xelatex/latexmk，未执行真实编译；只做静态检查，不得声称编译通过"
        (out / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "static_only", "engine": "none"}, ensure_ascii=False))
        return

    if engine == "latexmk":
        # latexmk 自己会跑 bibtex/biber，也会自己判断重编轮次；不要给它传 pdflatex 专用旗标。
        cmd = [path, "-pdf", "-f", "-outdir=" + str(out), a.main]
    else:
        cmd = [path, "-interaction=nonstopmode", "-file-line-error",
               "-output-directory=" + str(out), a.main]
    manifest["command"] = [c.replace(str(out), "<OUT>") for c in cmd]

    log_path = out / (Path(a.main).stem + ".log")
    aux_path = out / (Path(a.main).stem + ".aux")
    import time
    t0 = time.monotonic()
    rounds, bib_runs, log_text = 0, 0, ""
    bib_failed = False
    budget_hit = False
    for i in range(1, a.rounds + 1):
        if time.monotonic() - t0 > a.time_budget:
            budget_hit = True
            break
        r = run(cmd, proj, renv)
        rounds += 1
        log_text = r.stdout + "\n" + r.stderr
        if log_path.exists():
            log_text += "\n" + log_path.read_text(encoding="utf-8", errors="replace")
        # 第一轮之后插入 bibtex/biber，解决 "Citation ... undefined"
        if (not a.no_bibtex) and engine != "latexmk" and bib_runs == 0 and rounds == 1 and needs_bib(proj, main_tex):
            bibtex = shutil.which("bibtex")
            biber = shutil.which("biber")
            if bibtex and aux_path.exists():
                br = run([bibtex, aux_path.stem], out, dict(renv, BIBINPUTS=f"{out}:{proj}:"))
                bib_runs += 1
                bib_failed = br.returncode != 0
                log_text += "\n" + br.stdout + "\n" + br.stderr
                continue  # 跑完 bib 必须再编
            elif biber:
                br = run([biber, aux_path.stem], out, dict(renv, BIBINPUTS=f"{out}:{proj}"))
                bib_runs += 1
                bib_failed = br.returncode != 0
                log_text += "\n" + br.stdout + "\n" + br.stderr
                continue
        if not re.search(r"Rerun to get|Label\(s\) may have changed|There were undefined references"
                         r"|Citation .* undefined", log_text):
            break

    diag = parse_log(log_text)
    (out / "logdiag.json").write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "run.log").write_text(log_text[-200000:], encoding="utf-8")
    manifest["rounds"] = rounds
    manifest["bibtex_runs"] = bib_runs
    manifest["elapsed_s"] = round(time.monotonic() - t0, 1)
    manifest["time_budget_s"] = a.time_budget
    manifest["budget_hit"] = budget_hit
    manifest["bibtex_failed"] = bib_failed
    manifest["log"] = "run.log"
    pdf = out / (Path(a.main).stem + ".pdf")
    pages = None
    if pdf.exists():
        manifest["pdf"] = {"path": pdf.name, "bytes": pdf.stat().st_size, "sha256": sha_full(pdf)}
        try:
            pi = run(["pdfinfo", str(pdf)], out)
            m = re.search(r"Pages:\s+(\d+)", pi.stdout or "")
            if m:
                pages = int(m.group(1))
                manifest["pdf"]["pages"] = pages
        except Exception:
            pass
        bbl = out / (Path(a.main).stem + ".bbl")
        if bbl.exists():
            manifest["pdf"]["bbl_sha256"] = sha_full(bbl)
            manifest["bbl"] = {"path": bbl.name, "bytes": bbl.stat().st_size}
    errors = len(diag["errors"])
    converged = errors == 0 and not diag["rerun_required"] and pdf.exists()
    manifest["errors"] = errors
    manifest["converged"] = converged
    manifest["rerun_required"] = bool(diag["rerun_required"])
    manifest["pages"] = pages
    manifest["undefined_cites"] = [w["message"][:80] for w in diag["warnings"] if w["code"] == "E06"][:10]
    if pdf.exists():
        manifest["status"] = "success" if converged else "partial"
    else:
        manifest["status"] = "failed"
    try:
        ver = run([path, "--version"], out)
        manifest["engine_version"] = (ver.stdout or "").splitlines()[0][:120]
    except Exception:
        pass
    (out / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "engine": engine, "rounds": rounds, "bibtex_runs": bib_runs,
                      "errors": errors, "warnings": diag["warning_count"],
                      "converged": converged, "pages": pages}, ensure_ascii=False))
    raise SystemExit(0 if manifest["status"] in ("success",) else 1)


if __name__ == "__main__":
    main()

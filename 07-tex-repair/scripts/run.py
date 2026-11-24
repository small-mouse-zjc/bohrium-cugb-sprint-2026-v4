#!/usr/bin/env python3
"""Harness 入口：读平台输入 → texfit → build → logdiag → 写 result.json。

平台契约（题面 /app/input/case.json、/app/output/result.json）：
  python scripts/run.py                       # 默认 /input → /app/output
  python scripts/run.py --input . --output out --project examples/demo/fixed --template examples/demo/template.yaml

case.json 容错：依次尝试 project / project_dir / paper / source / workdir 等键；
找不到就退化为「输入目录下第一个含 main.tex 的目录」。template 同理。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PROJ_KEYS = ("project", "project_dir", "projectDir", "paper", "source", "source_dir", "workdir", "submission")
TPL_KEYS = ("template", "template_path", "templatePath", "template_yaml", "journal_template")
MAIN_KEYS = ("main", "main_tex", "main_file", "entry")
CASE_KEYS = ("case_id", "caseId", "id", "name")


def dig(obj, keys, depth=0):
    """在嵌套 dict/list 里找第一个命中的键（限深度，避免误抓）。"""
    if depth > 4:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and isinstance(obj[k], str):
                return obj[k]
        for v in obj.values():
            got = dig(v, keys, depth + 1)
            if got:
                return got
    elif isinstance(obj, list):
        for v in obj[:5]:
            got = dig(v, keys, depth + 1)
            if got:
                return got
    return None


def find_project(root: Path):
    for p in sorted(root.rglob("main.tex")):
        if "build" not in p.parts:
            return p.parent
    return None


def find_template(root: Path, project: Path | None):
    cands = list(root.rglob("template.yaml")) + list(root.rglob("template.yml")) + list(root.rglob("template.json"))
    if project:
        cands += list(project.rglob("template.yaml"))
    return cands[0] if cands else None


def read_epoch(template: Path | None):
    """从模板文件里取 source_date_epoch（yaml/json 都用同一正则，不引第三方依赖）。"""
    if not template or not template.exists():
        return None
    try:
        txt = template.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    m = re.search(r"(?:source_date_epoch|source-date-epoch|epoch)\s*[:=]\s*\"?(\d+)", txt)
    return int(m.group(1)) if m else None


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    ap.add_argument("--project")
    ap.add_argument("--template")
    ap.add_argument("--main", default="main.tex")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--time-budget", type=int, default=900)
    a = ap.parse_args()

    inp = Path(a.input)
    outp = Path(a.output)
    outp.mkdir(parents=True, exist_ok=True)
    case = {}
    case_id = "unknown"
    for name in ("case.json", "task.json", "input.json"):
        p = inp / name
        if p.exists():
            try:
                case = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                case_id = str(dig(case, CASE_KEYS) or case.get("case_id") or p.stem)
                break
            except Exception as e:
                case = {"_parse_error": str(e)}

    project = Path(a.project) if a.project else None
    if project is None:
        rel = dig(case, PROJ_KEYS)
        if rel and (inp / rel).exists():
            project = inp / rel
        if project is None:
            project = find_project(inp)
    template = Path(a.template) if a.template else None
    if template is None:
        rel = dig(case, TPL_KEYS)
        if rel and (inp / rel).exists():
            template = inp / rel
        if template is None:
            template = find_template(inp, project)

    result = {"case_id": case_id, "status": "cannot_determine", "metrics": {},
              "artifacts": [], "notes": []}

    if project is None or not (project / a.main).exists():
        result["status"] = "rejected"
        result["notes"].append(f"找不到含 {a.main} 的工程目录（input={inp}）")
        (outp / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(2)

    metrics = {"project": str(project), "template": str(template) if template else None}
    # 只有 .cls/.sty 没有 template.yaml 时：仍做通用静态检查（T03–T07），
    # 但模板类别/必填项/章节无法自动判定，必须显式标 generic，不许静默跳过。
    cls_files = list(project.rglob("*.cls")) + list(project.rglob("*.sty"))
    if template is None and cls_files:
        generic = outp / "_generic_template.json"
        generic.write_text("{}", encoding="utf-8")
        template = generic
        metrics["template_mode"] = "generic_cls_only"
        metrics["template_files"] = [p.name for p in cls_files][:5]
        result["notes"].append("输入只有 .cls/.sty 模板，已按通用规则（宏包/引用/列数/图路径）检查；"
                               "documentclass、必填项、章节要求需人工确认，故结论最高只能给 partial")
    elif template is not None:
        metrics["template_mode"] = "template_yaml"
    result["metrics"] = metrics

    # 1) 静态合规
    if template:
        rc, text = run([sys.executable, str(HERE / "texfit.py"), "--project", str(project),
                        "--template", str(template), "--out", str(outp), "--no-fail"])
        metrics["texfit_rc"] = rc
        try:
            fit = json.loads((outp / "texfit.json").read_text(encoding="utf-8"))
            metrics["violations"] = len(fit.get("violations", []))
            metrics["violation_counts"] = fit.get("counts", {})
        except Exception:
            metrics["violations"] = None
            result["notes"].append("texfit.json 未生成：" + text[-200:])
    else:
        metrics["violations"] = None
        result["notes"].append("输入里没有 template.yaml/json，跳过 T01–T08 静态检查")

    # 2) 真实编译（无 TeX 时由 build.py 自己降级为 static_only）
    #    epoch 必须从"输入目录的模板"里取：平台布局把 template.yaml 放在 /input/、
    #    工程在 /input/project/，build.py 只在工程目录里找会静默退回默认值，
    #    用户按 SKILL 配的 source_date_epoch 就会失效（换机器 sha256 对不上）。
    epoch_args = []
    ep = read_epoch(template) if template else None
    if ep:
        epoch_args = ["--epoch", str(ep)]
        metrics["source_date_epoch"] = ep
    rc, text = run([sys.executable, str(HERE / "build.py"), "--project", str(project),
                    "--out", str(outp), "--main", a.main, "--rounds", str(a.rounds),
                    "--time-budget", str(a.time_budget)] + epoch_args)
    metrics["build_rc"] = rc
    try:
        bm = json.loads((outp / "build_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        bm = {}
        result["notes"].append("build_manifest.json 未生成：" + text[-200:])
    metrics["build_status"] = bm.get("status")
    metrics["errors"] = bm.get("errors")
    metrics["converged"] = bm.get("converged")
    metrics["rerun_required"] = bm.get("rerun_required")
    metrics["bibtex_runs"] = bm.get("bibtex_runs")
    metrics["pages"] = bm.get("pages")
    metrics["elapsed_s"] = bm.get("elapsed_s")
    metrics["time_budget_s"] = bm.get("time_budget_s", a.time_budget)
    metrics["budget_hit"] = bm.get("budget_hit", False)
    metrics["pdf"] = (bm.get("pdf") or {}).get("path")

    # 3) 日志诊断
    try:
        lg = json.loads((outp / "logdiag.json").read_text(encoding="utf-8"))
        metrics["error_count"] = len(lg.get("errors", []))
        metrics["warning_count"] = lg.get("warning_count")
        metrics["error_codes"] = lg.get("counts", {})
        metrics["undefined_cites"] = [w.get("key") for w in lg.get("warnings", []) if w.get("code") == "E06"][:10]
    except Exception:
        pass

    # 4) 判定
    viol = metrics.get("violations")
    bstat = metrics.get("build_status")
    generic_tpl = metrics.get("template_mode") == "generic_cls_only"
    if bstat == "success" and viol == 0 and not generic_tpl:
        result["status"] = "success"
    elif bstat in ("success", "partial"):
        result["status"] = "partial"
    elif bstat == "static_only":
        result["status"] = "cannot_determine"
        result["notes"].append("本机无 TeX，只完成静态检查；没有编译证据，不能判 success")
    else:
        result["status"] = "rejected" if bstat == "rejected" else "cannot_determine"

    # 预算闸门命中：说明没编到收敛就被按下暂停，绝不能仍报 success
    if metrics.get("budget_hit") and result["status"] == "success":
        result["status"] = "partial"
        result["notes"].append(f"编译预算 {metrics.get('time_budget_s')}s 已用尽（{metrics.get('elapsed_s')}s），"
                               "未确认收敛完毕，降级为 partial")

    result["artifacts"] = [p for p in ("texfit.json", "texfit.md", "build_manifest.json",
                                       "logdiag.json", "run.log")
                           if (outp / p).exists()]
    result["decided_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    (outp / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""LaTeX 工程静态合规检查（T01–T08），不依赖 TeX。

  python texfit.py --project paper --template template.yaml --out out
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MACRO_PKG = {
    r"\toprule": "booktabs", r"\midrule": "booktabs", r"\bottomrule": "booktabs",
    r"\includegraphics": "graphicx", r"\textcolor": "xcolor", r"\colorbox": "xcolor",
    r"\multirow": "multirow", r"\url": "url", r"\SI": "siunitx", r"\bm": "bm",
}


def tex_files(project: Path):
    return sorted([p for p in project.rglob("*.tex") if "build" not in p.parts])


def lines_of(p: Path):
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def strip_comments(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\":
            out.append(s[i:i + 2])
            i += 2
            continue
        if s[i] == "%":
            break
        out.append(s[i])
        i += 1
    return "".join(out)


def check(project: Path, template: dict):
    files = tex_files(project)
    if not files:
        return {"pass": False, "violations": [{"rule": "T00", "file": "", "line": 0,
                                               "detail": "工程里没有 .tex 文件"}], "counts": {}}
    v = []
    main = next((f for f in files if "\\documentclass" in f.read_text(encoding="utf-8", errors="replace")), files[0])
    main_txt = main.read_text(encoding="utf-8", errors="replace")
    main_lines = lines_of(main)

    # T01 documentclass
    m = re.search(r"\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}", main_txt)
    if not m:
        v.append({"rule": "T01", "file": main.name, "line": 0, "detail": "缺少 \\documentclass"})
    else:
        opts, cls = m.group(1) or "", m.group(2).strip()
        need_cls = template.get("documentclass")
        if need_cls and cls != need_cls:
            v.append({"rule": "T01", "file": main.name, "line": 1, "detail": f"模板要求 {need_cls}，实为 {cls}"})
        for o in template.get("class_options", []):
            if o not in [x.strip() for x in opts.split(",")]:
                v.append({"rule": "T01", "file": main.name, "line": 1, "detail": f"缺少类选项 {o}"})

    # T02 必填项
    for cmd in template.get("required_commands", []):
        if not re.search(re.escape(cmd), main_txt):
            v.append({"rule": "T02", "file": main.name, "line": 0, "detail": f"缺少必填命令 {cmd}"})
    if template.get("bibliography_style"):
        if f"\\bibliographystyle{{{template['bibliography_style']}}}" not in main_txt:
            v.append({"rule": "T02", "file": main.name, "line": 0,
                      "detail": f"缺少参考文献样式 {template['bibliography_style']}"})

    # T03 宏包
    pkgs = set()
    for f in files:
        for mm in re.finditer(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", f.read_text(encoding="utf-8", errors="replace")):
            pkgs.update(x.strip() for x in mm.group(1).split(","))
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="replace")
        for macro, pkg in MACRO_PKG.items():
            if macro in txt and pkg not in pkgs:
                ln = next((i for i, l in enumerate(txt.splitlines(), 1) if macro in l), 0)
                v.append({"rule": "T03", "file": f.name, "line": ln, "detail": f"用了 {macro}，但未加载 {pkg}"})

    # T04 引用/标签
    labels, refs = set(), []
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="replace")
        for i, l in enumerate(txt.splitlines(), 1):
            for mm in re.finditer(r"\\label\{([^}]*)\}", l):
                labels.add(mm.group(1))
            for mm in re.finditer(r"\\(?:ref|eqref|autoref|pageref)\{([^}]*)\}", l):
                refs.append((mm.group(1), f.name, i))
    for key, fn, ln in refs:
        if key not in labels:
            v.append({"rule": "T04", "file": fn, "line": ln, "detail": f"\\ref{{{key}}} 没有对应 \\label"})

    # T05 引文键
    bibs = list(project.rglob("*.bib"))
    bibkeys = set()
    for b in bibs:
        bibkeys.update(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", b.read_text(encoding="utf-8", errors="replace")))
    for f in files:
        for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for mm in re.finditer(r"\\cite[a-z]*\{([^}]*)\}", l):
                for k in mm.group(1).split(","):
                    k = k.strip()
                    if k and k not in bibkeys:
                        v.append({"rule": "T05", "file": f.name, "line": i, "detail": f"\\cite{{{k}}} 不在 .bib 中"})

    # T06 tabular 列数
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="replace")
        for mm in re.finditer(r"\\begin\{tabular\}\{([^}]*)\}", txt):
            spec = mm.group(1)
            ncol = len(re.findall(r"[clrpmbXS]|>", re.sub(r"@\{[^}]*\}|<\{[^}]*\}", "", spec)))
            start = txt[:mm.start()].count("\n") + 1
            end = txt.find("\\end{tabular}", mm.end())
            body = txt[mm.end():end if end > 0 else len(txt)]
            for k, row in enumerate(body.split(r"\\")[:-1], start=2):
                if "multicolumn" in row:
                    continue
                amps = row.count("&")
                if row.strip() and amps + 1 != ncol:
                    v.append({"rule": "T06", "file": f.name, "line": start + k,
                              "detail": f"列格式 {ncol} 列，该行有 {amps+1} 列"})

    # T07 图片路径
    for f in files:
        for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for mm in re.finditer(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", l):
                rel = mm.group(1).strip()
                cands = [rel] + [rel + e for e in (".pdf", ".png", ".jpg", ".jpeg")]
                if not any((f.parent / c).exists() for c in cands):
                    v.append({"rule": "T07", "file": f.name, "line": i, "detail": f"图片不存在: {rel}"})

    # T08 必填章节
    secs = set()
    for f in files:
        for mm in re.finditer(r"\\section\*?\{([^}]*)\}", f.read_text(encoding="utf-8", errors="replace")):
            secs.add(re.sub(r"^[\d.\s]+", "", mm.group(1)).strip().lower())
    for need in template.get("required_sections", []):
        if need.strip().lower() not in secs:
            v.append({"rule": "T08", "file": main.name, "line": 0, "detail": f"缺少章节 {need}"})

    counts = {}
    for x in v:
        counts[x["rule"]] = counts.get(x["rule"], 0) + 1
    return {"pass": not v, "violations": v, "counts": counts, "main": str(main.relative_to(project))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()
    tpl = {}
    p = Path(a.template)
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
            tpl = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            tpl = json.loads(p.read_text(encoding="utf-8"))
    else:
        tpl = json.loads(p.read_text(encoding="utf-8"))

    res = check(Path(a.project), tpl)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "texfit.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# 模板合规静态检查", "", f"- 结论: {'通过' if res['pass'] else '未通过'}", ""]
    if res["violations"]:
        md += ["| 规则 | 文件 | 行 | 说明 |", "|---|---|---|---|"]
        md += [f"| {x['rule']} | {x['file']} | {x['line']} | {x['detail']} |" for x in res["violations"]]
    (out / "texfit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"pass": res["pass"], "counts": res["counts"], "violations": len(res["violations"])}, ensure_ascii=False))
    if not a.no_fail and not res["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

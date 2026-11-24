#!/usr/bin/env python3
"""把 LaTeX 日志映射成结构化错误：文件、行号、根因、修法、是否级联。

  python logdiag.py --log build/main.log --out out
  python logdiag.py --dir paper --out out
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CATALOG = {
    "E01": ("未定义命令", "命令名拼错，或缺少对应宏包；查是否漏 \\usepackage", "核对拼写；补加载宏包"),
    "E02": ("文件未找到", "宏包/图片/子文件路径错误或未安装", "装包或修正相对路径；图片补扩展名"),
    "E03": ("宏包报错", "选项冲突或参数类型错误", "读该宏包 Error 后的说明；查选项与模板是否冲突"),
    "E05": ("交叉引用未定义", "\\label 缺失、拼错，或编译轮次不足", "补 \\label 或多编一轮"),
    "E06": ("引文键未定义", "键不在 .bib，或未跑 bibtex/biber", "核对键名；执行 bib 处理后再编"),
    "E08": ("Overfull 版式溢出", "内容超出版心，多见于长公式/宽表", "拆行、缩表、改列宽；不要靠缩字号掩盖"),
    "E09": ("字体不可用", "缺字体或编码不匹配", "换 ctex/xeCJK，或安装字体；不擅自换引擎"),
    "E10": ("缺数学模式符", "文本里出现 _ ^ 等数学符号", "给符号加 $...$ 或转义"),
}

HEAD = re.compile(r"(?:(?P<file>[^\s:()]+\.(?:tex|sty|cls|bib)):)?(?P<line>\d+)?\s*:\s*(?P<msg>.*)")
UNDEF_REF = re.compile(r"Reference `([^']+)' .*undefined")
UNDEF_CITE = re.compile(r"Citation `([^']+)' .*undefined")
OVERFULL = re.compile(r"Overfull \\hbox \(([0-9.]+)pt too wide\)(?: in paragraph at lines (\d+)--(\d+))?")
NOFILE = re.compile(r"File `([^']+)' not found")
PKGERR = re.compile(r"Package ([^ ]+) Error: (.+)")
LOR = re.compile(r"l\.(\d+)")


def parse_log(text: str):
    errs, warns, rerun = [], [], False
    if re.search(r"Rerun to get|Label\(s\) may have changed|There were undefined references", text):
        rerun = True

    lines = text.splitlines()
    cur = None
    for i, raw in enumerate(lines):
        m_over = OVERFULL.search(raw)
        if m_over:
            warns.append({"code": "E08", "file": "", "line": int(m_over.group(2) or 0),
                          "message": f"Overfull {m_over.group(1)}pt", "root_cause": CATALOG["E08"][1],
                          "fix": CATALOG["E08"][2]})
            continue
        mr = UNDEF_REF.search(raw)
        if mr:
            warns.append({"code": "E05", "file": "", "line": 0, "message": raw.strip()[:160],
                          "root_cause": CATALOG["E05"][1], "fix": CATALOG["E05"][2]})
            continue
        mc = UNDEF_CITE.search(raw)
        if mc:
            warns.append({"code": "E06", "file": "", "line": 0, "message": raw.strip()[:160],
                          "root_cause": CATALOG["E06"][1], "fix": CATALOG["E06"][2]})
            continue

        head = re.match(r"(?:(?P<file>[^\s:()]+\.(?:tex|sty|cls|bib)):\s*)?(?P<line>\d+):\s*(?P<msg>.*)", raw)
        if head and head.group("file"):
            msg = head.group("msg").strip()
            code, detail = "E00", msg
            if NOFILE.search(msg):
                code = "E02"
            elif "Undefined control sequence" in msg:
                code = "E01"
            elif "Missing $ inserted" in msg:
                code = "E10"
            elif msg.startswith("Package") or PKGERR.search(msg):
                code = "E03"
            cur = {"code": code, "file": head.group("file") or "", "line": int(head.group("line") or 0),
                   "message": detail[:200], "root_cause": CATALOG.get(code, ("其他", "", ""))[1],
                   "fix": CATALOG.get(code, ("其他", "", ""))[2]}
            if code == "E02":
                nf = NOFILE.search(msg)
                if nf:
                    cur["detail_file"] = nf.group(1)
            errs.append(cur)
            continue

        if raw.startswith("! "):
            msg = raw[2:].strip()
            code = "E00"
            if NOFILE.search(msg):
                code = "E02"
            elif msg.startswith("Undefined control sequence"):
                code = "E01"
            elif msg.startswith("Missing $"):
                code = "E10"
            elif msg.startswith("Package") or PKGERR.search(msg):
                code = "E03"
            cur = {"code": code, "file": "", "line": 0, "message": msg[:200],
                   "root_cause": CATALOG.get(code, ("其他", "", ""))[1],
                   "fix": CATALOG.get(code, ("其他", "", ""))[2]}
            if code == "E02" and NOFILE.search(msg):
                cur["detail_file"] = NOFILE.search(msg).group(1)
            errs.append(cur)
            continue

        if cur is not None and cur.get("line", 0) == 0:
            lm = LOR.search(raw)
            if lm:
                cur["line"] = int(lm.group(1))

    # 级联：同文件、同一错误码、行号相差 ≤3，说明前一条没修完导致重复报错
    for idx, e in enumerate(errs):
        for j in range(idx - 1, max(-1, idx - 4), -1):
            p = errs[j]
            if p["file"] == e["file"] and p["code"] == e["code"] and abs((p["line"] or 0) - (e["line"] or 0)) <= 3:
                e["cascade_of"] = j
                break

    counts = {}
    for e in errs:
        counts[e["code"]] = counts.get(e["code"], 0) + 1
    return {"errors": errs, "warnings": warns, "warning_count": len(warns), "rerun_required": rerun,
            "counts": counts, "converged": (not errs) and (not rerun)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    ap.add_argument("--dir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.log:
        text = Path(a.log).read_text(encoding="utf-8", errors="replace")
    else:
        cands = sorted(Path(a.dir).rglob("*.log"))
        if not cands:
            raise SystemExit("没有 .log 可解析；无 TeX 环境应使用 static_only")
        text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in cands)
    res = parse_log(text)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "logdiag.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"errors": len(res["errors"]), "warnings": res["warning_count"],
                      "counts": res["counts"], "converged": res["converged"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

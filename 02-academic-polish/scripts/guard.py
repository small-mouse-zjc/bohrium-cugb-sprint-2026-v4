#!/usr/bin/env python3
"""02 润色轻量校验：正文完整、改动可追溯、数字与引用未丢失。

主张强度、语义是否保源由 Agent 判断；脚本只硬查可回指的事实标记。
"""
import argparse
import json
import os
import re
import sys

STATUS = {"success", "partial", "needs_attention"}
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
CITE_RE = re.compile(r"\[\d+\]")


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _original_text(case):
    parts = []
    for k in ("text", "draft", "source_text", "original"):
        v = case.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v)
    for key in ("paragraphs", "sentences"):
        paras = case.get(key)
        if isinstance(paras, list):
            for p in paras:
                parts.append(p.get("text", "") if isinstance(p, dict) else str(p))
    return "\n".join(parts)


def check_result(result, case=None, outdir=None):
    errors, warnings = [], []
    if not isinstance(result, dict):
        return {"ok": False, "errors": ["result 不是对象"], "warnings": [],
                "suggested_status": "needs_attention"}

    for k in ("case_id", "status", "result"):
        if k not in result:
            errors.append(f"缺顶层字段 {k}")
    status = result.get("status")
    if status not in STATUS:
        errors.append(f"status 非法: {status!r}")

    res = result.get("result")
    if not isinstance(res, dict):
        errors.append("result.result 不是对象")
        return {"ok": False, "errors": errors, "warnings": warnings,
                "suggested_status": "needs_attention"}

    polished = str(res.get("polished_text", ""))
    if not polished.strip():
        errors.append("polished_text 为空")
    elif len(polished.strip()) < 20:
        warnings.append("polished_text 过短，可能只给了片段")

    changes = res.get("changes")
    if changes is None:
        errors.append("缺 changes")
    elif not isinstance(changes, list):
        errors.append("changes 不是数组")
    else:
        for i, c in enumerate(changes):
            if not isinstance(c, dict):
                errors.append(f"changes[{i}] 不是对象")
                continue
            if not c.get("original"):
                errors.append(f"changes[{i}] 缺 original")
            if not c.get("revised"):
                errors.append(f"changes[{i}] 缺 revised")
            if not c.get("reason"):
                warnings.append(f"changes[{i}] 未写 reason")

    if "preserved" not in res:
        warnings.append("缺 preserved 保留清单")

    if case:
        orig = _original_text(case)
        if orig.strip():
            lost_num = set(NUM_RE.findall(orig)) - set(NUM_RE.findall(polished))
            if lost_num:
                errors.append(f"润色稿丢失数字: {sorted(lost_num)}")
            lost_cite = set(CITE_RE.findall(orig)) - set(CITE_RE.findall(polished))
            if lost_cite:
                errors.append(f"润色稿丢失引用: {sorted(lost_cite)}")

    for k in ("evidence", "uncertainty"):
        if k in result and not isinstance(result[k], list):
            errors.append(f"{k} 不是数组")

    art = res.get("artifacts")
    if isinstance(art, dict):
        for key, p in art.items():
            if not p:
                continue
            path = p if os.path.isabs(p) else os.path.join(outdir or ".", p)
            if not os.path.exists(path):
                warnings.append(f"产物不存在: {key}={p}")

    suggested = "success" if not errors else ("partial" if status in STATUS else "needs_attention")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "suggested_status": suggested}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--outdir", default="/app/output")
    ap.add_argument("--case")
    args = ap.parse_args()

    result = _load(args.result)
    case = _load(args.case) if args.case else None
    report = check_result(result, case, args.outdir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()

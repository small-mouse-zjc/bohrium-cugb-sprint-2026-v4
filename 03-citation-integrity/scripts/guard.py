#!/usr/bin/env python3
"""03 引用管理轻量校验：正文-文献表闭环、条目结构完整、无悬空编号。

来源真伪与元数据准确性由 Agent 核对；脚本只查一致性与结构。
"""
import argparse
import json
import os
import re
import sys

STATUS = {"success", "partial", "needs_attention"}
NUM_CITE_RE = re.compile(r"\[([0-9,\s]+)\]")


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _cited_numbers(manuscript):
    nums = set()
    for group in NUM_CITE_RE.findall(manuscript):
        for part in group.split(","):
            part = part.strip()
            if part:
                nums.add(part)
    return nums


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

    manuscript = str(res.get("editable_manuscript", ""))
    if not manuscript.strip():
        errors.append("editable_manuscript 为空")

    bib = res.get("bibliography")
    if not isinstance(bib, list) or not bib:
        errors.append("bibliography 为空或不是数组")
        bib = []

    bib_ids, bib_keys = set(), set()
    for i, entry in enumerate(bib):
        if not isinstance(entry, dict):
            errors.append(f"bibliography[{i}] 不是对象")
            continue
        eid = str(entry.get("id") or entry.get("bib_id") or "")
        key = str(entry.get("key") or entry.get("cite_key") or "")
        if eid:
            bib_ids.add(eid)
        if key:
            bib_keys.add(key)
        if not eid and not key:
            errors.append(f"bibliography[{i}] 缺 id/key")
        for field in ("author", "year", "title", "source"):
            if not entry.get(field):
                warnings.append(f"条目 {eid or key} 缺 {field}")

    cited = _cited_numbers(manuscript)
    dangling = cited - bib_ids
    if dangling:
        errors.append(f"悬空引用编号: {sorted(dangling)}")

    unused = bib_ids - cited
    if cited and unused:
        warnings.append(f"文献表未被正文引用: {sorted(unused)}")

    mapping = res.get("number_mapping")
    if mapping is not None and not isinstance(mapping, list):
        errors.append("number_mapping 不是数组")

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

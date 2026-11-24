#!/usr/bin/env python3
"""09 平台入口：读 /input/case.json → nanopub build → /app/output/result.json。

  python scripts/run.py                                   # 默认 /input → /app/output
  python scripts/run.py --input examples/demo --output /tmp/o \
      --assertions examples/demo/assertions.json --sources examples/demo/sources.json

status 口径：
  success           校验无违规、断言 >=3 条、TriG 回解析成功
  partial           导出成功但仍有违规（如 N02 证据非逐字）或断言不足 3 条
  cannot_determine  只有源段落、没有断言文件
  rejected          输入缺 assertions.json 或 sources.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

A_KEYS = ("assertions", "assertions_file", "assertionsJson")
S_KEYS = ("sources", "sources_file", "paragraphs", "source_json")
CASE_KEYS = ("case_id", "caseId", "id", "name")


def dig(obj, keys, depth=0):
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


def find_file(inp: Path, names):
    for n in names:
        for p in inp.rglob(n):
            if "output" not in p.parts:
                return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    ap.add_argument("--assertions")
    ap.add_argument("--sources")
    a = ap.parse_args()

    inp, outp = Path(a.input), Path(a.output)
    outp.mkdir(parents=True, exist_ok=True)
    case, case_id = {}, "unknown"
    for name in ("case.json", "task.json", "input.json"):
        p = inp / name
        if p.exists():
            try:
                case = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                case_id = str(case.get("case_id") or dig(case, CASE_KEYS) or "unknown")
                break
            except Exception as e:
                case = {"_parse_error": str(e)}

    def pick(arg, keys, names):
        if arg:
            return Path(arg)
        rel = dig(case, keys)
        if rel and (inp / rel).exists():
            return inp / rel
        return find_file(inp, names)

    assertions = pick(a.assertions, A_KEYS, ("assertions.json",))
    sources = pick(a.sources, S_KEYS, ("sources.json", "paragraphs.json"))

    result = {"case_id": case_id, "status": "cannot_determine", "metrics": {}, "notes": [], "artifacts": []}
    if assertions is None or sources is None:
        result["status"] = "rejected"
        result["notes"].append(f"缺 assertions.json 或 sources.json（input={inp}）")
        (outp / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(2)

    r = subprocess.run([sys.executable, str(HERE / "nanopub.py"), "build", "--assertions", str(assertions),
                        "--sources", str(sources), "--out", str(outp), "--no-fail"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = (r.stdout or "") + (r.stderr or "")
    try:
        v = json.loads((outp / "validation.json").read_text(encoding="utf-8"))
    except Exception:
        v = {}
        result["notes"].append("validation.json 未生成：" + log[-200:])
    rates = v.get("rates") or {}
    m = result["metrics"]
    m.update({"build_rc": r.returncode, "assertions": rates.get("assertions"),
              "atomic_rate": rates.get("atomic_rate"), "verbatim_rate": rates.get("verbatim_rate"),
              "provenance_rate": rates.get("provenance_rate"),
              "export_roundtrip": rates.get("export_roundtrip"),
              "violations": rates.get("violations"),
              "codes": sorted({x.get("code") for x in (v.get("violations") or [])}),
              "pass": bool(v.get("pass"))})

    n = m.get("assertions") or 0
    if v.get("pass") and n >= 3 and m.get("export_roundtrip"):
        result["status"] = "success"
    elif v:
        result["status"] = "partial"
        if n == 0:
            result["notes"].append("断言数为 0，比率不应记 1.00；无法判 success")
        if not m.get("export_roundtrip"):
            result["notes"].append("TriG 回解析失败（命名图/断言节点/引文数不一致）")
    else:
        result["status"] = "cannot_determine"

    result["artifacts"] = [p for p in ("assertions.json", "nanopub.jsonld", "nanopub.trig", "validation.json")
                           if (outp / p).exists()]
    (outp / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()

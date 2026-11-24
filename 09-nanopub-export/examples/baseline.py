#!/usr/bin/env python3
"""09 基线对照：模拟"裸 Agent"——把断言清单原样转存成 JSON，不校验、不导出 TriG。

  python examples/baseline.py --assertions examples/demo/assertions.json --out out_base

产物只有 assertions_raw.json（故意没有 validation.json / nanopub.trig），
供 eval/metrics.py --base_dir 对比。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assertions", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    payload = json.loads(Path(a.assertions).read_text(encoding="utf-8"))
    asserts = payload.get("assertions") or []
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = [{"id": x.get("id"), "text": x.get("text"), "relation": x.get("relation")} for x in asserts]
    (out / "assertions_raw.json").write_text(json.dumps({"assertions": raw}, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    (out / "baseline.json").write_text(json.dumps({"method": "dump assertions as JSON, no validation, "
                                                   "no TriG export", "assertions": len(raw)},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"assertions": len(raw), "outputs": ["assertions_raw.json"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

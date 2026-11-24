#!/usr/bin/env python3
"""09 包自检：5 条断言全原子/逐字/来源完整且 TriG 回解析一致；四类缺陷必须命中。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
DEMO = ROOT / "examples/demo"


def run(args, rc=(0, 1)):
    r = subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode not in rc:
        raise AssertionError(f"rc={r.returncode} {' '.join(map(str,args))}\n{r.stderr[-600:]}")
    return r


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_09_"))
    ok, err = [], []
    base = json.loads((DEMO / "assertions.json").read_text(encoding="utf-8"))
    try:
        run([ROOT / "scripts/nanopub.py", "build", "--assertions", DEMO / "assertions.json",
             "--sources", DEMO / "sources.json", "--out", tmp])
        v = json.loads((tmp / "validation.json").read_text(encoding="utf-8"))
        assert v["pass"], v["violations"]
        assert v["rates"]["export_roundtrip"], "TriG 回解析失败"
        assert (tmp / "nanopub.trig").exists() and (tmp / "nanopub.jsonld").exists()
        ok.append("正例：5 条断言原子/逐字/来源完整，JSON-LD + TriG 导出且回解析一致")

        cases = [
            ("D1_non_atomic", "N01", lambda d: d["assertions"][0].__setitem__(
                "text", "Gas hydrate occurs in marine sediment at site CUG-3, and pore-water salinity is 3.5 wt%.")),
            ("D2_paraphrase", "N02", lambda d: d["assertions"][2]["evidence"].__setitem__(
                "quote", "dissociation pressure rises with salinity")),
            ("D3_missing_para", "N05", lambda d: d["assertions"][4]["evidence"].__setitem__("paragraph_id", None)),
            ("D4_duplicate", "N07", lambda d: d["assertions"].append(dict(d["assertions"][0], id="A6"))),
        ]
        for name, code, mutate in cases:
            d = json.loads(json.dumps(base))
            mutate(d)
            ap = tmp / f"{name}.json"
            ap.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            od = tmp / name
            run([ROOT / "scripts/nanopub.py", "build", "--assertions", ap, "--sources", DEMO / "sources.json",
                 "--out", od, "--no-fail"])
            vv = json.loads((od / "validation.json").read_text(encoding="utf-8"))
            codes = {x["code"] for x in vv["violations"]}
            assert code in codes, f"{name} 未命中 {code}，实际 {sorted(codes)}"
            ok.append(f"{name} → {code}")

        print("SELFTEST OK")
        for line in ok:
            print("  ✓", line)
    except AssertionError as e:
        err.append(str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if err:
        print("SELFTEST FAIL")
        for e in err:
            print("  ✗", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

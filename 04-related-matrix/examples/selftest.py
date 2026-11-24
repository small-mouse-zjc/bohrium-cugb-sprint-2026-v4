#!/usr/bin/env python3
"""04 包自检：正例五项全过；四类注入缺陷必须命中。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(args, rc=(0,)):
    r = subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode not in rc:
        raise AssertionError(f"rc={r.returncode} {' '.join(map(str,args))}\n{r.stdout}\n{r.stderr}")
    return r


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_04_"))
    ok, err = [], []
    demo = ROOT / "examples/demo"
    try:
        run([ROOT / "scripts/matrix.py", "build", "--works", demo / "works.json",
             "--dims", demo / "dimensions.json", "--out", tmp])
        m = json.loads((tmp / "matrix.json").read_text(encoding="utf-8"))
        assert m["works"] == 6 and len(m["gaps"]) == 1, f"矩阵异常: {m['works']} works, {len(m['gaps'])} gaps"
        assert m["gaps"][0]["limitation"] == "长期监测", "空白推导不对"
        assert len(m["conflicts"]) == 1, "冲突未识别"
        ok.append(f"矩阵 6 篇/2 组以上/空白 {len(m['gaps'])} 条/冲突 {len(m['conflicts'])} 条")

        run([ROOT / "scripts/claim_bind.py", "--draft", demo / "intro_draft.md", "--works", demo / "works.json",
             "--manuscript", demo / "manuscript.json", "--out", tmp])
        b = json.loads((tmp / "bind.json").read_text(encoding="utf-8"))
        assert b["pass"], f"正例未过: {[v['type'] for v in b['violations']]}"
        ok.append("正例：论断挂引用/空白支撑/关键覆盖/贡献证据 全 1.00")

        drafts = json.loads((ROOT / "baseline/fixtures/injected.json").read_text(encoding="utf-8"))["fixtures"]
        src = (demo / "intro_draft.md").read_text(encoding="utf-8")
        for fx in drafts:
            t = src
            for a, c in fx["replace"]:
                assert a in t, f"夹具定位失败: {a}"
                t = t.replace(a, c)
            dp = tmp / f"{fx['name']}.md"
            dp.write_text(t, encoding="utf-8")
            od = tmp / fx["name"]
            run([ROOT / "scripts/claim_bind.py", "--draft", dp, "--works", demo / "works.json",
                 "--manuscript", demo / "manuscript.json", "--out", od, "--no-fail"], rc=(0, 1))
            got = json.loads((od / "bind.json").read_text(encoding="utf-8"))
            types = {v["type"] for v in got["violations"]}
            assert set(fx["expect_types"]) <= types, f"{fx['name']} 未检出，实际 {sorted(types)}"
            assert not got["pass"], f"{fx['name']} 判为通过"
            ok.append(f"{fx['name']} → {sorted(set(fx['expect_types']))}")

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

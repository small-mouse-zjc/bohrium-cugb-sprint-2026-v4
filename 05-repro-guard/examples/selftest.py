#!/usr/bin/env python3
"""05 包自检：正例参数全溯源、九项齐全、步骤完整；四类注入缺陷必须命中。"""
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


def run(args, rc=(0,)):
    r = subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode not in rc:
        raise AssertionError(f"rc={r.returncode} {' '.join(map(str,args))}\n{r.stdout}\n{r.stderr}")
    return r


def align(draft, out):
    return run([ROOT / "scripts/param_align.py", "--draft", draft, "--params", DEMO / "params.json",
                "--sources", DEMO / "config.yaml", DEMO / "train.log", DEMO / "model.py",
                "--out", out, "--no-fail"], rc=(0, 1))


def check(manifest, steps, params, out):
    return run([ROOT / "scripts/repro_check.py", "--manifest", manifest, "--steps", steps,
                "--params", params, "--out", out, "--no-fail"], rc=(0, 1))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_05_"))
    ok, err = [], []
    try:
        align(DEMO / "methods.md", tmp)
        a = json.loads((tmp / "audit.json").read_text(encoding="utf-8"))
        assert a["pass"], f"正例参数未过: {a['violations']}"
        check(DEMO / "manifest.json", DEMO / "steps.json", tmp / "params.csv", tmp)
        r = json.loads((tmp / "repro.json").read_text(encoding="utf-8"))
        assert r["pass"], f"正例复现未过: {r['violations']}"
        ok.append("正例：有源率 100%、无源 0、冲突 0、九项 100%、步骤 100%")

        fx = json.loads((ROOT / "baseline/fixtures/injected.json").read_text(encoding="utf-8"))["fixtures"]
        base_text = (DEMO / "methods.md").read_text(encoding="utf-8")
        for f in fx:
            od = tmp / f["name"]
            if f["kind"] == "text":
                t = base_text
                for x, y in f.get("replace", []):
                    t = t.replace(x, y)
                t += f.get("append", "")
                dp = tmp / f"{f['name']}.md"
                dp.write_text(t, encoding="utf-8")
                align(dp, od)
                got = json.loads((od / "audit.json").read_text(encoding="utf-8"))
            elif f["kind"] == "manifest":
                m = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
                for k in f["drop_keys"]:
                    m.pop(k, None)
                mp = tmp / f"{f['name']}.json"
                mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
                check(mp, DEMO / "steps.json", tmp / "params.csv", od)
                got = json.loads((od / "repro.json").read_text(encoding="utf-8"))
            else:
                s = json.loads((DEMO / "steps.json").read_text(encoding="utf-8"))
                for d in f["drop_step_fields"]:
                    for step in s["steps"]:
                        if step["id"] == d["id"]:
                            for kk in d["fields"]:
                                step.pop(kk, None)
                sp = tmp / f"{f['name']}.json"
                sp.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
                check(DEMO / "manifest.json", sp, tmp / "params.csv", od)
                got = json.loads((od / "repro.json").read_text(encoding="utf-8"))
            types = {v["type"] for v in got["violations"]}
            assert set(f["expect_types"]) <= types, f"{f['name']} 未检出，实际 {sorted(types)}"
            ok.append(f"{f['name']} → {sorted(set(f['expect_types']))}")

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

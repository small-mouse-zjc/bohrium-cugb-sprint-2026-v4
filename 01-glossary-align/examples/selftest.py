#!/usr/bin/env python3
"""01 包自检：正例必须通过；三类注入缺陷必须被抓到。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(args, expect_rc=(0,)):
    r = subprocess.run([PY] + [str(a) for a in args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode not in expect_rc:
        raise AssertionError(f"命令失败 rc={r.returncode}\n{' '.join(map(str,args))}\n{r.stdout}\n{r.stderr}")
    return r


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_01_"))
    ok, fail = [], []
    try:
        paras = tmp / "paras.jsonl"
        run([ROOT / "scripts/pdf_to_paras.py", "--in", ROOT / "examples/demo/source.txt", "--out", paras])
        rows = [json.loads(l) for l in paras.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(rows) >= 7, f"取段过少: {len(rows)}"
        assert all(r["id"].startswith("P") for r in rows), "段落编号异常"
        ok.append(f"取段 {len(rows)} 段，编号稳定")

        glos = tmp / "glossary.csv"
        run([ROOT / "scripts/glossary.py", "lock", "--in", ROOT / "examples/demo/glossary_filled.csv", "--out", glos])
        gl = glos.read_text(encoding="utf-8").strip().splitlines()
        assert len(gl) >= 10, "术语表行数不足"
        ok.append(f"术语锁定 {len(gl)-1} 条")

        qc1 = tmp / "qc1"
        r = run([ROOT / "scripts/qc.py", "--paras", paras, "--bi", ROOT / "examples/demo/bilingual.json",
                 "--glossary", glos, "--out", qc1])
        d = json.loads((qc1 / "qc.json").read_text(encoding="utf-8"))
        assert d["pass"] is True, f"正例未通过: {d['failed']}"
        ok.append("正例：五项比率全 1.00，质检通过")

        fixtures = json.loads((ROOT / "baseline/fixtures/injected.json").read_text(encoding="utf-8"))
        base = json.loads((ROOT / "examples/demo/bilingual.json").read_text(encoding="utf-8"))
        for fx in fixtures["fixtures"]:
            bi = json.loads(json.dumps(base))
            for m in fx["mutations"]:
                idx = next((i for i, p in enumerate(bi["paragraphs"]) if p["id"] == m["id"]), None)
                if idx is None:
                    continue
                if m["op"] == "drop":
                    bi["paragraphs"].pop(idx)
                elif m["op"] == "replace":
                    bi["paragraphs"][idx]["target"] = bi["paragraphs"][idx]["target"].replace(m["from"], m["to"])
                elif m["op"] == "empty":
                    bi["paragraphs"][idx]["target"] = ""
            bp = tmp / f"{fx['name']}.json"
            bp.write_text(json.dumps(bi, ensure_ascii=False), encoding="utf-8")
            qcd = tmp / fx["name"]
            run([ROOT / "scripts/qc.py", "--paras", paras, "--bi", bp, "--glossary", glos,
                 "--out", qcd, "--no-fail"], expect_rc=(0, 1))
            got = json.loads((qcd / "qc.json").read_text(encoding="utf-8"))
            types = {v["type"] for v in got["violations"]}
            missing = [t for t in fx["expect_types"] if t not in types]
            assert not missing, f"{fx['name']} 未检出 {missing}，实际 {sorted(types)}"
            assert got["pass"] is False, f"{fx['name']} 居然判为通过"
            ok.append(f"{fx['name']} → 检出 {sorted(set(fx['expect_types']) & types)}")

        print("SELFTEST OK")
        for line in ok:
            print("  ✓", line)
    except AssertionError as e:
        fail.append(str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if fail:
        print("SELFTEST FAIL")
        for f in fail:
            print("  ✗", f)
        sys.exit(1)


if __name__ == "__main__":
    main()

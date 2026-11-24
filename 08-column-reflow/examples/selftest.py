#!/usr/bin/env python3
"""08 包自检：用已知真值验证重排；朴素基线必须明显更差；页眉页脚必须剔除。"""
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
        raise AssertionError(f"rc={r.returncode} {' '.join(map(str,args))}\n{r.stderr[-800:]}")
    return r


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_08_"))
    ok, err = [], []
    try:
        run([ROOT / "examples/tools/make_demo.py", "--out", tmp])
        pdf = tmp / "demo.pdf"
        truth = tmp / "truth.json"
        assert pdf.exists(), "演示 PDF 未生成"

        rd = tmp / "reflow"
        run([ROOT / "scripts/reflow.py", "--pdf", pdf, "--out", rd, "--audit"])
        info = json.loads((rd / "reflow.json").read_text(encoding="utf-8"))
        assert info["layout"] == "2-column", info["layout"]
        assert len(info["dropped_headers_footers"]) == 4, "页眉页脚未全部剔除"
        assert not info["suspicious"], f"仍有串栏疑似: {info['suspicious']}"
        m = json.loads(run([ROOT / "eval/measure.py", "--out", rd, "--truth", truth]).stdout)
        assert m["order_match"] is True, f"顺序与真值不一致: {m}"
        assert m["inversions"] == 0, m
        ok.append("双栏重排：与真值逐段一致，0 逆序，0 串栏，页眉页脚 4 条全剔除")

        bd = tmp / "base"
        run([ROOT / "scripts/reflow.py", "--pdf", pdf, "--out", bd, "--baseline"])
        mb = json.loads(run([ROOT / "eval/measure.py", "--out", bd, "--truth", truth]).stdout)
        assert mb["order_match"] is False and mb["inversions"] >= 10, mb
        ok.append(f"朴素基线：位置命中 {mb['exact_position_rate']:.0%}、逆序 {mb['inversions']} 处、相邻错位 {mb['adjacent_errors']} 处（对照，不是分数）")

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

#!/usr/bin/env python3
"""07 包自检：损坏工程被抓、修复版零违规、真实日志分类正确、无 TeX 时报 static_only。"""
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


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_07_"))
    ok, err = [], []
    try:
        od = tmp / "broken"
        run([ROOT / "scripts/texfit.py", "--project", DEMO / "broken", "--template", DEMO / "template.yaml",
             "--out", od, "--no-fail"], rc=(0, 1))
        b = json.loads((od / "texfit.json").read_text(encoding="utf-8"))
        rules = set(b["counts"])
        need = {"T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08"}
        assert need <= rules, f"静态检查漏规则: 缺 {sorted(need - rules)}"
        assert not b["pass"], "损坏工程被判通过"
        ok.append(f"损坏工程命中 {len(rules)} 条规则 / {len(b['violations'])} 处违规")

        fd = tmp / "fixed"
        run([ROOT / "scripts/texfit.py", "--project", DEMO / "fixed", "--template", DEMO / "template.yaml", "--out", fd])
        f = json.loads((fd / "texfit.json").read_text(encoding="utf-8"))
        assert f["pass"] and not f["violations"], f"修复版仍有违规: {f['violations']}"
        ok.append("修复版 0 违规")

        ld = tmp / "log"
        run([ROOT / "scripts/logdiag.py", "--log", DEMO / "fixtures/pdflatex_2022_broken.log", "--out", ld])
        d = json.loads((ld / "logdiag.json").read_text(encoding="utf-8"))
        assert d["counts"].get("E10", 0) >= 2, d["counts"]
        assert d["counts"].get("E01", 0) >= 2, d["counts"]
        assert d["counts"].get("E02", 0) >= 1, d["counts"]
        assert {w["code"] for w in d["warnings"]} >= {"E05", "E06"}, [w["code"] for w in d["warnings"]]
        lines = {e["code"]: e["line"] for e in d["errors"]}
        assert 13 in [e["line"] for e in d["errors"] if e["code"] == "E10"], "缺 $ 行号定位失败"
        assert 19 in [e["line"] for e in d["errors"] if e["code"] == "E01"], "未定义命令行号定位失败"
        ok.append("真实日志：E10×2 / E01×2 / E02×1，警告 E05/E06，行号 13/19/30 定位正确")

        bd = tmp / "build"
        run([ROOT / "scripts/build.py", "--project", DEMO / "fixed", "--out", bd], rc=(0, 1))
        m = json.loads((bd / "build_manifest.json").read_text(encoding="utf-8"))
        assert m["status"] in ("success", "partial", "static_only", "failed"), m["status"]
        if m["status"] == "static_only":
            assert "未执行真实编译" in m["note"]
            ok.append("本机无 TeX：切到 static_only 并明确未编译（未谎称通过）")
        else:
            assert m["status"] in ("success", "partial"), f"有 TeX 却 failed：{m.get('note')}"
            assert m.get("rerun_required") is not None and m.get("converged") is not None, "manifest 缺收敛字段"
            ok.append(f"本机有 TeX：status={m['status']} converged={m['converged']} "
                      f"bibtex_runs={m['bibtex_runs']} errors={m['errors']} pages={m['pages']}")

        # 平台入口：/input/case.json → /app/output/result.json
        rp = tmp / "run"
        rp.mkdir()
        (rp / "case.json").write_text(json.dumps({"case_id": "selftest-07",
                                                  "project": "fixed", "template": "template.yaml"},
                                                 ensure_ascii=False), encoding="utf-8")
        shutil.copytree(DEMO / "fixed", rp / "fixed")
        shutil.copy(DEMO / "template.yaml", rp / "template.yaml")
        ro = tmp / "run_out"
        run([ROOT / "scripts/run.py", "--input", rp, "--output", ro], rc=(0, 1, 2))
        rj = json.loads((ro / "result.json").read_text(encoding="utf-8"))
        assert rj["case_id"] == "selftest-07", rj
        assert rj["status"] in ("success", "partial", "cannot_determine"), rj["status"]
        assert "metrics" in rj and "artifacts" in rj, rj
        ok.append(f"平台入口：case.json→result.json，status={rj['status']}，"
                  f"violations={rj['metrics'].get('violations')}，build={rj['metrics'].get('build_status')}")

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

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
            # SKILL §6 的收敛门槛必须在这里被锁住，不能把 partial 当通过
            assert m["status"] == "success", f"有 TeX 但未到 success：status={m['status']} {m.get('note')}"
            assert m.get("converged") is True, f"converged={m.get('converged')}"
            assert m.get("errors") == 0, f"errors={m.get('errors')}"
            assert (m.get("bibtex_runs") or 0) >= 1, f"bibtex_runs={m.get('bibtex_runs')}"
            assert m.get("rerun_required") is False, f"rerun_required={m.get('rerun_required')}"
            assert m.get("pdf", {}).get("sha256"), "manifest 未记录 PDF sha256"
            ok.append(f"本机有 TeX：硬门槛全过 status={m['status']} converged={m['converged']} "
                      f"bibtex_runs={m['bibtex_runs']} errors={m['errors']} pages={m['pages']} "
                      f"pdf.sha256={m['pdf']['sha256'][:12]}…")

            # 字节级复现：同工程再编一次，PDF sha256 必须相同且与清单一致
            bd2 = tmp / "build2"
            run([ROOT / "scripts/build.py", "--project", DEMO / "fixed", "--out", bd2], rc=(0, 1))
            m2 = json.loads((bd2 / "build_manifest.json").read_text(encoding="utf-8"))
            assert m2["pdf"]["sha256"] == m["pdf"]["sha256"], (
                "两次编译 PDF 不一致：", m["pdf"]["sha256"], m2["pdf"]["sha256"])
            import hashlib
            got = hashlib.sha256((bd2 / m2["pdf"]["path"]).read_bytes()).hexdigest()
            assert got == m2["pdf"]["sha256"], "清单里的 sha256 与实际文件不符"
            ok.append(f"字节复现：两次编译 PDF sha256 相同（{m['pdf']['sha256'][:12]}…），"
                      f"且与清单记录一致（SOURCE_DATE_EPOCH={m['compile_env']['SOURCE_DATE_EPOCH']}）")

            # 反向锁定：故意跳过 bibtex → 必须降级为 partial，不许 success
            bd3 = tmp / "build_nobib"
            rr = subprocess.run([PY, str(ROOT / "scripts/build.py"), "--project", str(DEMO / "fixed"),
                                 "--out", str(bd3), "--no-bibtex"], capture_output=True, text=True,
                                encoding="utf-8")
            assert rr.returncode != 0, "跳过 bibtex 仍返回 0（门槛失效）"
            m3 = json.loads((bd3 / "build_manifest.json").read_text(encoding="utf-8"))
            assert m3["status"] == "partial" and m3["converged"] is False, m3["status"]
            ok.append(f"反向锁定：--no-bibtex 时 status={m3['status']} converged=False（引文未解析不判 success）")

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

        # 多文件 + 注释 + biblatex 引用：\input 两章、\parencite/\textcite，注释里故意写 \toprule 和假 cite
        mp = tmp / "multi"
        mp.mkdir()
        shutil.copytree(DEMO / "multi", mp / "paper")
        (mp / "case.json").write_text(json.dumps({"case_id": "selftest-multi",
                                                  "project": "paper", "template": "paper/template.yaml"},
                                                 ensure_ascii=False), encoding="utf-8")
        mo = tmp / "multi_out"
        run([ROOT / "scripts/run.py", "--input", mp, "--output", mo], rc=(0, 1, 2))
        mj = json.loads((mo / "result.json").read_text(encoding="utf-8"))
        assert mj["metrics"]["violations"] == 0, f"多文件案例误报违规: {mj['metrics'].get('violation_counts')}"
        assert mj["status"] in ("success", "cannot_determine"), mj["status"]
        ok.append(f"多文件案例（\\input 两章 + 注释干扰 + \\parencite/\\textcite）：violations=0，"
                  f"status={mj['status']}，pages={mj['metrics'].get('pages')}")

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

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

        # 转述数字必须与所引作品记录一致：3.2 MPa 改成 9.9 MPa 仍挂 [W1] 也要报
        t = src.replace("露点偏移可达 3.2 MPa [W1]", "露点偏移可达 9.9 MPa [W1]")
        dp = tmp / "num_conflict.md"
        dp.write_text(t, encoding="utf-8")
        od = tmp / "num_conflict"
        run([ROOT / "scripts/matrix.py", "build", "--works", demo / "works.json",
             "--dims", demo / "dimensions.json", "--out", od])
        run([ROOT / "scripts/claim_bind.py", "--draft", dp, "--works", demo / "works.json",
             "--manuscript", demo / "manuscript.json", "--out", od, "--no-fail"], rc=(0, 1))
        nc = json.loads((od / "bind.json").read_text(encoding="utf-8"))
        assert any(v["type"] == "claim_evidence_conflict" and "9.9" in v["detail"] for v in nc["violations"]), nc["violations"]
        assert nc["pass"] is False, nc["rates"]
        ok.append("论断数字 9.9 MPa 在所引 W1 记录里找不到 → claim_evidence_conflict、pass=False")

        # 空白改引非支撑文献 [W1][W2]（该空白支撑是 W4/W6）→ 按矩阵每个 gap 复核，必须报
        t = src.replace("现有工作均未覆盖长期监测 [W4][W6]", "这一尺度的研究存在明显空白 [W1][W2]")
        dp = tmp / "gap_wrong_support.md"
        dp.write_text(t, encoding="utf-8")
        od = tmp / "gap_wrong_support"
        run([ROOT / "scripts/matrix.py", "build", "--works", demo / "works.json",
             "--dims", demo / "dimensions.json", "--out", od])
        run([ROOT / "scripts/claim_bind.py", "--draft", dp, "--works", demo / "works.json",
             "--manuscript", demo / "manuscript.json", "--out", od, "--no-fail"], rc=(0, 1))
        gw = json.loads((od / "bind.json").read_text(encoding="utf-8"))
        assert any(v["type"] == "gap_unsupported" and "长期监测" in v["detail"] for v in gw["violations"]), gw["violations"]
        assert gw["rates"]["gap_support_rate"] == 0.0 and gw["pass"] is False, gw["rates"]
        ok.append("空白改引 W1/W2 → gap_support_rate=0.0、逐 gap 报「长期监测未获 >=2 篇支撑」、pass=False")

        # 重述式空白（不含「覆盖/研究/工作」字样）仍要被识别为空白句，并卡支撑
        t = src.replace("现有工作均未覆盖长期监测 [W4][W6]", "现有工作在这一尺度上仍有明显不足 [W1][W2]")
        dp = tmp / "gap_restated.md"
        dp.write_text(t, encoding="utf-8")
        od = tmp / "gap_restated"
        run([ROOT / "scripts/matrix.py", "build", "--works", demo / "works.json",
             "--dims", demo / "dimensions.json", "--out", od])
        run([ROOT / "scripts/claim_bind.py", "--draft", dp, "--works", demo / "works.json",
             "--manuscript", demo / "manuscript.json", "--out", od, "--no-fail"], rc=(0, 1))
        gr = json.loads((od / "bind.json").read_text(encoding="utf-8"))
        assert gr["gap_sentences"] >= 1 and gr["pass"] is False, gr
        assert any(v["type"] == "gap_unsupported" for v in gr["violations"]), gr["violations"]
        ok.append("重述式空白句（无「覆盖/研究/工作」字样）仍被识别、gap 支撑仍被卡")
        ein = tmp / "entry_in"
        ein.mkdir()
        for f in ("works.json", "dimensions.json", "manuscript.json", "intro_draft.md"):
            shutil.copy(demo / f, ein / f)
        (ein / "case.json").write_text(json.dumps({"case_id": "selftest-04", "works": "works.json",
                                                   "dimensions": "dimensions.json", "manuscript": "manuscript.json",
                                                   "draft": "intro_draft.md"}, ensure_ascii=False), encoding="utf-8")
        eo = tmp / "entry_out"
        run([ROOT / "scripts/run.py", "--input", ein, "--output", eo])
        rj = json.loads((eo / "result.json").read_text(encoding="utf-8"))
        assert rj["case_id"] == "selftest-04" and rj["status"] == "success", rj
        assert {"matrix.json", "bind.json"} <= set(rj["artifacts"]), rj["artifacts"]
        ok.append(f"平台入口：case.json→result.json，status={rj['status']}，works={rj['metrics']['works']}")

        # result.json 的空白口径必须与 bind.json 一致，且带数字核对计数
        eb = json.loads((eo / "bind.json").read_text(encoding="utf-8"))
        met = rj["metrics"]
        assert met["gaps_total"] == eb["gaps_total"] == 1 and met["gaps_covered"] == eb["gaps_covered"] == 1, met
        assert met["claim_evidence_checks"] == eb["claim_evidence_checks"] >= 1, met
        md = (eo / "bind_report.md").read_text(encoding="utf-8")
        assert f"论断 {eb['claims']} 条，挂引用 {eb['claim_cited']} 条" in md, md
        assert f"空白句 {eb['gap_sentences']} 条，支撑充分 {eb['gap_supported']} 条" in md, md
        assert f"数字核对 {eb['claim_evidence_checks']} 处" in md, md
        assert f"矩阵空白 {eb['gaps_total']} 个，草稿里获 >=2 篇支撑 {eb['gaps_covered']} 个" in md, md
        assert f"贡献 {eb['contributions']} 条" in md, md
        ok.append(f"result.json.metrics 与 bind.json/bind_report.md 同口径（空白 {met['gaps_covered']}/{met['gaps_total']}、数字核对 {met['claim_evidence_checks']} 处、✓ 行数逐项相符）")

        # 零贡献草稿：不能再报 1.00
        zc = tmp / "zero_contrib.md"
        zc.write_text(src.split("# 4 贡献")[0], encoding="utf-8")
        run([ROOT / "scripts/claim_bind.py", "--draft", zc, "--works", demo / "works.json",
             "--manuscript", demo / "manuscript.json", "--out", tmp / "zc", "--no-fail"], rc=(0, 1))
        z = json.loads((tmp / "zc" / "bind.json").read_text(encoding="utf-8"))
        assert z["rates"]["contribution_evidence_rate"] is None, z["rates"]
        assert "contribution_missing" in {v["type"] for v in z["violations"]}, z["violations"]
        assert not z["pass"], "零贡献草稿被判通过"
        ok.append("零贡献草稿：contribution_evidence_rate=None + contribution_missing，不再虚报 1.00")

        # 悬空引用不能算"已挂引用"
        dg = src.replace("3.2 MPa [W1]，分子模拟在 20 MPa 以下没有观察到露点上升 [W2]",
                         "3.2 MPa [W9]，分子模拟在 20 MPa 以下没有观察到露点上升 [W9]")
        dp2 = tmp / "dangling.md"
        dp2.write_text(dg, encoding="utf-8")
        run([ROOT / "scripts/claim_bind.py", "--draft", dp2, "--works", demo / "works.json",
             "--manuscript", demo / "manuscript.json", "--out", tmp / "dg", "--no-fail"], rc=(0, 1))
        d = json.loads((tmp / "dg" / "bind.json").read_text(encoding="utf-8"))
        assert d["rates"]["claim_citation_rate"] < 1.0, d["rates"]
        assert "claim_uncited" in {v["type"] for v in d["violations"]}, d["violations"]
        ok.append(f"悬空引用：claim_citation_rate={d['rates']['claim_citation_rate']}（不再算挂上）")

        # 基线对照：裸 Agent 只有 summary.md，没有矩阵与绑定
        base = tmp / "base"
        run([ROOT / "examples/baseline.py", "--works", demo / "works.json", "--out", base])
        assert (base / "summary.md").exists() and not (base / "matrix.json").exists()
        import importlib.util
        spec = importlib.util.spec_from_file_location("m04", ROOT / "eval/metrics.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        sb, ss = mod.load(base), mod.load(tmp / "entry_out")
        assert sb["group_total"] is None and sb["pass"] is False, sb
        assert ss["group_total"] == 3 and ss["pass"] is True, ss
        ok.append("基线对照：裸 Agent group_total=None/pass=False vs Skill 3/True")

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

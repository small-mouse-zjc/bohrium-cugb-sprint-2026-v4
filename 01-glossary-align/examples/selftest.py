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
        assert len(rows) >= 12, f"取段过少: {len(rows)}"
        assert all(r["id"][0] in ("P", "H") for r in rows), "段落编号异常"
        heads = [r for r in rows if r.get("type") == "heading"]
        assert len(heads) == 5, f"章节标题未作为段落输出: {len(heads)}"
        assert all(r["text"] for r in heads), "标题文本为空"
        ok.append(f"取段 {len(rows)} 段（含 5 个章节标题，H 前缀不打乱正文 P 编号）")

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

        # 平台入口：/input/case.json → /app/output/result.json
        ent_in = tmp / "entry_in"
        ent_out = tmp / "entry_out"
        shutil.copytree(ROOT / "examples/demo", ent_in)
        r = run([ROOT / "scripts/run.py", "--input", ent_in, "--output", ent_out])
        rj = json.loads((ent_out / "result.json").read_text(encoding="utf-8"))
        assert rj["status"] == "success" and rj["metrics"]["pass"] is True, rj
        assert rj["metrics"]["headings"] == 5, rj["metrics"]
        assert (ent_out / "qc.json").exists() and (ent_out / "bilingual.json").exists(), "产物缺失"
        ok.append("平台入口：case.json→result.json，status=success、12 段含 5 标题、五项比率带出")

        # 无译文草稿时只能交前半段，status 必须是 partial（不许冒充 success）
        no_draft = tmp / "entry_nodraft"
        shutil.copytree(ROOT / "examples/demo", no_draft)
        case = json.loads((no_draft / "case.json").read_text(encoding="utf-8"))
        case.pop("bilingual")
        (no_draft / "case.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/run.py", "--input", no_draft, "--output", tmp / "nodraft_out"], expect_rc=(1,))
        nd = json.loads((tmp / "nodraft_out/result.json").read_text(encoding="utf-8"))
        assert nd["status"] == "partial" and nd["metrics"]["pass"] is False, nd
        ok.append("缺译文草稿 → status=partial，不再假报成功")

        # 硬违规必须卡 pass：单位丢失 + 重复译文（比率仍可能全 1.0）
        bih = json.loads((ROOT / "examples/demo/bilingual.json").read_text(encoding="utf-8"))
        for p in bih["paragraphs"]:
            if p["id"] == "P0002":
                p["target"] = p["target"].replace("MPa", "").replace("兆帕", "")
            if p["id"] == "P0003":
                p["target"] = next(x["target"] for x in bih["paragraphs"] if x["id"] == "P0002")
        hp = tmp / "hard.json"
        hp.write_text(json.dumps(bih, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/qc.py", "--paras", paras, "--bi", hp, "--glossary", glos,
             "--out", tmp / "hard", "--no-fail"], expect_rc=(0, 1))
        hd = json.loads((tmp / "hard/qc.json").read_text(encoding="utf-8"))
        assert hd["pass"] is False, "硬违规未卡 pass"
        assert {"number_unit_mismatch", "dup_target"} <= {v["type"] for v in hd["violations"]}, hd["violation_counts"]
        ok.append(f"硬违规卡 pass：number_unit_mismatch + dup_target，hard_violations={hd['hard_violations']}")

        # 数值互换：数字总量、单位数量都没变，只查"存在性"必然漏检
        sw = json.loads((ROOT / "examples/demo/bilingual.json").read_text(encoding="utf-8"))
        for p in sw["paragraphs"]:
            if p["id"] == "P0002":
                p["target"] = p["target"].replace("3.5 wt%", "4 wt%").replace("4 °C", "3.5 °C")
        sp = tmp / "swap.json"
        sp.write_text(json.dumps(sw, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/qc.py", "--paras", paras, "--bi", sp, "--glossary", glos,
             "--out", tmp / "swap", "--no-fail"], expect_rc=(0, 1))
        sd = json.loads((tmp / "swap/qc.json").read_text(encoding="utf-8"))
        assert sd["pass"] is False and any(v["type"] == "number_unit_mismatch" for v in sd["violations"]), sd["violation_counts"]
        assert sd["rates"]["number_preservation"] < 1.0, sd["rates"]
        ok.append(f"数值互换（3.5 wt% ↔ 4 °C）→ number_unit_mismatch，数字保真率 {sd['rates']['number_preservation']:.2f}")

        # basis 全删：契约必填字段，不能静默通过
        nb = json.loads((ROOT / "examples/demo/bilingual.json").read_text(encoding="utf-8"))
        for p in nb["paragraphs"]:
            p["basis"] = ""
        bp2 = tmp / "nobasis.json"
        bp2.write_text(json.dumps(nb, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/qc.py", "--paras", paras, "--bi", bp2, "--glossary", glos,
             "--out", tmp / "nobasis", "--no-fail"], expect_rc=(0, 1))
        nd2 = json.loads((tmp / "nobasis/qc.json").read_text(encoding="utf-8"))
        assert nd2["pass"] is False and nd2["violation_counts"].get("missing_basis", 0) >= 8, nd2["violation_counts"]
        assert nd2["rates"]["basis_coverage"] == 0.0, nd2["rates"]
        ok.append(f"basis 全删 → missing_basis={nd2['violation_counts']['missing_basis']}、basis_coverage=0.00，不再静默通过")

        # 降级段（untranslatable + 保留原文片段）不该被剔出覆盖率分子
        cr = json.loads((ROOT / "examples/demo/bilingual.json").read_text(encoding="utf-8"))
        for p in cr["paragraphs"]:
            if p["id"] == "P0002":
                p["status"] = "untranslatable"
                p["target"] = p.get("source") or p.get("target") or "原文片段"
                p["risk"] = ["原文残缺，保留片段"]
        cp = tmp / "untrans.json"
        cp.write_text(json.dumps(cr, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/qc.py", "--paras", paras, "--bi", cp, "--glossary", glos,
             "--out", tmp / "untrans", "--no-fail"])
        cd = json.loads((tmp / "untrans/qc.json").read_text(encoding="utf-8"))
        assert cd["rates"]["coverage"] == 1.0 and cd["pass"] is True, cd["rates"]
        bad = {v["type"] for v in cd["violations"]} & {"term_drift", "number_lost", "citation_lost", "length_ratio"}
        assert not bad, f"降级段仍被译文保真检查误判: {bad}"
        ok.append("untranslatable 段保留非空片段 → coverage 1.00、pass=True、四项保真零误判（不把降级当漏译）")

        # 父子术语：只出现"天然气水合物"时不要求"水合物"的译名
        sub = tmp / "subterm"
        sub.mkdir()
        (sub / "paras.jsonl").write_text(json.dumps({"id": "P9001", "type": "body", "page": 1,
            "section": "x", "text": "天然气水合物稳定带分布于深海。"}, ensure_ascii=False) + "\n", encoding="utf-8")
        (sub / "bi.json").write_text(json.dumps({"case_id": "subterm", "paragraphs": [{"id": "P9001", "type": "body",
            "source": "天然气水合物稳定带分布于深海。", "target": "天然气水合物稳定带分布于深海。",
            "status": "ok", "basis": "专名照抄"}]}, ensure_ascii=False), encoding="utf-8")
        (sub / "g.csv").write_text("source,translation\n天然气水合物,天然气水合物\n水合物,水合物X\n", encoding="utf-8")
        run([ROOT / "scripts/qc.py", "--paras", sub / "paras.jsonl", "--bi", sub / "bi.json",
             "--glossary", sub / "g.csv", "--out", sub / "out", "--no-fail"])
        subd = json.loads((sub / "out/qc.json").read_text(encoding="utf-8"))
        assert subd["pass"] is True and not any(v["type"] == "term_drift" for v in subd["violations"]), subd
        assert subd["rates"]["term_consistency"] == 1.0, subd["rates"]
        ok.append("父子术语遮蔽：只出现「天然气水合物」时不误判「水合物」→ 无 term_drift，一致率 1.00")

        # 基线对照：同一套指标下 Skill 优于裸 Agent
        bo = tmp / "base_out"
        run([ROOT / "examples/baseline.py", "--paras", paras, "--glossary", glos, "--out", bo])
        r = run([ROOT / "eval/metrics.py", "--skill", ent_out, "--base", bo])
        md = json.loads(r.stdout[:r.stdout.index("| 指标")].strip())
        assert md["skill_pass"] is True and md["base_pass"] is False, md
        assert md["delta"]["term_consistency"] and md["delta"]["term_consistency"] > 0, md["delta"]
        ok.append(f"基线对照：Skill pass=True vs 基线 pass=False，术语一致率差 {md['delta']['term_consistency']:+.2%}")

        # 缺 qc.json 时 metrics 不崩：该侧记 None
        empty = tmp / "empty_base"; empty.mkdir()
        r = run([ROOT / "eval/metrics.py", "--skill", ent_out, "--base", empty])
        assert "缺少" not in r.stdout and "Traceback" not in r.stderr, r.stdout[-300:]
        ok.append("缺 qc.json 的基线段：记 None 不崩溃")

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

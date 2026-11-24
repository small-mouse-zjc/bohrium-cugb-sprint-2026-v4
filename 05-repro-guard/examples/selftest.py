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

        # 平台入口：case.json → result.json
        ein, eout = tmp / "entry_in", tmp / "entry_out"
        shutil.copytree(DEMO, ein)
        run([ROOT / "scripts/run.py", "--input", ein, "--output", eout])
        rj = json.loads((eout / "result.json").read_text(encoding="utf-8"))
        assert rj["status"] == "success" and rj["metrics"]["pass"] is True, rj
        assert (eout / "audit.json").exists() and (eout / "repro.json").exists(), "产物缺失"
        ok.append("平台入口：case.json→result.json，status=success、参数 4 条全溯源、九项/步骤/限制均 1.00")

        # limitations 置空：必须 limitation_missing + rate=None + pass=False（旧版记 0.0 却 pass=true）
        m = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
        m.pop("limitations", None)
        mp = tmp / "nolimit.json"
        mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        check(mp, DEMO / "steps.json", eout / "params.csv", tmp / "nolimit")
        nl = json.loads((tmp / "nolimit/repro.json").read_text(encoding="utf-8"))
        assert nl["rates"]["limitation_specificity"] is None, nl["rates"]
        assert {"limitation_missing"} <= {v["type"] for v in nl["violations"]}, nl["violations"]
        assert nl["pass"] is False and "limitation_specificity" in nl["failed_gates"], nl
        ok.append("limitations 为空 → limitation_specificity=None + limitation_missing + pass=False")

        # 裸小数（无单位、无别名）必须被抓；章节编号不算
        t = (DEMO / "methods.md").read_text(encoding="utf-8").replace(
            "权重衰减为 0.01", "权重衰减为 0.01，dropout 设为 0.85")
        dp = tmp / "bare.md"
        dp.write_text(t, encoding="utf-8")
        align(dp, tmp / "bare")
        ba = json.loads((tmp / "bare/audit.json").read_text(encoding="utf-8"))
        assert any("0.85" in v["detail"] for v in ba["violations"]), ba["violations"]
        assert ba["pass"] is False, "裸小数未卡 pass"
        assert not any("3." in v["detail"] for v in ba["violations"]), "章节编号被误判"
        ok.append("裸小数 0.85 被捕获、章节编号 3.1–3.4 不误判")

        # 英文单位 + 裸整数必须抓（旧版 UNIT 只认中文单位、只抓 \d+.\d+，200 epochs / 3 blocks 漏网）
        t = (DEMO / "methods.md").read_text(encoding="utf-8") + "\n\n## 3.5 补充\n\n训练共 200 epochs，使用 128 channels 与 3 blocks。\n"
        dp = tmp / "enunit.md"
        dp.write_text(t, encoding="utf-8")
        align(dp, tmp / "enunit")
        eu = json.loads((tmp / "enunit/audit.json").read_text(encoding="utf-8"))
        det = " ".join(v["detail"] for v in eu["violations"])
        assert "200 epochs" in det and "128 channels" in det and "3 blocks" in det, eu["violations"]
        assert eu["pass"] is False, "英文单位无源数值未卡 pass"
        assert not any("3." in v["detail"] for v in eu["violations"]), "章节编号被英文单位规则误判"
        ok.append("英文单位裸整数：200 epochs / 128 channels / 3 blocks 全部命中，章节编号不误判")

        # 限制小节里的比较式阈值（"不低于 2 μm"）不溯源；混进同一节的无源实测值（25 °C）仍要抓
        t2 = (DEMO / "methods.md").read_text(encoding="utf-8") + "\n实验环境温度为 25 °C。\n"
        dp2 = tmp / "limnum.md"
        dp2.write_text(t2, encoding="utf-8")
        align(dp2, tmp / "limnum")
        ln = json.loads((tmp / "limnum/audit.json").read_text(encoding="utf-8"))
        assert any("25 °C" in v["detail"] for v in ln["violations"]), ln["violations"]
        assert not any("2 μm" in v["detail"] for v in ln["violations"]), "限制阈值被当成无源参数"
        ok.append("限制小节：比较式阈值 2 μm 不溯源，同节无源实测值 25 °C 仍被捕获")

        # 套话限制（只含关键词、无任何数值阈值）必须判 vague，不许拿 1.00
        m = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
        m["limitations"] = ["方法在数据规模变化时可能失效"]
        mp = tmp / "vaguelimit.json"
        mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        check(mp, DEMO / "steps.json", eout / "params.csv", tmp / "vaguelimit")
        vl = json.loads((tmp / "vaguelimit/repro.json").read_text(encoding="utf-8"))
        assert vl["rates"]["limitation_specificity"] == 0.0 and vl["vague_limits"], vl["rates"]
        assert vl["pass"] is False and "limitation_specificity" in vl["failed_gates"] and \
            any(v["type"] == "limitation_vague" for v in vl["violations"]), vl
        ok.append("套话限制（含\"规模\"但无数值阈值）→ limitation_specificity=0.0 + limitation_vague + pass=False")

        # SKILL §5 的合法写法"随机种子未固定，结果不可逐位复现"没有数字，但不许被判 vague
        m5 = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
        m5["limitations"] = ["随机种子未固定，结果不可逐位复现"] + m5["limitations"]
        mp5 = tmp / "mechlimit.json"
        mp5.write_text(json.dumps(m5, ensure_ascii=False), encoding="utf-8")
        check(mp5, DEMO / "steps.json", eout / "params.csv", tmp / "mechlimit")
        ml = json.loads((tmp / "mechlimit/repro.json").read_text(encoding="utf-8"))
        assert ml["rates"]["limitation_specificity"] == 1.0 and not ml["vague_limits"], ml["rates"]
        assert ml["pass"] is True, ml["violations"]
        ok.append("SKILL §5 示例限制（无数字但点名失效机制\"不可逐位复现\"）→ 仍判 specific、pass=True")

        # 清单自洽：manifest seed 与 config 矛盾必须报，不许"字段非空就算九项齐"
        m7 = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
        m7["data"]["seed"] = 7
        mp7 = tmp / "seed7.json"
        mp7.write_text(json.dumps(m7, ensure_ascii=False), encoding="utf-8")
        check(mp7, DEMO / "steps.json", eout / "params.csv", tmp / "seed7")
        s7 = json.loads((tmp / "seed7/repro.json").read_text(encoding="utf-8"))
        assert s7["seed_consistency"] is False, s7
        assert any(v["type"] == "manifest_seed_conflict" for v in s7["violations"]), s7["violations"]
        assert s7["pass"] is False, "manifest seed 矛盾仍 pass"
        ok.append("manifest seed=7 vs config seed=42 → manifest_seed_conflict、seed_consistency=False、pass=False")

        # 来源只有 CLI 日志（--lr 0.001 / --batch-size 32 / seed 42 / weight_decay=0.01 / epochs 50）
        cli = tmp / "cli.log"
        cli.write_text("python train.py --lr 0.001 --batch-size 32 seed 42 weight_decay=0.01 epochs 50\n",
                       encoding="utf-8")
        run([ROOT / "scripts/param_align.py", "--draft", DEMO / "methods.md", "--params", DEMO / "params.json",
             "--sources", cli, "--out", tmp / "cli", "--no-fail"])
        ca = json.loads((tmp / "cli/audit.json").read_text(encoding="utf-8"))
        assert ca["pass"] is True and ca["rates"]["sourced_rate"] == 1.0, ca
        assert not ca["violations"], ca["violations"]
        ok.append("来源只含 CLI 写法（--lr / --batch-size / seed / weight_decay= / epochs）→ 4 参数全 sourced、pass=True")

        # 并列句"学习率与批大小分别为 0.001 与 32"：一对一配值，不许把批大小误配成 0.001
        t3 = (DEMO / "methods.md").read_text(encoding="utf-8").replace(
            "学习率为 0.001，批大小为 32", "学习率与批大小分别为 0.001 与 32")
        dp3 = tmp / "parallel.md"
        dp3.write_text(t3, encoding="utf-8")
        align(dp3, tmp / "parallel")
        pa = json.loads((tmp / "parallel/audit.json").read_text(encoding="utf-8"))
        row = next(r for r in pa["rows"] if r["key"] == "batch_size")
        assert row["value"] == "32" and row["status"] == "sourced", row
        assert pa["rates"]["conflicts"] == 0 and pa["pass"] is True, pa["violations"]
        ok.append("并列句 学习率与批大小分别为 0.001 与 32 → batch_size=32 sourced、conflicts=0、pass=True")

        # 正文零参数：sourced_rate 记 None（旧版记 1.0），并报 no_params_declared
        empty = tmp / "empty.md"
        empty.write_text("# 3 方法\n\n我们训练了一个模型，效果不错。\n", encoding="utf-8")
        align(empty, tmp / "empty")
        ea = json.loads((tmp / "empty/audit.json").read_text(encoding="utf-8"))
        assert ea["rates"]["sourced_rate"] is None and ea["pass"] is False, ea
        assert any(v["type"] == "no_params_declared" for v in ea["violations"]), ea["violations"]
        ok.append("零参数声明 → sourced_rate=None + no_params_declared，不再虚报 1.0")

        # 基线对照：Skill pass=True vs 裸 Agent pass=False，九项/步骤/限制差值可复现
        bo = tmp / "base_out"
        run([ROOT / "examples/baseline.py", "--demo", DEMO, "--out", bo])
        r = run([ROOT / "eval/metrics.py", "--out_dir", eout, "--base_dir", bo])
        md = json.loads(r.stdout[:r.stdout.index("| 指标")].strip())
        assert md["skill"]["pass"] is True and md["base"]["pass"] is False and md["pass_gap"], md
        assert md["delta"]["repro_coverage"] and md["delta"]["repro_coverage"] > 0, md["delta"]
        ok.append(f"基线对照：Skill pass vs 基线 fail；九项差值 {md['delta']['repro_coverage']:+.4f}、"
                  f"步骤 {md['delta']['step_completeness']:+.4f}、限制 {md['delta']['limitation_specificity']:+.4f}")

        # 缺 audit/repro 时 metrics 不崩，记 None
        eb = tmp / "empty_dir"; eb.mkdir()
        r = run([ROOT / "eval/metrics.py", "--out_dir", eout, "--base_dir", eb])
        assert "Traceback" not in r.stderr, r.stderr[-300:]
        md2 = json.loads(r.stdout[:r.stdout.index("| 指标")].strip())
        assert md2["base"]["sourced_rate"] is None and "audit.json" in md2["base"]["missing"], md2["base"]
        ok.append("缺 audit.json/repro.json 的基线段：记 None 不崩溃")

        print("SELFTEST OK")
        for line in ok:
            print("  ✓", line)
    except AssertionError as e:
        import traceback, os
        if os.environ.get("SELFTEST_TRACE"):
            traceback.print_exc()
        err.append(str(e) or repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if err:
        print("SELFTEST FAIL")
        for e in err:
            print("  ✗", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

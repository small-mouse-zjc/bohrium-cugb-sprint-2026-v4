#!/usr/bin/env python3
"""05 基线：模拟"裸 Agent"——写一段不溯源的方法文字，复现清单缺项、限制写得笼统。

用途：给 eval/metrics.py 提供可复现的 base 目录，证明 Skill 的增益不是自说自话。
这不是可交付稿，只是对照组。

  python examples/baseline.py --demo examples/demo --out base_out
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NAIVE_DRAFT = """# 3 方法与实验

我们使用自建岩心 CT 数据集训练分割网络，按常见比例划分训练集与验证集。
学习率设为 0.002，批大小 16，共训练 80 轮，权重衰减 0.02，随机种子 1234。
在单卡上训练约 1 小时，测试集指标以均值报出。
本方法在多数情况下表现良好，但对极端样本可能不稳定。
"""

NAIVE_MANIFEST = {
    "code_version": "repo@unknown",
    "deps": ["torch", "numpy"],
    "data": {"name": "CUG-CT", "split": "8:1:1"},
    "command": ["python train.py"],
    "limitations": ["方法有一定局限，需谨慎使用"],
}

NAIVE_STEPS = {"steps": [
    {"id": "S1", "name": "读数据", "input": "原始 CT", "operation": "归一化", "output": "张量"},
]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default=str(ROOT / "examples/demo"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    demo, out = Path(a.demo), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "methods.md").write_text(NAIVE_DRAFT, encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(NAIVE_MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "steps.json").write_text(json.dumps(NAIVE_STEPS, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/param_align.py"), "--draft", str(out / "methods.md"),
                    "--params", str(demo / "params.json"), "--sources", str(demo / "config.yaml"),
                    "--out", str(out), "--no-fail"], capture_output=True, text=True, encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/repro_check.py"), "--manifest", str(out / "manifest.json"),
                    "--steps", str(out / "steps.json"), "--params", str(out / "params.csv"),
                    "--out", str(out), "--no-fail"], capture_output=True, text=True, encoding="utf-8")
    au = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    rp = json.loads((out / "repro.json").read_text(encoding="utf-8"))
    print(json.dumps({"out": str(out), "audit_pass": au["pass"], "repro_pass": rp["pass"],
                      "audit_rates": au["rates"], "repro_rates": rp["rates"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

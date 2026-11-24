#!/usr/bin/env python3
"""01 基线：模拟"裸 Agent"——照抄原文当译文、不用术语表、不做数字/引用核验。

用途：给 eval/metrics.py 提供可复现的 base 目录，证明 Skill 的增益不是自说自话。
注意：这不是一个可交付的翻译结果，只是对照组。

  python examples/baseline.py --paras paras.jsonl --gloassary glossary.csv --out base_out
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paras", required=True)
    ap.add_argument("--glossary", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    paras = [json.loads(l) for l in Path(a.paras).read_text(encoding="utf-8").splitlines() if l.strip()]
    bi = {"case_id": "baseline", "source_lang": "en", "target_lang": "zh",
          "note": "基线：整段照抄，未经术语锁定与核验",
          "paragraphs": [{"id": p["id"], "page": p["page"], "section": p["section"],
                          "target": p["text"], "terms": [], "status": "ok", "risk": []} for p in paras]}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bip = out / "bilingual.json"
    bip.write_text(json.dumps(bi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 仍用同一套 qc 度量基线，保证 apples-to-apples
    r = subprocess.run([sys.executable, str(ROOT / "scripts/qc.py"), "--paras", a.paras, "--bi", str(bip),
                        "--glossary", a.glossary, "--out", str(out), "--no-fail"],
                       capture_output=True, text=True, encoding="utf-8")
    qc = json.loads((out / "qc.json").read_text(encoding="utf-8"))
    print(json.dumps({"out": str(out), "qc_pass": qc["pass"], "rates": qc["rates"],
                      "violations": len(qc["violations"]), "qc_rc": r.returncode}, ensure_ascii=False))


if __name__ == "__main__":
    main()

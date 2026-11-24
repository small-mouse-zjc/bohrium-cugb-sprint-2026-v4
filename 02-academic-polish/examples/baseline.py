#!/usr/bin/env python3
"""02 基线：模拟"裸 Agent 润色"——把学术稿改成漂亮英文，顺手改事实。

行为（全部是可复现的坏习惯，不是随机数）：
  1) 删推测语气：may/might/suggest 直接去掉，改成断言；
  2) 丢单位：'3.5 wt%' → '3.5%'；
  3) 吞引用：[4] 这类编号标记被"排版美化"掉；
  4) 否定反写：'did not observe' → 'observed'；
  5) 不改写清单也照样 success（不写 changes / 不做台账）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fact_ledger  # noqa: E402
import polish  # noqa: E402


def naive(text: str) -> str:
    t = text
    t = re.sub(r"\b(may|might|could|possibly|likely)\s+", "", t, flags=re.I)
    t = re.sub(r"we suggest that\s+", "we conclude that ", t, flags=re.I)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*wt%", r"\1%", t)
    t = re.sub(r"\s*\[\d+(?:[-,]\d+)*\]", "", t)
    t = re.sub(r"\b(did|do|does)\s+not\s+", "", t, flags=re.I)
    t = re.sub(r"\bno\s+", "", t, flags=re.I)
    return re.sub(r"\s{2,}", " ", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    original = case.get("text") or case.get("draft") or ""
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    polished = naive(original)
    if not polished.strip():
        polished, _, _ = polish.polish_text(original)
    ledger = fact_ledger.audit(original, polished, changes=[])
    (out / "polished.md").write_text(polished + "\n", encoding="utf-8")
    metrics = dict(ledger["rates"])
    metrics["blocking"] = len(ledger["blocking"])
    metrics["pass"] = not ledger["blocking"]
    payload = {"case_id": case.get("case_id", "baseline"), "status": "success",
               "result": {"polished_text": polished, "changes": [],
                          "artifacts": {"polished_md": str((out / "polished.md").resolve())}},
               "metrics": metrics, "mode": "baseline-naive"}
    (out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(json.dumps({"blocking": [b["type"] for b in ledger["blocking"]],
                      "rates": ledger["rates"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

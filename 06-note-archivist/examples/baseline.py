#!/usr/bin/env python3
"""06 基线：模拟"裸 Agent 写读书笔记"的典型输出，用来算真实差值。

基线行为（都取自常见失败模式，不是我的答案）：
1. 套通用模板四节（Introduction/Methods/Results/Conclusion），原文小节数/名称一概不顾；
2. 笔记是压缩复述，不是原文句，所以没有任何偏移；
3. 锚点写"全文"或"p.1"，回查不了；
4. 卡片硬填，缺 limitations；补上原文没有的"3 次重复""n=30"。
"""
import argparse
import json
import os

TEMPLATE_SECTIONS = ["Introduction", "Methods", "Results", "Conclusion"]
CARD = {
    "problem": "研究 CO2 对水合物储层相态的影响。",
    "data": "共 30 个样品，重复 3 次。",
    "method": "高压反应釜实验加数值模拟。",
    "findings": "CO2 注入显著改变了水合物相态。",
    "limitations": "",
    "premises": "",
}


def build(case_id, outdir):
    notes = [{"note_id": f"B{i+1}", "section": s, "quote": f"{s} 部分的主要内容（复述，非原文）。",
              "anchor": "全文"} for i, s in enumerate(TEMPLATE_SECTIONS)]
    res = {
        "case_id": case_id,
        "status": "success",
        "result": {
            "structured_notes": "\n\n".join(f"{s}：复述该节主要内容，未保留原文句。" for s in TEMPLATE_SECTIONS),
            "notes": notes,
            "section_alignment": [{"section": s, "notes": "复述", "anchor": "全文"} for s in TEMPLATE_SECTIONS],
            "reading_card": dict(CARD),
            "card_support": {},
            "anchor_verification": [{"note_id": n["note_id"], "anchor": n["anchor"], "verified": True} for n in notes],
            "artifacts": {},
        },
        "evidence": [], "uncertainty": [],
    }
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="examples/demo/case.json")
    ap.add_argument("--out", default="examples/expected/baseline")
    args = ap.parse_args()
    case_id = "demo-note-01"
    if os.path.isfile(args.case):
        with open(args.case, "r", encoding="utf-8") as f:
            case_id = json.load(f).get("case_id", case_id)
    build(case_id, args.out)
    print(f"baseline written to {args.out}")


if __name__ == "__main__":
    main()

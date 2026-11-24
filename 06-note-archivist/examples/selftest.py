#!/usr/bin/env python3
"""06 自检：正例 + 缺陷注入（N01–N12）+ 降级 + 基线差值 + 空集。

跑法：python examples/selftest.py    （RC=0 表示全部通过）
"""
import copy
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import audit as auditlib   # noqa: E402
import card as cardlib     # noqa: E402
import extract             # noqa: E402
import notes as noteslib   # noqa: E402
import run as runlib       # noqa: E402

ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append(name + (f" | {detail}" if detail and not cond else ""))


def load_demo():
    with open(os.path.join(HERE, "demo", "case.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def pipeline(case):
    doc = extract.build_doc(case)
    ns, _w = noteslib.build_notes(doc, per_section=case.get("note_budget", 3))
    card, support, _gaps = cardlib.build_card(ns)
    res = {"case_id": case.get("case_id", "c"), "status": "success",
           "result": {"structured_notes": runlib.render_notes(doc, ns), "notes": ns,
                      "section_alignment": noteslib.render_sections(doc, ns),
                      "reading_card": card, "card_support": support}}
    return res, doc


def codes(rep):
    return [b.get("code") for b in rep["blocking"]]


def main():
    demo = load_demo()
    base_res, base_doc = pipeline(demo)
    base_rep = auditlib.audit(base_res, base_doc)
    check("正例：6 节全部有原文句笔记，锚点/卡片/数字五率均为 1.0", base_rep["pass"]
          and all(base_rep["rates"][k] == 1.0 for k in
                  ["anchor_resolvability_rate", "section_coverage_rate", "verbatim_support_rate",
                   "card_support_rate", "number_sourced_rate"]), json.dumps(base_rep["rates"]))
    check("正例：阅读卡片六字段都有 support，且 premises 来自 Methods 的 assume 句",
          all(base_res["result"]["card_support"][f] for f in cardlib.FIELDS)
          and base_res["result"]["reading_card"]["premises"].startswith("We assume"),
          base_res["result"]["reading_card"]["premises"][:40])

    # N01
    r = copy.deepcopy(base_res); r["result"]["structured_notes"] = "太短"
    check("N01 笔记过短 → notes_too_short", "N01" in codes(auditlib.audit(r, base_doc)))
    # N02
    r = copy.deepcopy(base_res); r["result"]["section_alignment"] = r["result"]["section_alignment"][:4]
    check("N02 小节数 6→4 → section_count", "N02" in codes(auditlib.audit(r, base_doc)))
    # N03
    r = copy.deepcopy(base_res); r["result"]["section_alignment"][0]["section"] = "Related Work"
    check("N03 自造小节名 → section_not_in_source", "N03" in codes(auditlib.audit(r, base_doc)))
    # N04
    r = copy.deepcopy(base_res); r["result"]["section_alignment"][2]["notes"] = ""
    check("N04 某节无笔记 → section_notes_empty", "N04" in codes(auditlib.audit(r, base_doc)))
    # N05
    r = copy.deepcopy(base_res); r["result"]["section_alignment"][1]["anchor"] = ""
    check("N05 某节无锚点 → section_anchor_empty", "N05" in codes(auditlib.audit(r, base_doc)))
    # N06
    r = copy.deepcopy(base_res); r["result"]["reading_card"]["limitations"] = ""
    check("N06 卡片字段空 → card_field_empty", "N06" in codes(auditlib.audit(r, base_doc)))
    # N07
    r = copy.deepcopy(base_res); del r["result"]["notes"][0]["span"]
    check("N07 笔记没有 span → anchor_unresolvable", "N07" in codes(auditlib.audit(r, base_doc)))
    # N08 span 偏移错（引文确实在原文，但偏移对不上）
    r = copy.deepcopy(base_res); r["result"]["notes"][0]["span"][0] += 1
    rep = auditlib.audit(r, base_doc)
    check("N08 偏移错一位 → anchor_section_mismatch(span_offset_wrong)", "N08" in codes(rep))
    # N08b 小节归属错
    r = copy.deepcopy(base_res)
    n = r["result"]["notes"][0]
    other = next(s for s in base_doc["sections"] if s["index"] != n["section_index"])
    n["section_index"] = other["index"]
    check("N08b 引文放进别的小节 → anchor_section_mismatch", "N08" in codes(auditlib.audit(r, base_doc)))
    # N10 复述句
    r = copy.deepcopy(base_res); r["result"]["notes"][1]["quote"] = "本节讨论了实验条件与样品来源。"
    r["result"]["notes"][1]["span"] = [0, len("本节讨论了实验条件与样品来源。")]
    check("N10 复述句（原文没有）→ note_not_verbatim", "N10" in codes(auditlib.audit(r, base_doc)))
    # N11 卡片无支撑
    r = copy.deepcopy(base_res); r["result"]["card_support"]["findings"] = []
    check("N11 卡片字段无 support → card_field_unsupported", "N11" in codes(auditlib.audit(r, base_doc)))
    # N11b support 指向不存在的 note_id
    r = copy.deepcopy(base_res); r["result"]["card_support"]["method"] = ["S9-X"]
    check("N11b support 指向不存在的 note_id → card_support_unknown_id",
          "N11b" in codes(auditlib.audit(r, base_doc)))
    # N11c 卡片值不是原文句
    r = copy.deepcopy(base_res); r["result"]["reading_card"]["findings"] = "CO2 让相态变了很多。"
    check("N11c 卡片值非原文 → card_value_not_verbatim", "N11c" in codes(auditlib.audit(r, base_doc)))
    # N12 有节没笔记
    r = copy.deepcopy(base_res)
    r["result"]["notes"] = [x for x in r["result"]["notes"] if x["section_index"] != 5]
    r["result"]["section_alignment"][5].update({"notes": "", "anchor": ""})
    check("N12 末节零笔记 → section_without_note", "N12" in codes(auditlib.audit(r, base_doc)))

    # 无标题全文：单节降级
    prose = ("Gas hydrate stability depends on pressure and temperature. " * 6 +
             "We measured 25 g samples at 12 MPa in a high pressure cell. " * 4 +
             "A limitation is that only 3 cores were tested and spatial variability cannot be assessed. ")
    doc_prose = extract.build_doc({"case_id": "p1", "text": prose})
    res_prose, _ = pipeline({"case_id": "p1", "text": prose})
    rep_prose = auditlib.audit(res_prose, doc_prose)
    check("无标题全文：识别为单节 + 记 heading 警告，不崩", len(doc_prose["sections"]) == 1
          and any(w["issue"] == "no_section_headings" for w in doc_prose["warnings"]) and rep_prose["pass"])

    # 太短 → cannot_determine / 缺 case.json → rejected
    res_short, _, _ = runlib.build(None, tempfile.mkdtemp(prefix="note06_none_"))
    check("缺 case.json → rejected，且说明试过的路径", res_short["status"] == "rejected"
          and res_short["uncertainty"][0]["issue"] == "case.json_not_found")
    tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    tf.write(json.dumps({"case_id": "tiny", "text": "too short"})); tf.close()
    res_tiny, _, doc_tiny = runlib.build(tf.name, tempfile.mkdtemp(prefix="note06_tiny_"))
    os.unlink(tf.name)
    check("正文过短 → cannot_determine", res_tiny["status"] == "cannot_determine")

    # 空集：notes 为空时比率记 None
    empty_rep = auditlib.audit({"result": {"structured_notes": "x" * 200, "notes": [],
                                           "section_alignment": [], "reading_card": {}}}, base_doc)
    check("空集：notes=0 时比率记 None 不崩，且报 N12", empty_rep["rates"]["anchor_resolvability_rate"] is None
          and "N12" in codes(empty_rep))

    # 基线差值
    sys.path.insert(0, HERE)
    import baseline  # noqa: E402
    tmp = tempfile.mkdtemp(prefix="note06_base_")
    baseline.build("demo-note-01", tmp)
    with open(os.path.join(tmp, "result.json"), "r", encoding="utf-8") as f:
        bres = json.load(f)
    brep = auditlib.audit(bres, base_doc)
    shutil.rmtree(tmp, ignore_errors=True)
    check("基线：阻断含 N02/N03/N06/N07/N09/N11/N12（复述句无 span 由 N07 直接拦下）",
          all(c in codes(brep) for c in ["N02", "N03", "N06", "N07", "N09", "N11", "N12"]),
          str(codes(brep)))
    check("基线：锚点可反查率 0.0、章节覆盖率 0.0（真实结果 1.0/1.0）",
          brep["rates"]["anchor_resolvability_rate"] == 0.0 and brep["rates"]["section_coverage_rate"] == 0.0,
          json.dumps(brep["rates"]))
    check("基线：编造的数字（30、3）被 N09 抓住并列入值表",
          any(b["type"] == "unsourced_numbers" and {"3", "30"} & set(b["values"]) for b in brep["blocking"]),
          json.dumps([b for b in brep["blocking"] if b["type"] == "unsourced_numbers"], ensure_ascii=False))

    for name in ok:
        print(f"  ✓ {name}")
    for name in fail:
        print(f"  ✗ {name}")
    print(f"SELFTEST {len(ok)} passed, {len(fail)} failed")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())

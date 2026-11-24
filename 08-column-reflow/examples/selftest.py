#!/usr/bin/env python3
"""08 包自检：用已知真值验证重排；朴素基线必须明显更差；页眉页脚必须剔除。"""
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
        raise AssertionError(f"rc={r.returncode} {' '.join(map(str,args))}\n{r.stderr[-800:]}")
    return r


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_08_"))
    ok, err = [], []
    try:
        run([ROOT / "examples/tools/make_demo.py", "--out", tmp])
        pdf = tmp / "demo.pdf"
        truth = tmp / "truth.json"
        assert pdf.exists(), "演示 PDF 未生成"

        rd = tmp / "reflow"
        run([ROOT / "scripts/reflow.py", "--pdf", pdf, "--out", rd, "--audit"])
        info = json.loads((rd / "reflow.json").read_text(encoding="utf-8"))
        assert info["layout"] == "2-column", info["layout"]
        assert len(info["dropped_headers_footers"]) == 4, "页眉页脚未全部剔除"
        assert not info["suspicious"], f"仍有串栏疑似: {info['suspicious']}"
        m = json.loads(run([ROOT / "eval/measure.py", "--out", rd, "--truth", truth]).stdout)
        assert m["order_match"] is True, f"顺序与真值不一致: {m}"
        assert m["inversions"] == 0, m
        ok.append("双栏重排：与真值逐段一致，0 逆序，0 串栏，页眉页脚 4 条全剔除")

        bd = tmp / "base"
        run([ROOT / "scripts/reflow.py", "--pdf", pdf, "--out", bd, "--baseline"])
        mb = json.loads(run([ROOT / "eval/measure.py", "--out", bd, "--truth", truth]).stdout)
        assert mb["order_match"] is False and mb["inversions"] >= 10, mb
        ok.append(f"朴素基线：位置命中 {mb['exact_position_rate']:.0%}、逆序 {mb['inversions']} 处、相邻错位 {mb['adjacent_errors']} 处（对照，不是分数）")

        # 平台入口：case.json → result.json（有真值时必须逐段一致才 success）
        ein = tmp / "entry_in"
        ein.mkdir()
        shutil.copy(pdf, ein / "demo.pdf")
        shutil.copy(truth, ein / "truth.json")
        (ein / "case.json").write_text(json.dumps({"case_id": "demo-reflow-01", "pdf": "demo.pdf",
                                                   "truth": "truth.json"}, ensure_ascii=False), encoding="utf-8")
        eout = tmp / "entry_out"
        run([ROOT / "scripts/run.py", "--input", ein, "--output", eout])
        rj = json.loads((eout / "result.json").read_text(encoding="utf-8"))
        assert rj["status"] == "success" and rj["metrics"]["pass"] is True, rj
        assert rj["metrics"]["order_match"] is True and rj["metrics"]["inversions"] == 0, rj["metrics"]
        assert (eout / "measure.json").exists(), "measure.json 未落盘"
        ok.append("平台入口：case.json→result.json，status=success、顺序一致、0 逆序")

        # 没有真值：只能交重排结果，status=partial，不许冒充成功
        nd = tmp / "entry_notruth"
        nd.mkdir()
        shutil.copy(pdf, nd / "demo.pdf")
        (nd / "case.json").write_text(json.dumps({"case_id": "no-truth", "pdf": "demo.pdf"}, ensure_ascii=False),
                                      encoding="utf-8")
        run([ROOT / "scripts/run.py", "--input", nd, "--output", tmp / "notruth_out"], rc=(0, 1))
        nr = json.loads((tmp / "notruth_out/result.json").read_text(encoding="utf-8"))
        assert nr["status"] == "partial" and nr["metrics"]["order_match"] is None, nr
        ok.append("无真值 → status=partial、order_match=None（不宣称通过）")

        # 缺 PDF：rejected
        bad = tmp / "entry_badpdf"
        bad.mkdir()
        (bad / "case.json").write_text(json.dumps({"case_id": "bad", "pdf": "nope.pdf"}, ensure_ascii=False),
                                       encoding="utf-8")
        run([ROOT / "scripts/run.py", "--input", bad, "--output", tmp / "bad_out"], rc=(2,))
        bj = json.loads((tmp / "bad_out/result.json").read_text(encoding="utf-8"))
        assert bj["status"] == "rejected", bj
        ok.append("缺 PDF → status=rejected")

        # metrics 的基线差值：Skill 全对、基线明显更差
        r = run([ROOT / "eval/metrics.py", "--out_dir", eout, "--truth", truth, "--base_dir", bd])
        md = json.loads(r.stdout[:r.stdout.index("| 指标")].strip())
        assert md["skill"]["pass"] is True and md["base"]["pass"] is False, md
        assert md["delta"]["inversions"] and md["delta"]["inversions"] < 0, md["delta"]
        ok.append(f"基线差值：逆序 {md['base']['inversions']} vs 0、位置命中 {md['base']['exact_position_rate']:.0%} vs 100%")

        # 缺 truth 的对照侧：记 None 不崩
        r = run([ROOT / "eval/metrics.py", "--out_dir", eout, "--truth", tmp / "no_truth.json", "--base_dir", bd],
                rc=(0, 1))
        assert "Traceback" not in r.stderr, r.stderr[-300:]
        ok.append("缺 truth.json：指标记 None 不崩溃")

        # 真实论文形态：每页变化的页码、页边注、跨页断句
        import fitz
        edge = tmp / "edge.pdf"
        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_textbox(fitz.Rect(50, 60, 545, 130),
                          "This paragraph ends without a full stop, so the sentence continues", fontsize=10)
        p1.insert_textbox(fitz.Rect(505, 200, 580, 260), "margin note: see appendix", fontsize=7)
        p1.insert_textbox(fitz.Rect(50, 800, 545, 830), "Page 1 of 2", fontsize=8)
        p2 = doc.new_page(width=595, height=842)
        p2.insert_textbox(fitz.Rect(50, 60, 545, 130),
                          "on the next page and only then ends here.", fontsize=10)
        p2.insert_textbox(fitz.Rect(50, 800, 545, 830), "Page 2 of 2", fontsize=8)
        doc.save(str(edge))
        doc.close()

        ed = tmp / "edge_out"
        run([ROOT / "scripts/reflow.py", "--pdf", edge, "--out", ed, "--audit"])
        eo = json.loads((ed / "reflow.json").read_text(encoding="utf-8"))
        rows = [json.loads(l) for l in (ed / "paragraphs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(eo["dropped_headers_footers"]) == 2, eo["dropped_headers_footers"]
        assert all(d.get("reason") == "页码形态" for d in eo["dropped_headers_footers"]), eo["dropped_headers_footers"]
        assert not any(r["text"].startswith("Page ") for r in rows), [r["text"] for r in rows]
        ok.append("每页变化的页码（Page 1 of 2 / Page 2 of 2）→ 2 条按页码形态剔除，正文零泄漏")

        assert any(r.get("role") == "note" for r in rows), rows
        assert eo["note_blocks"] and eo["note_blocks"][0]["text"].startswith("margin note"), eo["note_blocks"]
        note_rows = [r for r in rows if r.get("role") == "note"]
        assert all(r["col"] == "note" for r in note_rows), note_rows
        ok.append("页边窄块 → role=note、col=note，进 note_blocks，不混入正文序列")

        cont = [r for r in rows if r.get("continues_from")]
        assert cont and eo["continues"], eo["continues"]
        prev = next(r for r in rows if r["id"] == cont[0]["continues_from"])
        assert prev["page"] == cont[0]["page"] - 1, (prev, cont[0])
        ok.append(f"跨页断句 → {cont[0]['id']} 记 continues_from={cont[0]['continues_from']}（上页末段）")

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

#!/usr/bin/env python3
"""09 包自检：5 条断言全原子/逐字/来源完整且 TriG 回解析一致；四类缺陷必须命中。"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
DEMO = ROOT / "examples/demo"


def run(args, rc=(0, 1)):
    r = subprocess.run([PY] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode not in rc:
        raise AssertionError(f"rc={r.returncode} {' '.join(map(str,args))}\n{r.stderr[-600:]}")
    return r


def main():
    tmp = Path(tempfile.mkdtemp(prefix="v3_09_"))
    ok, err = [], []
    base = json.loads((DEMO / "assertions.json").read_text(encoding="utf-8"))
    try:
        run([ROOT / "scripts/nanopub.py", "build", "--assertions", DEMO / "assertions.json",
             "--sources", DEMO / "sources.json", "--out", tmp])
        v = json.loads((tmp / "validation.json").read_text(encoding="utf-8"))
        assert v["pass"], v["violations"]
        assert v["rates"]["export_roundtrip"], "TriG 回解析失败"
        assert (tmp / "nanopub.trig").exists() and (tmp / "nanopub.jsonld").exists()
        ok.append("正例：5 条断言原子/逐字/来源完整，JSON-LD + TriG 导出且回解析一致")

        cases = [
            ("D1_non_atomic", "N01", lambda d: d["assertions"][0].__setitem__(
                "text", "Gas hydrate occurs in marine sediment at site CUG-3, and pore-water salinity is 3.5 wt%.")),
            ("D2_paraphrase", "N02", lambda d: d["assertions"][2]["evidence"].__setitem__(
                "quote", "dissociation pressure rises with salinity")),
            ("D3_missing_para", "N05", lambda d: d["assertions"][4]["evidence"].__setitem__("paragraph_id", None)),
            ("D4_duplicate", "N07", lambda d: d["assertions"].append(dict(d["assertions"][0], id="A6"))),
        ]
        for name, code, mutate in cases:
            d = json.loads(json.dumps(base))
            mutate(d)
            ap = tmp / f"{name}.json"
            ap.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            od = tmp / name
            run([ROOT / "scripts/nanopub.py", "build", "--assertions", ap, "--sources", DEMO / "sources.json",
                 "--out", od, "--no-fail"])
            vv = json.loads((od / "validation.json").read_text(encoding="utf-8"))
            codes = {x["code"] for x in vv["violations"]}
            assert code in codes, f"{name} 未命中 {code}，实际 {sorted(codes)}"
            ok.append(f"{name} → {code}")

        # 平台入口：case.json → /app/output/result.json
        ein = tmp / "entry_in"
        ein.mkdir()
        for f in ("assertions.json", "sources.json"):
            shutil.copy(DEMO / f, ein / f)
        (ein / "case.json").write_text(json.dumps({"case_id": "selftest-09", "assertions": "assertions.json",
                                                   "sources": "sources.json"}, ensure_ascii=False), encoding="utf-8")
        eo = tmp / "entry_out"
        run([ROOT / "scripts/run.py", "--input", ein, "--output", eo])
        rj = json.loads((eo / "result.json").read_text(encoding="utf-8"))
        assert rj["case_id"] == "selftest-09" and rj["status"] == "success", rj
        assert "nanopub.trig" in rj["artifacts"], rj["artifacts"]
        ok.append(f"平台入口：case.json→result.json，status={rj['status']}，assertions={rj['metrics']['assertions']}")

        # 零断言：比率必须 null，不能记 1.00，且报 N00
        z = json.loads(json.dumps(base))
        z["assertions"] = []
        zp = tmp / "zero.json"
        zp.write_text(json.dumps(z, ensure_ascii=False), encoding="utf-8")
        zo = tmp / "zero"
        run([ROOT / "scripts/nanopub.py", "build", "--assertions", zp, "--sources", DEMO / "sources.json",
             "--out", zo, "--no-fail"], rc=(0, 1))
        zv = json.loads((zo / "validation.json").read_text(encoding="utf-8"))
        assert zv["rates"]["atomic_rate"] is None, zv["rates"]
        assert "N00" in {x["code"] for x in zv["violations"]}, zv["violations"]
        assert zv["pass"] is False, "零断言被判通过"
        ok.append("零断言：三比率=None + N00，不再虚报 1.00")

        # N04 必须拉低逐字率（以前三个比率对着违规清单仍全绿）
        d4 = json.loads(json.dumps(base))
        d4["assertions"][0]["subject"]["label"] = "zzq alpha absent"
        d4["assertions"][0]["object"]["label"] = "zzq beta absent"
        d4p = tmp / "n04.json"
        d4p.write_text(json.dumps(d4, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/nanopub.py", "build", "--assertions", d4p, "--sources", DEMO / "sources.json",
             "--out", tmp / "n04", "--no-fail"], rc=(0, 1))
        v4 = json.loads((tmp / "n04" / "validation.json").read_text(encoding="utf-8"))
        assert v4["rates"]["verbatim_rate"] < 1.0, v4["rates"]
        assert "N04" in {x["code"] for x in v4["violations"]}, v4["violations"]
        ok.append(f"N04 拉低逐字率：verbatim_rate={v4['rates']['verbatim_rate']}")

        # TriG 的 DOI IRI 不能出现 urn:doi:urn:doi 双前缀
        trig = (eo / "nanopub.trig").read_text(encoding="utf-8")
        assert "urn:doi:urn:doi" not in trig, "DOI 双前缀畸形 IRI 仍在"
        assert "wasDerivedFrom <" in trig, "provenance 未写成 IRI"
        ok.append("TriG：DOI 统一为单一 IRI（无 urn:doi:urn:doi）")

        # 基线对照：裸 Agent 只有 raw JSON，没有校验
        base_out = tmp / "base"
        run([ROOT / "examples/baseline.py", "--assertions", DEMO / "assertions.json", "--out", base_out])
        import importlib.util
        spec = importlib.util.spec_from_file_location("m09", ROOT / "eval/metrics.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        sb, ss = mod.load(base_out), mod.load(eo)
        assert sb["atomic_rate"] is None and sb["pass"] is False, sb
        assert ss["pass"] is True and ss["export_roundtrip"] is True, ss
        ok.append("基线对照：裸 Agent 率=None/pass=False vs Skill pass=True/roundtrip=True")

        # 9) JSON-LD 与 TriG 的 DOI 必须同一 IRI（纯 DOI 时两边都是 https://doi.org/...）
        sys.path.insert(0, str(ROOT / "scripts"))
        import nanopub as npb
        d5 = json.loads(json.dumps(base))
        src5 = json.loads((DEMO / "sources.json").read_text(encoding="utf-8"))
        src5["sources"][0]["doi"] = "10.1234/foo.2026"
        p5 = {"title": src5["sources"][0].get("title"), "year": src5["sources"][0].get("year"),
              "doi": src5["sources"][0]["doi"]}
        as5, _ = npb.build(d5["assertions"], src5["sources"], p5)
        jl = npb.export_jsonld(as5, p5, "demo-09")
        tg = npb.export_trig(as5, p5, "demo-09")
        jl_doi = next(g for g in jl["@graph"] if g.get("@type") == "np:Provenance")["prov:wasDerivedFrom"]["@id"]
        tg_doi = re.search(r"prov:wasDerivedFrom <([^>]+)>", tg).group(1)
        assert jl_doi == tg_doi == "https://doi.org/10.1234/foo.2026", (jl_doi, tg_doi)
        assert "urn:doi:urn:doi" not in tg, tg[:200]
        ok.append("JSON-LD 与 TriG 的 DOI 同一 IRI：都是 https://doi.org/10.1234/foo.2026")

        # 10) TriG 的主/客体/关系是 IRI 节点，不是裸字面量
        assert "rel:subject <https://example.org/np/" in tg, tg[:400]
        assert "rel:relation <https://example.org/rel/" in tg, tg[:400]
        assert 'rel:subject "' not in tg and 'rel:relation "' not in tg, "TriG 仍有字面量主客体"
        ok.append("TriG 主语/关系为 IRI 节点（无裸字面量）")

        # 11) 真解析：坏 TriG 必须解析失败（旧的计数法在这些输入上是 ok=True）
        import trig as triglib
        good = tg
        assert npb.reparse(good, len(as5))["ok"], npb.reparse(good, len(as5))
        bads = {
            "括号不闭合": good[: good.rfind("}")] + "\n",
            "字面量未转义引号": good.replace('rel:text "', 'rel:text "bad"quote', 1),
            "三元组缺 .": good.replace(" .\n", " ;\n", 1),
            "谓语位置裸写": good.replace("a np:Assertion", "np:Assertion", 1),
        }
        for name, bad in bads.items():
            r = npb.reparse(bad, len(as5))
            assert r["ok"] is False and r.get("error"), (name, r)
        ok.append("真解析：坏 TriG（括号/引号/缺./裸谓语）四种全部解析失败并给出行号")

        # 12) 序列化对齐：正确导出 JSON-LD/TriG 逐字段一致，改坏一处必报 N09
        parsed_good = triglib.parse(good)
        ser_ok = npb.compare_serializations(jl, parsed_good, as5, "demo-09")
        assert ser_ok["ok"] and ser_ok["consistency_rate"] == 1.0, ser_ok
        ld_broken = json.loads(json.dumps(jl))
        for node in ld_broken["@graph"]:
            if node.get("@type") == "np:Assertion":
                node["rel:relation"] = {"@id": "https://example.org/rel/bogus"}
                break
        ser_bad = npb.compare_serializations(ld_broken, parsed_good, as5, "demo-09")
        assert not ser_bad["ok"] and ser_bad["mismatch"], ser_bad
        ok.append(f"序列化对齐：正确导出 15 项全一致({ser_ok['checked']})，关系 IRI 改坏即 {len(ser_bad['mismatch'])} 处不一致")

        # 13) 基线：无 TriG、无一致性 → 指标为 None
        assert sb.get("export_roundtrip") is None or sb.get("export_roundtrip") is False, sb
        ok.append("基线：不产出 TriG/JSON-LD 对照 → roundtrip 与一致性均不可评（None）")

        # 13b) N10 方向：证据写 increases，关系改成 decreases 必须被拦（旧的只看逐字引文照样过）
        dn = json.loads(json.dumps(base))
        dn["assertions"][2]["relation"] = "decreases"
        dnp = tmp / "n10.json"
        dnp.write_text(json.dumps(dn, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/nanopub.py", "build", "--assertions", dnp, "--sources", DEMO / "sources.json",
             "--out", tmp / "n10", "--no-fail"], rc=(0, 1))
        vn = json.loads((tmp / "n10" / "validation.json").read_text(encoding="utf-8"))
        assert "N10" in {x["code"] for x in vn["violations"]}, vn["violations"]
        assert vn["rates"]["direction_rate"] < 1.0 and vn["pass"] is False, vn["rates"]
        ok.append(f"关系写反（increases→decreases，证据仍是 increases）→ N10、direction_rate={vn['rates']['direction_rate']}")

        # 13c) N11 主客角色：把 A3 的 subject/object 互换（salinity 当主语）必须被拦；证据缺一端也算
        dr = json.loads(json.dumps(base))
        a3 = dr["assertions"][2]
        a3["subject"], a3["object"] = a3["object"], a3["subject"]
        drp = tmp / "n11.json"
        drp.write_text(json.dumps(dr, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/nanopub.py", "build", "--assertions", drp, "--sources", DEMO / "sources.json",
             "--out", tmp / "n11", "--no-fail"], rc=(0, 1))
        vr = json.loads((tmp / "n11" / "validation.json").read_text(encoding="utf-8"))
        assert "N11" in {x["code"] for x in vr["violations"]}, vr["violations"]
        assert vr["rates"]["role_rate"] == 0.8 and vr["pass"] is False, vr["rates"]
        dr2 = json.loads(json.dumps(base))
        dr2["assertions"][3]["object"]["label"] = "zzq absent endpoint"
        dr2p = tmp / "n11b.json"
        dr2p.write_text(json.dumps(dr2, ensure_ascii=False), encoding="utf-8")
        run([ROOT / "scripts/nanopub.py", "build", "--assertions", dr2p, "--sources", DEMO / "sources.json",
             "--out", tmp / "n11b", "--no-fail"], rc=(0, 1))
        vr2 = json.loads((tmp / "n11b" / "validation.json").read_text(encoding="utf-8"))
        assert any(x["code"] == "N11" and "客体" in x["detail"] for x in vr2["violations"]), vr2["violations"]
        ok.append(f"主客颠倒（salinity 当主语）→ N11、role_rate={vr['rates']['role_rate']}；证据缺客体表面形式同样报 N11")


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

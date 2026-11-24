#!/usr/bin/env python3
"""参数-来源对齐：正文数值 vs 配置/日志/代码；顺带抓"带单位但全库找不到"的数。

  python param_align.py --draft methods.md --params params.json \
      --sources config.yaml train.log model.py --out out
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

NUM = r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?\d+)?"
UNIT = (r"(?:%|MPa|GPa|kPa|°C|K|s|ms|h|min|GB|MB|TB|轮|层|维|次|个|条|张|幅|μm|um|mm|cm|"
        r"epochs|epoch|iterations|steps|samples|images|channels|blocks|layers|fps|tokens|batches|"
        r"params|cores|threads|hours|minutes|seconds|days|GPUs|GPU)")
EN_UNITS = {"epochs", "epoch", "iterations", "steps", "samples", "images", "channels", "blocks", "layers", "fps",
            "tokens", "batches", "params", "cores", "threads", "hours", "minutes", "seconds", "days", "gpus", "gpu",
            "mb", "gb", "tb", "ms", "min", "h", "s", "k"}
# 数字后紧跟的英文词：不在停用词里就当作单位（epochs/blocks 这类白名单外的写法不再漏网）
UNIT_EN_STOP = {"and", "or", "of", "to", "the", "in", "on", "for", "per", "vs", "at", "is", "are", "by",
                "with", "as", "from", "than", "each", "respectively", "approximately", "about", "over"}


def limitation_spans(text: str):
    """「限制/局限性」小节的字符区间：里面的数值是作者给的失效阈值，不是实验参数。

    这些阈值不与 config/log 对齐（本来就不在配置里），但必须写进 manifest.limitations，
    由 repro_check 的 limitation_specificity 复核，所以这里跳过、不记无源。
    """
    spans = []
    for m in re.finditer(r"(?m)^#{1,6}\s*[^\n]*?(限制|局限)[^\n]*$", text):
        start = m.start()
        nxt = re.search(r"(?m)^#{1,6}\s", text[m.end():])
        end = m.end() + (nxt.start() if nxt else len(text))
        spans.append((start, end))
    return spans


CMP = ("超过", "高于", "低于", "少于", "大于", "小于", "不低于", "不超过", "不少于", "不多于", "±", "约为",
       "≥", "≤", ">", "<")


def in_spans(pos, spans):
    return any(a <= pos < b for a, b in spans)


def threshold_in_limit(text, pos, spans):
    """限制小节里以比较式给出的阈值（"不低于 2 μm"/"超过 0.005"）才免于溯源。

    这样"实验环境温度为 25 °C"这类混进限制小节的无源实测值仍会被抓；
    阈值本身是否写进 manifest.limitations 由 repro_check 的 limitation_specificity 复核。
    """
    if not in_spans(pos, spans):
        return False
    head = text[max(0, pos - 15):pos]
    return any(w in head for w in CMP)


def parse_num(s: str):
    try:
        return float(s)
    except Exception:
        return None


def same(a: str, b: str) -> bool:
    fa, fb = parse_num(a), parse_num(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) <= 1e-12 * max(1.0, abs(fa))
    return a.strip().lower() == b.strip().lower()


KV_RE = re.compile(rf"""["']?([A-Za-z_][A-Za-z0-9_]{{1,30}})["']?\s*(?::|=|,)\s*({NUM})""")
CLI_RE = re.compile(rf"--([A-Za-z_][A-Za-z0-9_-]{{1,30}})[= ]({NUM})")
SPACE_RE = re.compile(rf"\b([A-Za-z_][A-Za-z0-9_]{{1,30}})\s+({NUM})\b")


def index_sources(files):
    """来源索引：YAML/JSON 键值（含引号键、嵌套叶子键）、`--lr 0.001` / `--lr=0.001`、
    空格分隔的 `lr 0.001`（CLI 日志常见写法）都要收，否则值就在文件里却被判无源。"""
    idx = {}
    generic = []
    for f in files:
        p = Path(f)
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            span = f"{p.name}:{i}"
            for rx in (KV_RE, CLI_RE, SPACE_RE):
                for m in rx.finditer(line):
                    idx.setdefault(m.group(1).lower().lstrip("-").replace("-", "_"), []).append((m.group(2), span))
            for m in re.finditer(NUM, line):
                generic.append((m.group(0), span))
    return idx, generic


def parallel_pins(text, params):
    """并列句"学习率与批大小分别为 0.001 与 32"：第 N 个别名配第 N 个数，不都取最近的那个。

    values_in_draft 逐别名向后抓第一个数，在并列句里会把所有别名都配成第一个数（0.001 被当成批大小，
    误报 conflict）。这里先识别并列结构并钉住一对一的映射。
    """
    pins = {}
    for sent in re.split(r"[。\n；;]", text):
        if not re.search(r"分别|各自|依次", sent):
            continue
        m = re.search(r"(?:分别|各自|依次)(?:为|是|取|设|采用)?", sent)
        if not m:
            continue
        left, right = sent[:m.start()], sent[m.end():]
        right = re.split(r"[，,]", right)[0]  # 只取并列项所在的那一小句，后面"共训练 50 轮"不参与配对
        hits = []
        for p in params:
            for al in [p["key"]] + [x for x in p.get("aliases", []) if x]:
                pos = left.lower().find(al.lower())
                if pos >= 0:
                    hits.append((pos, p["key"]))
        keys = [k for _, k in sorted(hits)]
        nums = re.findall(NUM, right)
        if len(keys) >= 2 and len(keys) == len(nums):
            for k, v in zip(keys, nums):
                pins.setdefault(k, v)
    return pins


def values_in_draft(text, alias):
    out = []
    for m in re.finditer(re.escape(alias), text, re.I):
        tail = text[m.end():m.end() + 30]
        n = re.search(NUM, tail)
        if n:
            # 只接受别名后 12 字符内出现的数值，避免跨句误配
            gap = tail[:n.start()]
            if len(gap) <= 12:
                out.append((n.group(0), m.start()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fail", action="store_true")
    a = ap.parse_args()

    text = Path(a.draft).read_text(encoding="utf-8")
    params = json.loads(Path(a.params).read_text(encoding="utf-8"))["params"]
    src_idx, generic = index_sources(a.sources)
    pins = parallel_pins(text, params)

    rows, viol = [], []
    declared_numbers = set()
    for p in params:
        key = p["key"]
        aliases = [key] + [x for x in p.get("aliases", []) if x]
        found = []
        if key in pins:
            found = [(pins[key], text.lower().find(key.lower()))]
        else:
            for al in aliases:
                found += values_in_draft(text, al)
        src_hits = []
        for al in aliases:
            src_hits += src_idx.get(al.lower().replace("-", "_"), [])
        if not found:
            if src_hits:
                viol.append({"type": "param_omitted", "detail": f"来源有 {key}，正文未写", "key": key})
            continue
        for val, _pos in found:
            declared_numbers.add(val)
            if not src_hits:
                rows.append({"key": key, "value": val, "unit": p.get("unit", ""), "source": "",
                             "source_locator": "", "status": "unsourced", "note": "来源里找不到该参数"})
                viol.append({"type": "param_unsourced", "detail": f"{key}={val} 无来源", "key": key})
                continue
            match = next((h for h in src_hits if same(val, h[0])), None)
            if match:
                rows.append({"key": key, "value": val, "unit": p.get("unit", ""), "source": match[1].split(":")[0],
                             "source_locator": match[1], "status": "sourced", "note": ""})
            else:
                rows.append({"key": key, "value": val, "unit": p.get("unit", ""), "source": src_hits[0][1].split(":")[0],
                             "source_locator": src_hits[0][1], "status": "conflict",
                             "note": f"来源值为 {src_hits[0][0]}"})
                viol.append({"type": "param_conflict", "detail": f"{key}: 正文 {val} vs 来源 {src_hits[0][0]}", "key": key})

    # 带单位的数值：全库找不到即视为无源（限制小节里的失效阈值除外，那部分由 repro_check 复核）
    lim_spans = limitation_spans(text)
    for m in re.finditer(rf"({NUM})\s*{UNIT}", text):
        val = m.group(1)
        if val in declared_numbers:
            continue
        if threshold_in_limit(text, m.start(), lim_spans):
            continue
        if not any(same(val, g[0]) for g in generic):
            viol.append({"type": "unsourced_number", "detail": f"带单位数值 {m.group(0)} 在全部来源里找不到",
                         "span": [m.start(), m.end()]})

    # 白名单外的英文单位（200 epochs / 3 blocks）：数字 + 空格 + 英文词，词不在停用表里就按"带单位数值"核
    for m in re.finditer(rf"(?<![A-Za-z0-9_.])({NUM})\s+([A-Za-zμ][A-Za-zμ]{{1,14}})", text):
        val, word = m.group(1), m.group(2)
        if word.lower() in UNIT_EN_STOP:
            continue
        if re.fullmatch(UNIT, word):
            continue  # 已在上面白名单那句核过，不重复报
        if val in declared_numbers:
            continue
        if threshold_in_limit(text, m.start(), lim_spans):
            continue
        if not any(same(val, g[0]) for g in generic):
            viol.append({"type": "unsourced_number",
                         "detail": f"英文单位数值 {m.group(0)}（{word}）在全部来源里找不到",
                         "span": [m.start(), m.end()]})

    # 裸小数（如 dropout 0.7）：不带单位也不在前述参数别名里，仍是可复现性漏洞；阈值类句子除外
    for m in re.finditer(r"(?<![A-Za-z0-9.])(\d+\.\d+)(?![0-9])", text):
        val = m.group(1)
        if val in declared_numbers:
            continue
        head = text[max(0, m.start() - 8):m.start()]
        line_head = text[text.rfind("\n", 0, m.start()) + 1:m.start()]
        if re.fullmatch(r"[#*\s>-]*", line_head):
            continue  # 行首的 3.1 / 3.2 是章节编号，不是参数
        if any(w in head for w in CMP):
            continue
        if any(same(val, g[0]) for g in generic):
            continue
        viol.append({"type": "unsourced_number", "detail": f"裸小数 {val} 未在任何来源出现，也无参数别名绑定",
                     "span": [m.start(), m.end()]})

    n_src = sum(1 for r in rows if r["status"] == "sourced")
    rates = {
        "declared_params": len({r["key"] for r in rows}),
        "sourced_rate": round(n_src / len(rows), 4) if rows else None,
        "unsourced": sum(1 for r in rows if r["status"] == "unsourced") + sum(1 for v in viol if v["type"] == "unsourced_number"),
        "conflicts": sum(1 for r in rows if r["status"] == "conflict"),
    }
    if not rows:
        viol.append({"type": "no_params_declared", "detail": "正文没有声明任何可溯源参数，无法证明可复现"})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "params.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["key", "value", "unit", "source", "source_locator", "status", "note"])
        w.writeheader()
        w.writerows(rows)
    audit = {"rates": rates, "rows": rows, "violations": viol,
             "pass": bool(rows) and rates["unsourced"] == 0 and rates["conflicts"] == 0
                     and not any(v["type"] == "param_omitted" for v in viol)}
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pass": audit["pass"], **rates, "violations": len(viol)}, ensure_ascii=False))
    if not a.no_fail and not audit["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


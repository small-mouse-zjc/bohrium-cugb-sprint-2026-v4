#!/usr/bin/env python3
"""02 最小编辑引擎：只做安全替换，不碰数字、引用、限定词、否定。

平台没有 LLM 时，run.py 用它产出"保源润色"；有 LLM 稿时用它做对照。
每条替换都在句级产出 change（original → revised），便于逐条审计。
"""
from __future__ import annotations

import re

# 只允许"删冗余/固定搭配/口语化"三类替换，全部不改变事实
RULES = [
    (re.compile(r"\bin order to\b", re.I), "to", "固定搭配精简"),
    (re.compile(r"\bdue to the fact that\b", re.I), "because", "冗余从句精简"),
    (re.compile(r"\bit (?:can|may) be seen that\b", re.I), "", "删空壳引导句"),
    (re.compile(r"\ba lot of\b", re.I), "many", "口语化措辞替换"),
    (re.compile(r"\blots of\b", re.I), "many", "口语化措辞替换"),
    (re.compile(r"\bis able to\b", re.I), "can", "口语化措辞替换"),
    (re.compile(r"\bare able to\b", re.I), "can", "口语化措辞替换"),
    (re.compile(r"\bmaybe can\b", re.I), "may", "情态动词合并（保留推测语气）"),
    (re.compile(r"\bmaybe\b", re.I), "possibly", "口语化措辞替换（保留推测语气）"),
    (re.compile(r"\butilize[sd]?\b", re.I), "use", "过度正式用词替换"),
    (re.compile(r"\bvery\s+", re.I), "", "删空泛程度副词"),
    (re.compile(r"\bthe the\b", re.I), "the", "重复词修正"),
]

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _tidy(s: str) -> str:
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    return s.strip()


def polish_sentence(sentence: str) -> tuple:
    """返回 (revised, reasons)。无改动则 reasons 为空。"""
    out, reasons = sentence, []
    for pat, rep, why in RULES:
        new = pat.sub(rep, out)
        if new != out:
            reasons.append(why)
            out = new
    out = _tidy(out)
    if out and sentence and sentence[0].isupper() and out[0].islower():
        out = out[0].upper() + out[1:]
    return out, sorted(set(reasons))


def polish_text(text: str) -> tuple:
    """句级润色，返回 (polished_text, changes, unchanged_sentences)。"""
    text = (text or "").strip()
    sentences = [s for s in SENT_SPLIT.split(text) if s.strip()]
    revised, changes, unchanged = [], [], []
    for s in sentences:
        r, why = polish_sentence(s)
        if r != s.strip() and why:
            changes.append({"original": s.strip(), "revised": r, "reason": "; ".join(why),
                            "fact_changed": False})
        else:
            unchanged.append(s.strip())
        revised.append(r)
    polished = " ".join(revised)
    return polished, changes, unchanged


if __name__ == "__main__":
    import json
    import sys

    src = sys.stdin.read() if len(sys.argv) == 1 else open(sys.argv[1], encoding="utf-8").read()
    p, c, u = polish_text(src)
    print(json.dumps({"polished_text": p, "changes": c, "unchanged": len(u)},
                     ensure_ascii=False, indent=2))

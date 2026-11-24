# 输出契约（06 note-archivist）

`/app/output/result.json` 顶层字段：

```json
{
  "case_id": "输入的 case_id（缺失时用文件名/文本回退，不编造）",
  "status": "success | partial | needs_attention | cannot_determine | rejected",
  "result": {
    "structured_notes": "markdown 逐节笔记，每条含 role 与 anchor",
    "notes": [ {
        "note_id": "S<section>-N<k>",
        "section": "小节标题（取自输入/检测）",
        "section_index": 0,
        "role": "problem|data|method|finding|limitation|premise|background",
        "quote": "原文切片",
        "anchor": "§i ¶j [/ p.N] [start-end]",
        "span": [start, end],
        "page": 2,
        "para": 2
    } ],
    "section_alignment": [ {"section", "section_index", "notes", "note_ids", "anchor"} ],
    "reading_card": {"problem","data","method","findings","limitations","premises"},
    "card_support": {"<field>": ["note_id", ...]},
    "anchor_verification": [ {"note_id", "anchor", "verified", "check"} ],
    "artifacts": {"notes_md": "...", "reading_card_json": "..."}
  },
  "evidence": [ {"anchor", "note"} ],
  "uncertainty": [ {"issue", "detail"} ],
  "audit": {"blocking", "advisory", "rates", "pass", "codes"},
  "metrics": {"anchor_resolvability_rate", "section_coverage_rate", "verbatim_support_rate",
              "card_support_rate", "number_sourced_rate", "notes_count", "sections"}
}
```

## status 语义（由产物判定，禁止手写）

| status | 条件 |
|---|---|
| `rejected` | 找不到 / 无法解析 `case.json` |
| `cannot_determine` | 正文 < 50 字符（如只有扫描件路径、空文本） |
| `needs_attention` | 审计有任一阻断码 |
| `partial` | 无阻断，但有 `not_reported` 字段或提示项 |
| `success` | 无阻断、无 `not_reported`、无提示 |

## `not_reported` 规则

- 卡片字段在原文确实没有对应句时写字符串 `not_reported`，并同步写 `uncertainty`；不得用空格、`N/A`、`none` 或自造结论代替。
- `not_reported` 不算空字段（N06 不报），但会让 `status=partial`。

## 不确定性与证据

- `uncertainty` 只写真实缺失/降级：`no_section_headings`、`heading_missing`、`section_without_sentences`、`no_text_layer`、`text_too_short`、`field_not_reported_in_source`、`case_json_not_found`、`case_json_unreadable`。
- `evidence` 每条给 anchor + 原文句（截断 80 字符），与 `notes` 同源。

## 附件

`notes.md`（可读笔记）、`reading_card.json`（卡片 + 支撑）、`section_align.md`（对照表 + 审计结论）。三者均由 `scripts/run.py` 从同一份 `result` 渲染，不得手改。

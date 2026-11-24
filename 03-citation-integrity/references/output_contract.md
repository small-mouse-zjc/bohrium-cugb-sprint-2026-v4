# 输出契约 · 03 引用管理

> `case.json` 自带 `output_contract` / `required_fields` 时以它为准。

## 顶层（必填）

| 字段 | 说明 |
|---|---|
| `case_id` | 与输入一致 |
| `status` | `success` / `partial` / `needs_attention` |
| `result` | 正文、文献表、编号映射、产物 |
| `evidence` | 引用-条目对应定位 |
| `uncertainty` | 缺失来源、元数据不全、未合并项 |

## result

| 字段 | 必填 | 说明 |
|---|---|---|
| `editable_manuscript` | 是 | 可编辑正文，引用标记在原位；空判 partial |
| `bibliography` | 是 | `[{id/key, author, year, title, source, doi?}]` |
| `number_mapping` | 是 | 正文引用 ↔ 文献 key/编号 |
| `claim_source_map` | 否 | 主张 ↔ 来源 |
| `artifacts` | 是 | `manuscript` / `bibliography` 绝对路径，必须存在 |

## 硬规则

- 正文出现的每个编号/key 都能在文献表找到；悬空引用判 error。
- 不编造作者、年份、标题、期刊、DOI；元数据不全进 `uncertainty`。
- 重复条目合并，保留真实元数据。
- `success` 要求：正文与文献表闭环、`guard.py` 无 error。

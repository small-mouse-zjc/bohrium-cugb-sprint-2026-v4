# 输出契约 · 02 学术语言润色

> `case.json` 自带 `output_contract` / `required_fields` 时以它为准。

## 顶层（必填）

| 字段 | 说明 |
|---|---|
| `case_id` | 与输入一致 |
| `status` | `success` / `partial` / `needs_attention` |
| `result` | 润色稿、改动、保留项、产物 |
| `evidence` | 改动定位与依据 |
| `uncertainty` | 拿不准的句子、歧义、未改段落 |

## result

| 字段 | 必填 | 说明 |
|---|---|---|
| `polished_text` | 是 | 完整润色正文；空或过短判 partial |
| `changes` | 是 | `[{original, revised, reason}]`；无改动也要写“原文无需修改” |
| `preserved` | 是 | 数字、引用、限定词、否定、比较级的保留清单 |
| `artifacts` | 是 | `polished_md` / `audit_json` 绝对路径，必须存在 |

## 硬规则

- 最小编辑：不新增事实、数据、引用、结论。
- hedge（may/might/likely）、否定、因果、比较级强度不变。
- 数字、单位、引用编号、图表编号与原文一致。
- `success` 要求：正文完整、`guard.py` 无 error。

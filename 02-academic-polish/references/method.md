# 02 · 事实保留校验方法（可复现说明）

润色本身由 Agent 或最小编辑引擎完成；本文件说明"脚本到底查什么、怎么查、查不了什么"。

## 1. 事实单元抽取（`scripts/facts.py`）

| 单元 | 抽取方式 | 归一化 |
|---|---|---|
| 数字+单位 | `(?<![A-Za-z0-9_.])\d+(\.\d+)?` + 紧随的字母/`%`/`°` 词 | `wt %`→`wt%`、`℃`/`ºc`→`°c`、`weight%`/`pct`→`%`；后接 `to/and/of/in/at/...` 等普通词时不当作单位 |
| 引用 | `[12]`、`[3-5]`、`(Smith et al., 2020)`、`(Smith, 2020)` | 去空格 |
| 限定词 | may/might/could/possibly/likely/suggest/appear/seem/tend to/presumably/arguably/approximately/rather/up to | 按小写词计数 |
| 否定 | not/never/none/neither/nor/cannot/without/lack/fail/unable/hardly/barely/rarely | 按小写词计数 |
| 比较级 | more than/less than/higher than/lower than/increase/decrease/rise/decline/exceed/above/below/twice/fold/rather than/compared with | 按小写词计数 |
| 强断言 | prove/demonstrate/confirm/establish/significant/definitively/clearly/undoubtedly/always/conclusively | 只用于"是否新增" |

## 2. 逐条判定（`scripts/fact_ledger.py`）

每个原始事实单元判一个状态：

| 状态 | 条件 | 是否阻断 |
|---|---|---|
| `kept` | 润色稿里同 token 出现次数 ≥ 原文 | 否 |
| `normalized` | 同数字同单位，只是空格/符号/大小写写法不同 | 否（audit 里记 `as`） |
| `changed` | 数字还在，单位或基准变了（`3.5 wt%`→`3.5%`、MPa→kPa） | 是（F01b `unit_change`） |
| `removed` | 数字或单位整体消失 | 是（F01）。**不做单位换算后放行**：kPa 与 MPa 数值不同即换单位，需人工确认 |
| `added` | 润色稿里出现原文没有的数字 | 是（F11 `number_added`） |

引用同理：丢一条 F02，凭空多一条 F03。限定词数量减少 F04；原文有推测语气而润色稿新增强断言 F05。否定减少 F06，比较方向丢失 F07。

## 3. 句子对齐

- 切句：`(?<=[.!?])\s+`。
- 对齐：每句原文对全部润色句做 `difflib.SequenceMatcher` 取最高相似度。
- 判定：<0.45 判 `sentence_dropped`（F08）；0.45–0.85 记 `sentence_rewritten`（A02，进 `uncertainty`）；润色句对原文最高相似度 <0.6 且不在 `changes.revised` 里判 `unlogged_new_sentence`（F09）。

## 4. 改动清单核验

- `changes.original` 必须能在原文中找到（找不到 A01）。
- `changes.revised` 必须在润色稿里（找不到 A04）。
- 对每条改动抽 `facts.fact_tokens(original)` 与 `facts.fact_tokens(revised)`：集合变了就必须 `fact_changed: true`，否则 F10；声明了却没变记 A05。

## 5. 比率（分母 0 一律 `None`）

- `fact_preservation_rate = (kept + normalized) / (全部原始事实)`；`facts_by_status` 给出五类计数。
- `number_retention` / `citation_retention` / `hedge_retention` / `negation_retention` / `sentence_coverage` / `term_consistency`。
- `fact_unchanged` 布尔 = 没有 `changed/removed/added`；"原文无需修改"的声明由它反推，不由 LLM 手填。

## 6. 明确盲区（写进 `result.uncertainty`）

- **语义改写**：词法项不变但含义变了（`correlated with` → `causes`、`in vitro` → `in vivo`），脚本查不出，必须人工或第二次 LLM 复核。
- **单位换算等价**：`0.9 MPa` → `900 kPa` 数值等价但单位变了，本包按 `unit_change` 阻断，交人工决定，不静默放行。
- **跨句逻辑**：把两句合并成一句、因果顺序调换，句级对齐相似度可能仍高，脚本只能给 A02 提示。

## 7. 复跑

```bash
python scripts/run.py --input examples/demo --output /tmp/o2
python examples/baseline.py --case examples/demo/case.json --out /tmp/b2
python eval/metrics.py --out_dir /tmp/o2 --base_dir /tmp/b2
python examples/selftest.py
```

---
name: academic-polish
description: 学术语言润色。在不改变原意、主张强度和事实的前提下把句子写得更顺、更地道；逐句记录改动，保住数字、单位、引用、限定词与否定，并对"有没有改事实"给出可复算的证据。
---

# academic-polish

润色本身交给 Agent 或最小编辑引擎，**本手册的价值在于把"不得改原意、不得编造数据"变成机器可复算的检查**：逐句对齐、逐条改动核对、零分母不虚报。

## 1. 输入（平台约定 `/input/`）

`case.json` 字段（脚本全部容错，缺哪个就按降级规则走）：

| 字段 | 必填 | 说明 |
|---|---|---|
| `case_id` / `id` | 是 | 与输出一致 |
| `text` / `draft` / `source_text` / `original` | 是（四选一） | 学生草稿原文 |
| `paragraphs` / `sentences` | 可选 | 草稿按段落给出时用，`[{text}]` 或字符串数组 |
| `polished_text` / `revised_text` | 可选 | Agent（LLM）产出的润色稿；**给了就只审计不改写**（`mode=llm`），不给则由最小编辑引擎产出（`mode=minimal-edit`） |
| `changes` | 可选 | LLM 稿自带改动清单（`[{original, revised, reason, fact_changed}]`） |
| `terms` | 可选 | 术语表，见 §5 |

## 2. 主产物（`scripts/run.py` 产出，不许手写）

```bash
python scripts/run.py                       # /input → /app/output
python scripts/run.py --input examples/demo --output out
```

| 文件 | 内容 |
|---|---|
| `result.json` | `case_id` / `status` / `result{polished_text, changes, unchanged_sentences, preserved, artifacts}` / `metrics` / `evidence` / `uncertainty` |
| `polished.md` | 完整润色正文 |
| `audit.json` | 阻断/提示项、保留率、术语检查、逐句台账 |
| `diff_audit.md` | 给人看的事实台账（逐句相似度 + 事实标记变化） |

`status` 由产物判定，**不手写**：

| status | 条件 |
|---|---|
| `success` | 无阻断项、结构校验通过、四项保留率全 1.0（该项无数据记 `None` 也算过）、术语无违规 |
| `partial` | 有任一阻断项、结构错误、保留率 <1.0、或术语违规 |
| `needs_attention` | 润色稿为空或 <20 字符 |
| `cannot_determine` | `case.json` 里没有任何正文 |
| `rejected` | 缺 `/input/case.json` |

## 3. 工作流（4 步）

1. **通读 + 建台账**：`fact_ledger` 抽出数字+单位、引用、限定词、否定、比较级，作为 `preserved` 的来源。
2. **最小编辑**：能不改就不改。遵守 §4 的"限定强度守恒表"，每条改动写 `original / revised / reason`，改了事实必须 `fact_changed: true`。
3. **审计落盘**：`scripts/run.py` 自动跑 `fact_ledger`（逐句对齐 + 逐条改动）、`term_check`（术语）、`guard`（结构），任一阻断即 `partial`。
4. **交付**：`result.json` + `polished.md` + `audit.json` + `diff_audit.md`。拿不准的句子进 `uncertainty`，不硬改主张。

## 4. 阻断项与提示项（`audit.json` 的 `code`）

| code | 含义 | 级别 |
|---|---|---|
| F01 | 数字+单位整体消失 | 阻断 |
| F01b | 数字还在但单位/基准变了（`3.5 wt%`→`3.5%`） | 阻断 |
| F01c | 数值也变的等价换算（`0.9 MPa`→`900 kPa`） | 阻断（需人工确认） |
| F11 | 出现原文没有的数字（编造数据） | 阻断 |
| F12 | 程度副词被删（significantly/slightly/markedly…） | 阻断 |
| F12b | 凭空加了程度副词（higher→significantly higher） | 阻断 |
| F13 | 引用被挪到别的句子（归属变了） | 阻断 |
| F02 | 引用丢失 | 阻断 |
| F03 | 凭空出现原文没有的引用 | 阻断 |
| F04 | 限定词（may/might/could/suggest/approximately…）减少 | 阻断 |
| F05 | 新增强断言且方向是弱→强（原文 weak/hedge 减少：found→proved）；强→强同义替换（proves→demonstrates）放行 | 阻断 |
| F06 | 否定减少（did not observe → observed） | 阻断 |
| F06b | 否定**增加**（thickens → does not thicken，结论被反转成反义） | 阻断 |
| F07 | 比较级/增减方向丢失（higher than、increase） | 阻断 |
| F07b | 比较级**凭空增加**（rises → rises more than expected） | 阻断 |
| F08 | 整句丢失（与所有润色句相似度 <0.45） | 阻断 |
| F09 | 出现无记录的新句子（与原文相似度 <0.6 且不在 changes.revised 里） | 阻断 |
| F10 | changes 里改了数字/引用却没 `fact_changed: true` | 阻断 |
| A01 | `changes.original` 在原文中找不到 | 提示 |
| A02 | 单句相似度 0.45–0.85（改写幅度大） | 提示 |
| A03 | 长度比 <0.7 或 >1.4 | 提示 |
| A04 | `changes.revised` 不在润色稿里 | 提示 |
| A05 | 声明了 `fact_changed` 但事实标记没变 | 提示 |
| T01 | 术语出现非规范变体 | 阻断（进 `partial`） |

**限定强度守恒表**

| 原文 | 可改为 | 不可改为 |
|---|---|---|
| `may / might / could` | `may`、`can under some conditions` | `proves`、`demonstrates`、`显著` |
| `we observed` | `we found`、`the data show` | `it is well known` |
| `only / solely` | 保留 | 删除、改为 `mainly` |
| `not / never / no` | 保留否定 | 反义改写、弱化为 `rarely` |
| `approximately / about 3.5 wt%` | 保留约数与单位 | 改成精确值、改单位 |

## 5. 术语一致性

`terms` 三种写法都认：

```json
[{"concept": "dissociation pressure", "canonical": "dissociation pressure",
  "variants": ["disassociation pressure", "dissociation pressures"]}]
```

变体出现即 T01；`term_consistency = 规范写法次数 / 全部次数`，`terms` 为空时记 `None`（不记 1.0）。

## 6. 指标与基线

```bash
python eval/metrics.py --out_dir out --base_dir base_out
```

- 保留率：`number_retention` / `citation_retention` / `hedge_retention` / `negation_retention` / `sentence_coverage` / `term_consistency`；分母为 0 记 `None`。
- `examples/baseline.py` 模拟"裸 Agent 润色"：删推测语气、丢单位、吞引用、反写否定 → 基线 `pass=false`；实测引用/限定/否定保留率 0.0，本包 1.0。

## 7. 自检

```bash
python examples/selftest.py      # 36 条断言
```

覆盖：正例、F01/F01b/F11（单位基准变化、编造数字）、F03 编造引用、F04+F05（may→proves 与 found→proved；proves→demonstrates 反向放行）、**D14/D15 标点紧跟的限定词/否定词（`may,`/`not,`）删除、D17 强→强同义放行、D18 近义双句删一句、D19 两句合并为一句（记 A02 不记 F08）**、F06 否定反写、F10 未声明改事实、F09 凭空加句、T01 术语变体、合法归一（`3.5 wt%` ↔ `3.5 wt %` 放行）、平台入口（minimal-edit 与 LLM 稿两种模式）、降级（无正文/缺 case.json）、基线差值、缺基线数据记 `None`、零事实草稿记 `None`。

## 8. 异常与降级

| 情况 | 行为 |
|---|---|
| 无正文 | `cannot_determine`，不产假正文 |
| 润色稿过短 | `needs_attention` |
| 原文零数字零引用 | 对应保留率 `None`，不冒充 1.0 |
| `guard` 结构错误 | `partial`，`notes` 写明缺哪个字段 |
| 缺 `terms` | 术语一致率 `None` |

## 9. 不能造假

- 新增原文没有的事实、数据、引用或结论（F03/F09）；
- 把 `may / 可能` 改成 `证明 / 显著`（F05），翻转否定（F06/F06b），删比较方向（F07），凭空加比较（F07b）；
- 删改数字、单位、引用编号（F01/F02）；
- 只给润色片段不给完整正文；
- `status` 手写、`pass` 不看保留率。

## 10. 事实状态与盲区

`audit.json` 的 `facts[]` 给每个原始事实一个状态：`kept` / `normalized`（写法归一，放行）/ `changed` / `removed` / `added`。`fact_preservation_rate = (kept+normalized)/原始事实总数`，`fact_unchanged` 由它反推——"原文无需修改"的声明不由 LLM 手填。

**脚本查不了的**（写进 `result.uncertainty`，不许声称脚本保证语义不变）：

- 语义改写：`correlated with` → `causes`、`in vitro` → `in vivo` 这类词法项不变的改写；
- 单位换算等价：`0.9 MPa` → `900 kPa` 按 `unit_change` 阻断，交人工决定，不静默放行；
- 跨句逻辑：合并句子、调换因果顺序，只给 A02 提示。

详见 `references/method.md`。



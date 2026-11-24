---
name: related-work-matrix
description: 把参考文献整理成"工作×维度"比较矩阵，由矩阵里重复出现的共同局限推出研究空白，再按矩阵分组写相关工作，最后逐句核对"论断是否挂了引用、引用是否都在库里、贡献是否有图表证据"。用于写引言/相关工作时避免逐篇摘要拼接。
---

# 相关工作：从比较矩阵到可核对的空白

## 0. 单点

**先做矩阵，再写文字**：每条工作落在"问题设定 / 方法路线 / 数据与尺度 / 评价与指标 / 局限"五维上；空白只能由矩阵中**反复出现的局限 + 无人覆盖**推出；正文里每个实质论断必须挂引用，每条贡献必须指向本文图表。

不做的：不做整篇论文代写、不生成摘要、不编造文献。

## 1. 何时触发

触发："写引言""整理相关工作""这组文献怎么分组""研究空白怎么写""贡献怎么写才不虚"。
不触发：单篇摘要、文献列表排序、翻译、格式转换。

## 2. 输入与输出

输入：`/input/case.json`、`/input/task.md`、文献材料（可能给 PDF/摘要/元数据）、`references` 清单、本文的章节与图表信息。
**先读材料再建矩阵**；材料里没有的工作不得写进矩阵。

输出 `/app/output/`：

| 文件 | 内容 |
|---|---|
| `matrix.md` | 工作×维度表，每格带来源定位 |
| `matrix.json` | 同上，机器可读；含 `coverage`、`gaps`、`conflicts` |
| `intro_draft.md` | 四段式：研究背景 / 相关工作（按矩阵分组）/ 研究空白 / 贡献 |
| `bind.json` | 论断-引用绑定报告（未挂引用的论断、悬空引用、未用文献、空白支撑不足、贡献证据缺失） |
| `result.json` | 契约字段 `case_id` + `status` + `metrics`，**由 `scripts/run.py` 产出**（读 `/input/case.json`，不手填） |

`status` 由脚本按产物判定：`success` 需绑定核对 `pass`、贡献 ≥1 条、工作 ≥3 篇；`partial` 是矩阵出来了但核对未过或缺草稿/贡献/空白；`cannot_determine` 是连矩阵都建不起来（缺 works/dimensions）；`rejected` 是输入不成立。零贡献时 `contribution_evidence_rate` 记 `null` 并报 `contribution_missing`，不记 1.00。

## 3. 流程

**第 1 步 建矩阵（脚本建骨架，你填证据）**
```
python scripts/matrix.py build --works work/works.json --dims work/dimensions.json --out /app/output
```
`works.json` 每条形如：
```json
{"wid":"W1","label":"[1]","year":2021,"route":"实验相态测量",
 "problem":"CO2 注入后的相态偏移","data":"3 组砂岩岩心，10–30 MPa","metric":"露点偏移",
 "limitation":"未覆盖 40 MPa 以上","limits":["高压条件"],"addresses":["长期监测"],
 "stance":{"CO2 提高露点":"supports"},
 "evidence":{"locator":"p.4 §2.3","quote":"dew point increased by 3.2 MPa"}}
```
矩阵没填满时脚本会给 `gap_cells`，**缺格不是空白**，只是提醒你补材料。

**第 2 步 推空白（只能从 `gaps` 出发，不许自由发挥）**
`matrix.py` 的 `gaps` 规则：某个局限被 ≥2 篇列为 `limits`，且没有任何一篇 `addresses` 它 → 候选空白，附支撑 wid。
你必须为每个空白写一句"由谁的什么限制推出"，并在正文中至少引 2 篇。支撑不足的空白会在 `bind.json` 里报 `gap_unsupported`。

**第 3 步 写四段（你写，按矩阵分组）**
- 背景：从"具体问题 + 技术约束"起句，禁止"近年来受到广泛关注"这类空转。
- 相关工作：**按矩阵的 route 分组**，每组先给该组共同设定，再在同一维度上比较取舍（不是逐篇摘要）。同组内出现相反结论时，必须写清条件差异。
- 空白：逐条对应第 2 步的 gap，写"谁的限制 + 无人覆盖 + 本文如何对应"。
- 贡献：3–5 条，每条形如"我们做了 X，证据见 §/Fig./Table"。证据必须能在 `manuscript.json` 中找到。

**第 4 步 绑定核对（脚本，必须跑）**
```
python scripts/claim_bind.py --draft /app/output/intro_draft.md --works work/works.json \
  --manuscript work/manuscript.json --out /app/output
```
硬门槛：

| 指标 | 门槛 |
|---|---|
| 论断挂引用率（含数字/比较/因果/首次类句子） | = 1.00 |
| 论断数字一致性（句内"数字+单位"必须能在所引 work 的记录里找到） | 违例 = 0（`claim_evidence_conflict`） |
| 悬空引用（引了库里没有的 wid） | = 0 |
| 关键文献覆盖率（`key=true` 与近 2 年工作） | = 1.00 |
| 空白支撑度（**按 matrix 的每个 gap 逐个复核**：必须有一句落在空白/局限小节、或点名该 gap 的限制词，且同时引到该 gap 的 ≥2 篇 `support_wids`） | = 1.00，`gaps_covered=gaps_total` |
| 贡献证据率（每条贡献指向存在的章节/图表） | = 1.00 |

**第 5 步 回填**
把 `bind.json` 的 `violations` 逐条改掉再重跑；仍无法满足的（例如材料里确实没有关键文献），在 `result.json` 的 `uncertainties` 写明"缺 X，未覆盖"，**不许补造条目**。

注意口径：转述他人数值必须与库内记录同值（`3.2 MPa` 写成 `9.9 MPa` 属于数字造假，直接阻断，不是笔误）；空白小节里的纯解释句（不带引用、也不断言领域空白）不强制挂引用，但**断言空白的句子必须引到该 gap 的支撑文献**，"任意 2 篇"不算过关。

## 4. 预算与降级

64 请求 / 900 秒。顺序：矩阵（脚本，0 请求）→ 空白（你，1–2 请求）→ 四段（每段 1 请求，共 4–6）→ 核对（脚本）→ 回填（1–2 请求）。剩余 <6 请求时交付 `partial`，把已完成的段落与未完成清单写清。

## 5. 异常

| 情况 | 处置 |
|---|---|
| 文献库为空 / 只给题录 | 只写"背景 + 待补文献清单"，`status=partial`，不写相关工作 |
| 引用查不到原文 | 该条只作"题录级引用"，在 `uncertainties` 标注"未读原文" |
| 同一工作两种结论 | 用 `stance` 标出冲突，正文写条件差异，不选边 |
| 目标期刊格式未知 | 默认数字式 `[n]`，并在 `README`/`result.json` 注明"编号待期刊模板确认" |
| 材料里数值与摘要不一致 | 以原文为准，冲突写进 `uncertainties` |

## 6. 自检

```
python examples/selftest.py
```
要求（共 14 条，全绿才算过）：正例 `bind.json` 五项全过；注入的四类缺陷（论断无引用、悬空引用、空白单篇支撑、贡献证据不存在）必须全部命中；再加六条：
1. 论断数字与所引记录不一致（`3.2 MPa` 改 `9.9 MPa`）→ `claim_evidence_conflict`、`pass=false`；
2. 空白句改引非支撑文献（引 `W1/W2` 而该 gap 支撑是 `W4/W6`）→ `gap_support_rate=0.0`、报"长期监测未获 ≥2 篇支撑"；
3. 重述式空白句（"现有工作在这一尺度上仍有明显不足"，不含"覆盖/研究/工作"字样）仍被识别为空白、仍卡支撑；
4. `run.py` 由 `case.json` 产出合法 `result.json`（demo 上 `status=success`）；
5. 零贡献草稿不虚报 1.00（`contribution_evidence_rate=null` + `contribution_missing`）、悬空引用不计入挂引用率、基线（逐篇摘要）`group_total=null / pass=false`；
6. `result.json.metrics` 的 `gaps_total`/`gaps_covered`/`claim_evidence_checks` 与 `bind.json`、`bind_report.md` 的 ✓ 行逐项相等（论断条数、空白句条数、矩阵空白个数、贡献条数、数字核对处数），口径只允许一套。

# 04 · 相关工作：从比较矩阵到可核对的空白

**一句话**：先把文献填进"工作×五维"比较矩阵，空白只允许从"≥2 篇共同局限且无人覆盖"推出来，再按矩阵分组写四段式引言，最后逐句核对"论断是否挂引用、引用是否在库里、贡献是否有图表证据"。

只做这一件事：不代写整篇论文、不生成摘要、不编造文献。

---

## 1. 为什么是这个单点

基础 Agent 写"相关工作"最典型的产物是**逐篇摘要拼接**：一段一篇，句句通顺，但读者看不出这些工作在同一维度上谁强谁弱，也看不出空白到底由什么证据支撑。常见四个硬伤：

1. **论断无引用**：比较句、因果句、"首次"句没有出处；
2. **悬空引用**：正文引了库里没有的编号；
3. **空白拍脑袋**：写"尚属空白"但只挂 1 篇，甚至 0 篇；
4. **贡献无证据**：写"本文提出 X"，但 X 找不到对应章节或图表。

这四个问题都能被机器判定，所以 v3 把它们做成硬门槛；同时把"怎么分组、怎么比较"交给矩阵结构，而不是让模型自由发挥。

## 2. 交付物

| 文件 | 内容 |
|---|---|
| `matrix.md` | 人读的工作×维度表，每格带来源定位 |
| `matrix.json` | 机器可读矩阵；含 `coverage`、`gap_cells`、`gaps`、`conflicts`、`groups`、`thin_groups` |
| `intro_draft.md` | 四段式：研究背景 / 相关工作（按 route 分组）/ 研究空白 / 贡献 |
| `bind.json` | 论断-引用绑定报告：未挂引用、悬空引用、未用文献、空白支撑不足、贡献证据缺失 |
| `result.json` | 契约字段 + `case_id` + `status` + 从两份报告拷贝的 `metrics` |

## 3. 五维矩阵的定义

| 维度 | 含义 | 填不出来的后果 |
|---|---|---|
| `problem` | 该工作解决的具体问题设定 | 该格进 `gap_cells`，提示补材料，**不等于空白** |
| `route` | 方法路线（实验测量 / 模拟 / 现场 / 综述…） | 无法分组，相关工作只能逐篇写 |
| `data` | 数据与尺度（样品数、温压范围、空间尺度） | 无法判断"可比/不可比" |
| `metric` | 评价指标与判定口径 | 冲突结论无法解释 |
| `limit` | 作者自述的局限 | 空白推不出来 |

空白规则（`matrix.py` 内置，不可由模型改写）：

```
候选空白 = { 某局限 L | count(works where L ∈ limits) ≥ 2
                      且 count(works where L ∈ addresses) = 0 }
```

`conflicts` 来自 `stance` 字段：同一论断有人 `supports`、有人 `opposes` 时自动登记，正文必须写条件差异，不许选边。

## 4. 流程

**第 1 步 建矩阵（脚本建骨架，模型填证据）**

```
python scripts/matrix.py build --works work/works.json --dims work/dimensions.json --out /app/output
```

`works.json` 单条示例：

```json
{"wid":"W1","label":"[1]","year":2021,"route":"实验相态测量",
 "problem":"CO2 注入后的相态偏移","data":"3 组砂岩岩心，10–30 MPa","metric":"露点偏移",
 "limitation":"未覆盖 40 MPa 以上","limits":["高压条件"],"addresses":["长期监测"],
 "stance":{"CO2 提高露点":"supports"},
 "evidence":{"locator":"p.4 §2.3","quote":"dew point increased by 3.2 MPa"}}
```

**第 2 步 推空白（只能从 `gaps` 出发）**

每个空白必须写清"由谁的什么限制推出"，正文至少引 2 篇；支撑不足会被 `bind.json` 报 `gap_unsupported`。

**第 3 步 写四段（模型写，按矩阵分组）**

- 背景：从"具体问题 + 技术约束"起句，禁止"近年来受到广泛关注"这类空转；
- 相关工作：**按 `route` 分组**，每组先给共同设定，再在同一维度上比较取舍，不逐篇摘要；同组内相反结论必须写条件差异；
- 空白：逐条对应第 2 步的 gap，写"谁的限制 + 无人覆盖 + 本文如何对应"；
- 贡献：3–5 条，每条形如"我们做了 X，证据见 §/Fig./Table"，证据必须能在 `manuscript.json` 中找到。

**第 4 步 绑定核对（脚本，必须跑）**

```
python scripts/claim_bind.py --draft /app/output/intro_draft.md --works work/works.json \
  --manuscript work/manuscript.json --out /app/output
```

**第 5 步 回填**

按 `bind.json` 的 `violations` 逐条改再重跑；材料确实缺关键文献时，在 `result.json` 的 `uncertainties` 写"缺 X，未覆盖"，**不许补造条目**。

## 5. 硬门槛

| 指标 | 定义 | 门槛 |
|---|---|---|
| 论断挂引用率 | 含数字/比较/因果/"首次"的句子中，带 `[n]` 的比例 | = 1.00 |
| 悬空引用 | 引用编号不在 `works.json` 里的条数 | = 0 |
| 关键文献覆盖率 | `key=true` 与近 2 年工作被引入正文的比例 | = 1.00 |
| 空白支撑度 | 每个空白 ≥2 篇 `limits` 支撑的比例 | = 1.00 |
| 贡献证据率 | 每条贡献指向真实存在的 §/Fig./Table 的比例 | = 1.00 |

## 6. 实测证据（构造演示，非平台案例）

`examples/demo/works.json` 是 6 篇构造文献，`examples/expected/` 是真实产物：

- 6 篇 × 5 维，**五维填充率均 1.00**，`gap_cells` 为空；
- 自动推出 **1 条空白**：`长期监测` 被 W4、W6 两篇列为局限且无人 `addresses`；
- 自动登记 **1 处冲突**：`CO2 提高露点` 由 W1/W3 支持、W2 反对，正文按条件差异处理；
- 按 route 分成 **3 组、每组 2 篇**，`thin_groups` 为空；
- 正文 **8 条论断全部挂引用**、**1 条空白句有 2 篇支撑**、**3 条贡献全部指向 manuscript 中真实章节/图表**；
- 四项比率均 1.00，`violations` 为空，`pass=true`。

缺陷注入自检（`python examples/selftest.py`）要求四类破坏全部命中：

| 注入 | 预期违规 |
|---|---|
| F1 论断无引用 | `claim_uncited` |
| F2 悬空引用 | `dangling_citation` |
| F3 空白只有 1 篇支撑 | `gap_unsupported` |
| F4 贡献证据不存在 | `contribution_evidence_missing` |

6 条断言全绿。

## 7. 异常与降级

| 情况 | 处置 |
|---|---|
| 文献库为空 / 只给题录 | 只写"背景 + 待补文献清单"，`status=partial`，不写相关工作 |
| 引用查不到原文 | 该条降为"题录级引用"，`uncertainties` 标"未读原文" |
| 同一工作两种结论 | `stance` 标冲突，正文写条件差异，不选边 |
| 目标期刊格式未知 | 默认数字式 `[n]`，在 `result.json` 注明"编号待期刊模板确认" |
| 材料数值与摘要不一致 | 以原文为准，冲突写进 `uncertainties` |
| 预算不足（剩余 <6 请求） | 交付 `partial`，列已完成段落与未完成清单 |

## 8. 快速开始

```bash
python scripts/matrix.py build --works work/works.json --dims work/dimensions.json --out out
# 模型据 out/matrix.json 的 gaps/groups 写 out/intro_draft.md
python scripts/claim_bind.py --draft out/intro_draft.md --works work/works.json \
  --manuscript work/manuscript.json --out out
python eval/metrics.py --out_dir out
python examples/selftest.py
```

依赖：Python 3.10+，仅标准库，无网络调用。

## 9. 目录结构

```
04-related-matrix/
├── SKILL.md
├── README.md
├── scripts/            # matrix.py（矩阵+空白）、claim_bind.py（绑定核对）
├── references/method.md
├── eval/               # rubric.yaml / metrics.py / protocol.md
├── baseline/cases.md
├── examples/
│   ├── demo/           # works.json / dimensions.json / manuscript.json / intro_draft.md
│   ├── expected/       # matrix.md+json / bind.json / bind_report.md
│   └── selftest.py
└── environment/resources.yaml
```

## 10. 维护与扩展

- 新增维度：在 `dimensions.json` 加键并在 `matrix.py` 的必填集合登记；`coverage` 会同步计算，不需要改核对器；
- 换学科：把 `route` 取值表换成该领域的方法分类（如"野外剖面 / 室内实验 / 数值模拟 / 机器学习"）；
- 空白规则若需放宽（例如 ≥2 篇改为 ≥3 篇），改 `matrix.py` 的阈值并同步 `eval/rubric.yaml`，保持"自述=实测"；
- `claim_bind.py` 的关键词表可按语言扩展（中文"首次/显著/优于"、英文 `first / significant / outperform`）。

## 11. 声明

- 演示文献编号、作者、年份、结论均为构造，**不得作为真实引用**；
- 本包未在平台运行，不声称任何平台得分；
- 不生成真实文献、不伪造 DOI、不替代人工的语义抽检（转述是否准确仍需人读）。

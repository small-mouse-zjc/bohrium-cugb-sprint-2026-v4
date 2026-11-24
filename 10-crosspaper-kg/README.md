# 10 · 跨篇别名归一 + 证据绑定 + 可执行查询

**一句话**：把两篇独立材料合成一个可查询图谱——同名/缩写归一，但"同名不同样品/模型/数据集"必须显式判为**不合并**并留证据；每条关系边都能回指原文一句；每条查询结果都带证据，空结果就报空。

只做这一件事：不做文献综述写作、影响因子统计、PDF 排版、单篇摘要。

---

## 1. 为什么是这个单点

多篇材料合到一起时，最容易犯的错不是"漏实体"，而是**错合并**：两篇都写 `sediment sample`，一篇是现场岩心 CUG-3、一篇是实验室合成样 S2，直接并成一个节点，后面所有"对比结论"都建立在一个不存在的同一对象上。第二类错误是**边无出处**：图谱画得很漂亮，问"这条边凭什么"答不出来。

v3 因此把优先级倒过来：**不错误合并 > 引文逐字 > 查询覆盖 > 节点数量**。规则判不了就保守不合并，并写 `non_merge` 说明理由。

## 2. 交付物

| 文件 | 内容 |
|---|---|
| `result.json` | 契约字段 `case_id` + `status` + `metrics`，**由 `scripts/run.py` 产出**（取自 `validation.json` 与 `query_validation.json`） |
| `kg.json` | 节点（别名、`attrs`、逐条提及）+ 边（含 `evidence`）+ `non_merge` 判定 |
| `queries_result.json` | 每条查询的问题、结果、证据列表 |
| `validation.json` | 六类违规码 + 覆盖率/引文率/查询有证据率 |
| `kg_report.md` | 人读版：哪些合并、哪些明确不合并、为什么 |

## 3. 归一与不合并规则

归一键：`NFKC` → 小写 → 连字符转空格 → 去标点 → 末词单数化。例：`Gas-Hydrates` 与 `gas hydrate` 同键。

缩写只按**本篇**的"全称 (缩写)"展开，不跨篇借用。同一缩写在两篇含义不同时，各篇独立，并记一条 `non_merge`。

`non_merge` 触发条件（任一）：

- 身份字段（`site / sample_id / model_id / dataset_id / conditions`）取值冲突；
- 身份字段**不重叠**——无法证明是同一实例（如"现场 CUG-3"与"实验室 S2"）；
- 同名术语分属不同类型（物质 vs 方法）。

节点正名选择：`(是否缩写, -出现次数, -长度, 字面)` 排序取首，避免把 `GH` 当成正名。

## 4. 流程

**第 1 步 建提及（模型做）**

逐段列出术语出现：`surface`（原文写法，不改大小写）、`type`（material/environment/property/method/location/value）、`paragraph_id`、`quote`（含该术语的那句原文）。有身份线索就写 `attrs`。

**第 2 步 归一与不合并（脚本 + 模型复核）**

```
python scripts/kg.py build --corpus work/corpus.json --relations work/relations.json --queries work/queries.json --out /app/output
```

模型必须复核每条 `non_merge` 的理由能否说服审稿人，不能只写"不确定"。

**第 3 步 绑边（模型做）**

每条边一个句子，`quote` 逐字复制；脚本校验是否为该段落**连续子串**，不是就 K03，边不进入图谱。写不出原文句子的关系不许建边。

**第 4 步 跑查询并交付**

`queries.json` 至少 3 条，覆盖：①跨篇归一证据 ②同一关系的多篇报告 ③两个概念间的证据链（可选第四条：非合并清单）。任一查询 `evidence` 为空即 K04，必须在 `result.json` 的 `uncertainties` 说明"该问题在本语料中无证据"，不许用常识补。

## 5. 违规码

| 码 | 含义 |
|---|---|
| K01 | 同键节点未被合并（归一失效） |
| K02 | 冲突限定被合并进同一节点（错误合并） |
| K03 | 边引文不是该段落连续子串 |
| K04 | 查询无证据支撑 |
| K05 | 缩写无篇内全称 |
| K06 | 端点无法解析 / 段落号不存在 |

## 6. 实测证据（构造演示，非平台案例）

`examples/demo/corpus.json` 是两篇构造材料，`examples/expected/` 是真实产物：

- **19 条提及 → 11 个节点**，其中 **6 个跨篇节点**（`mention_coverage=1.00`，无未解析别名）；
- **1 条非合并判定**：`sediment sample` 的现场样 CUG-3 与实验室样 S2 判不合并，理由与双篇证据写入 `non_merge`；
- **6 条边**，`edge_evidence_rate=1.00`（每条引文均为段落连续子串）；
- **4 条查询**（`node / edges / path / nonmerge`）全部有证据，`query_provenance_rate=1.00`；
- `violations` 为空，`pass=true`；`uncertainties` 明确写"同名不同实例，已判不合并，不做跨样品推论"。

四条查询的实际问题：

1. 两篇里的 `gas hydrate / GH` 是否归一为同一节点，证据分别在哪段？
2. 哪些论文报告了 `dissociation pressure` 随 `salinity` 上升，各自引文是什么？
3. `salinity` 与 `dissociation pressure` 之间能否走出证据链？
4. 哪些同名术语因限定冲突不得合并，依据是什么？

缺陷注入自检（`python scripts/run.py                      # 平台入口：/input → /app/output（含 build + query）
python examples/selftest.py`）要求五类破坏全部命中或正确拒绝：

| 注入 | 预期 |
|---|---|
| D1 变体未归一（`Gas-Hydrates` 漏并） | K01 |
| D2 冲突限定被合并 | K02 |
| D3 改写引文 | K03 |
| D4 空查询 | K04 |
| D5 缩写无篇内全称 | K05 |

自检 **20 条**全绿，另覆盖：**引文逐字但与本边无关（同段落另一句）→ K03 端点缺席、边不成立**；**同篇同名多实例按 relation 的 `paragraph_id` 绑到正确节点、段落也对不上则 K09 拒绝建边（不静默取首个实例）**；**relation 缺 `paper_id` → K06 而非 KeyError**；**提及 `quote` 被改写 → K10 且回退成该段真实句**；**`non_merge_reasons` 只写"不确定" → K11、`reason_source` 退回 `auto`（正例为 author）**；平台入口（`case.json → result.json`，`status=success` 且 query-only 独立跑通）、query 只读 `kg.json`（哨兵标签未被覆盖，证明没有重跑 build）、少于 3 条查询 → `K07/K08（查询数<3；查询未覆盖 node/edges/path 三类）` + `pass=false`、零边时 `edge_evidence_rate=None`（不把"没数据"记成 0）、基线对照（边引文率 1.0 vs 0.0、非合并 1 vs 0、`pass_gap=true`）、缺 `validation.json` 的基线段记 `None` 不崩溃。

## 7. 异常与降级

| 情况 | 处置 |
|---|---|
| 同一缩写两篇含义不同 | 不跨篇展开，各篇独立，记 `non_merge` |
| 同名但一为现场样、一为数值模型 | 拆节点，`rule` 写"术语相同≠实例相同" |
| 只有图表、无正文句 | 不建边，`uncertainties` 记"结论在图表中" |
| 两篇结论相反 | 两条边都保留，`predicate` 分别为 `supports`/`contradicts`，不折中 |
| 段落号缺失 | K06，该提及不进入图谱 |
| 预算不足（剩余 <8 请求） | 停建新边，跑查询并交 `partial` |

## 8. 快速开始

```bash
python scripts/kg.py build --corpus work/corpus.json --relations work/relations.json \
  --queries work/queries.json --out out
python eval/metrics.py --out_dir out
python scripts/run.py                      # 平台入口：/input → /app/output（含 build + query）
python examples/selftest.py
```

依赖：Python 3.10+，仅标准库，无网络调用。

## 9. 目录结构

```
10-crosspaper-kg/
├── SKILL.md
├── README.md
├── scripts/kg.py            # 归一/非合并/边校验/查询
├── references/method.md
├── eval/                    # rubric.yaml / metrics.py / protocol.md
├── baseline/cases.md
├── examples/
│   ├── demo/                # corpus.json / relations.json / queries.json
│   ├── expected/            # kg.json / queries_result.json / validation.json / result.json
│   └── selftest.py
└── environment/resources.yaml
```

## 10. 维护与扩展

- 归一规则：在 `kg.py` 的 `normalize_key` 加学科变体（如 Greek 字母、矿物缩写），需补一条回归用例；
- 身份字段：扩展 `IDENTITY_FIELDS` 时同步 `non_merge` 判定与文档，避免"新字段不参与判定"的静默漏洞；
- 关系词表：与 09 保持一致的封闭集合，跨包复用时只改一处映射；
- 接真实语料：段落号必须来自 JATS `paragraph_id`；无段落号时先补编号，不许用页码代替。

## 11. 声明

- 演示材料为两篇构造文本，**非真实文献、非平台案例**；
- 本包未在平台运行，不声称任何平台得分；
- 不做 ML 实体消歧；规则判不了就不合并；不生成两篇都没有的"综合结论"，不换算单位、不解析图表数值。

---
name: cross-paper-alias-graph
description: 把两篇相互独立的论文材料合成一个可查询图谱：跨篇同名术语归一（含"相同术语但不得合并"的显式判定）、每条关系边绑逐字原文引文、并提供至少三条真执行查询且每条结果都带证据。用于"多篇材料同一主题、需要区分'同一个东西'与'只是叫法相同'"的综述前置整理。
---

# 跨篇别名归一 + 证据绑定 + 可执行查询

## 0. 这个 Skill 只做一件事

把**两篇独立材料**变成**一个可查询图谱**：同名/缩写归一，但"同名不同样品/不同模型/不同数据集"必须**显式判为不合并并留下证据**；每条边都必须能回指原文一句话；查询结果必须带证据，空结果就报空。

不做：文献综述写作、影响因子统计、PDF 排版、单篇摘要。遇到这些请求说明超出范围。

## 1. 何时触发

触发：用户给出**两篇及以上**材料，要求"合并/对齐/去重/统一术语""建知识图谱""比较两篇的同一概念""哪些能比、哪些不能比"中的任意一项。
不触发：单篇材料内抽取、只要一张对照表、只要文字综述。

## 2. 输入与输出

输入（平台约定 `/input/`）：`corpus-manifest.json`（DOI/作者/哈希/许可）、`material.json`、`primary-material.json`、`secondary-material.json`。**`scripts/run.py` 负责把材料装配成 `corpus.json`（`materials[]` 直传也可），再接 `kg.py build → kg.py query`**；脚本不要求平台预先把材料摊成内部格式。
段落号用 **JATS `paragraph_id`**；**不要写"第 N 页"**，行内公式已被线性化，无图像像素。

先整理成三份工作文件：

- `corpus.json`：`{papers:[{paper_id, doi, title, year, paragraphs:[{paragraph_id,text}], mentions:[{surface,type,paragraph_id,quote,attrs?}]}]}`
- `relations.json`：`{relations:[{id,paper_id,subject,predicate,object,paragraph_id,quote}]}`
- `queries.json`：≥3 条，`kind` 取 `node / edges / path / nonmerge`

输出（`/app/output/`）：

| 文件 | 内容 |
|---|---|
| `result.json` | 契约字段 `case_id` + `status` + `metrics`，由 `scripts/run.py` 产出 |
| `kg.json` | 节点（含别名、attrs、逐条提及）+ 边（含 evidence）+ `non_merge` 判定 |
| `queries_result.json` | 每条查询的问题、结果、证据列表 |
| `validation.json` | K01–K08 违规码 + 覆盖率/引文率/查询有证据率 |
| `kg_report.md` | 人读版：哪些合并了、哪些明确不合并、为什么 |

## 3. 流程（4 步）

**第 1 步 建提及（你来做）**
逐段列出术语出现：`surface`（原文写法，不改大小写）、`type`（material/environment/property/method/location/value…）、`paragraph_id`、`quote`（含该术语的那句原文）。
有身份线索就写 `attrs`：`site / sample_id / model_id / dataset_id / conditions`。

**第 2 步 归一与不合并（脚本 + 你复核）**
```
python scripts/kg.py build --corpus work/corpus.json --relations work/relations.json --queries work/queries.json --out /app/output
```
规则：归一键统一大小写/连字符/单复数；缩写只按**本篇**的"全称 (缩写)"展开，不跨篇借用；身份字段冲突或不重叠 → 拆节点并写 `non_merge`。
你必须复核 `non_merge`：理由要能说服审稿人（"现场样 vs 实验室合成样"这类），不能只写"不确定"。

**第 3 步 绑边（你来做）**
每条边一个句子，`quote` 逐字复制。脚本双重校验：① `quote` 是否为该段落连续子串；② `quote` 里是否真的出现 subject 与 object 在本篇的写法（任一端点缺席即 K03）。写不出支撑这条边的原文句子的关系**不许建边**。端点解析优先用关系给的 `paragraph_id`（同篇同名多实例时取"该段有提及"的那个节点）；段落也对不上就不建边、报 K09，**不静默取第一个节点**；关系缺 `paper_id` 报 K06 而非崩溃。

**第 4 步 跑查询并交付**
`queries.json` 至少三条，覆盖：①跨篇归一证据 ②同一关系的多篇报告 ③两个概念间的证据链（可选第四条：非合并清单）。
任一查询 `evidence` 为空即 K04，必须在 `result.json` 的 `uncertainties` 说明"该问题在本语料中无证据"，不许用常识补。

## 4. 违规码

| 码 | 含义 |
|---|---|
| K01 | 同键节点未被合并（归一失效） |
| K02 | 冲突限定被合并进同一节点（错误合并） |
| K03 | 边引文不是该段落连续子串，或引文里没有 subject/object 在本篇的写法（逐字但不支持这条边） |
| K04 | 查询无证据支撑 |
| K05 | 缩写无篇内全称 |
| K06 | 端点无法解析 / 段落号不存在 |
| K07 | 查询少于 3 条，图谱结论无法独立复问 |
| K08 | 查询未覆盖 node/edges/path 三类（三条同类查询不算独立复问） |
| K09 | 同篇同名多实例、段落号也对不上 → 端点歧义，拒绝建边（不静默取第一个节点） |

## 5. 预算与降级（64 请求 / 900 秒 / 单次 16384 tokens）

- 优先级：不错误合并 > 引文逐字 > 查询覆盖 > 节点数量。
- 两篇材料各先处理 `Abstract / Results / Conclusions`，再补 `Methods`。
- 剩余请求 < 8 时停建新边，跑第 4 步并交 `partial`。

## 6. 异常处置

| 情况 | 处置 |
|---|---|
| 同一缩写两篇含义不同 | 不跨篇展开，各篇独立；`non_merge` 记一条 |
| 同名但一个是现场样、一个是数值模型 | 拆节点，`rule` 写"术语相同≠实例相同" |
| 只有图表、无正文句 | 不建边；`uncertainties` 记"结论在图表中" |
| 两篇结论相反 | 两条边都保留，`predicate` 分别为 supports/contradicts，不折中 |
| 段落号缺失 | K06，该提及不进入图谱 |

## 7. 自检
```
python examples/selftest.py
```
注入 9 类缺陷全部命中或正确拒绝：变体未归一（K01）、冲突合并（K02）、改写引文（K03 子串不成立）、**同段落但与本边无关的逐字引文（K03 端点缺席）**、空查询（K04）、缩写无全称（K05）、**同篇同名多实例按 `paragraph_id` 正确绑定 / 段落也对不上（K09 拒绝建边）**、**relation 缺 `paper_id`（K06 而非 KeyError）**，另有查询数 <3（K07）与查询类型覆盖不足（K08）。共 18 条断言全绿。

## 8. 边界

- 不做 ML 实体消歧；规则判不了就**不合并**（保守优先）。
- 不生成两篇都没有的"综合结论"。
- 不换算单位、不解析图表数值、不写页码。

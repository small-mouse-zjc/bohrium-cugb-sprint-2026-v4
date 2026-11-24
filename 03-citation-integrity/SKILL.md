---
name: citation-integrity
description: 学术引用管理。把正文引用与文后文献表对齐、去重合并、编号按首次出现顺序连锁重排；元数据逐字来自原始来源，缺什么留空，绝不编造作者/年份/期刊/DOI/卷期页码。
---

# citation-integrity

引用管理的不可替代价值不是"排得好看"，而是**能证明编号、去重、元数据三者都没有被顺手改坏**。

## 1. 输入（平台约定 `/input/`）

| 字段 | 必填 | 说明 |
|---|---|---|
| `case_id` / `id` | 是 | 与输出一致 |
| `manuscript` / `editable_manuscript` / `text` / `draft` | 是 | 正文（含 `[n]` 或 `(Author, Year)` 引用） |
| `bibliography` / `references` / `sources` / `bib` | 是 | **原始**文献表，是元数据真伪的唯一基准 |
| `style` | 可选 | `numeric`（默认）/ `author-year` |
| `result` / `proposed_result` | 可选 | LLM 已产出的结果；给了就只审计不改写（`mode=llm`） |

缺正文或文献表 → `cannot_determine`（不猜、不补）；缺 `case.json` → `rejected`。

## 2. 主产物（`scripts/run.py` 产出）

```bash
python scripts/run.py                        # /input → /app/output
python scripts/run.py --input examples/demo --output out
```

| 文件 | 内容 |
|---|---|
| `result.json` | `result{editable_manuscript, bibliography, number_mapping, claim_source_map, unresolved, unused, uncertainty}` + `metrics` |
| `manuscript.md` | 重排后的可编辑正文 |
| `bibliography.json` | 重排后的文献表（只含被引条目，元数据逐字） |
| `cite_chain.md` | 审计报告 |

`status` 由产物判定：`success` 需四方审计零阻断且无未解析引用；有阻断或未解析 → `partial`。

## 3. 工作流（4 步）

1. **盘点原始来源**：以 `case.json` 的文献表为准，逐条核对；缺 DOI/卷期不补全。
2. **查重合并**：作者姓+首字母、年份、标题规范化相似度 >0.9 三条同时成立才合并；**DOI 不同的两条不合并**（可能是会议版/期刊版），写进 `uncertainty`。
3. **连锁重排**：新编号 = 正文首次出现顺序 1..N；正文所有标记同步改写；`number_mapping` 记录 `from_id → bib_id`。
4. **审计落盘**：`scripts/run.py` 自动跑 `cite_chain.audit`（四方闭环 + 元数据逐字）与 `guard`（结构）；任一阻断即 `partial`。

## 4. 阻断码（`cite_chain.md` / `metrics.blocking`）

| code | 含义 |
|---|---|
| C01 | 正文编号在文献表里没有（悬空引用） |
| C02 | 新编号不连续（不是 1..N） |
| C03 | 编号顺序与正文首次出现顺序不一致 |
| C04 | 仍有可合并重复（作者+年份+标题>0.9 且 DOI 不冲突） |
| C05 | 两条文献 `key` 相同 |
| C06 | `number_mapping` 的 citation / bib_id / key 与正文或文献表不符 |
| C07 | 文献表出现原始来源里没有的条目 |
| C08 | 原始来源为空的字段被填了值（编造 DOI/卷期/页码） |
| C09 | 原始来源有值，输出却被删空（元数据丢失） |
| C10 | DOI 不同的会议版/期刊版被合并 |
| A06 | 同作者同年、标题相似但非逐字相同（0.9<sim<1.0）且无同 DOI：不自动合并，记 merge_advisories 待人工确认（如同一作者 2020a/2020b） |
| C11 | `claim_source_map` 没覆盖正文里的引用 |
| C12 | 重排后编号指向了另一篇论文（DOI/标题身份变了） |
| C13 | DOI 出现 `urn:doi:urn:doi:` 之类重复前缀 |

提示码：A01 `listed_not_cited`（原始条目未被引用，已保留并说明）、A02 `partial_metadata`。

## 5. 指标（分母为 0 记 `None`，不记 1.0）

- `citation_closure_rate` = 能解析的正文引用 / 全部正文引用
- `metadata_verbatim_rate` = 与原始来源逐字一致的字段数 / 核对字段数
- `claim_map_coverage` = 被 `claim_source_map` 覆盖的引用 / 全部引用
- `renumber_identity_rate` = 重排后编号身份不变（DOI+标题同一篇）/ 可核对条数

## 6. 自检

```bash
python examples/selftest.py      # 25 条断言
```

覆盖：正例（真重复合并、会议版不合并、编号重排 1..3、claim 全覆盖）、C01–C13 十一类注入、author-year 风格、平台入口（engine / llm 两种模式）、降级、基线对照、缺基线数据记 `None`。

## 7. 基线（`examples/baseline.py`）

模拟"裸 Agent 整理"：按标题粗合并（把会议版并掉）、删未引用条目不重排（留缺号）、补占位 DOI、卷期页码被"排版精简"、`claim_source_map` 留空。实测：claim 覆盖 1.0 vs 0.0、元数据逐字率 1.0 vs 0.8519，阻断 C02/C09/C10/C11。

## 8. 不能造假

- 编造作者、年份、标题、期刊、DOI、卷期页码（C07/C08）；
- 把 DOI 不同的会议版与期刊版合成一条（C10）；
- 只改正文不改文献表（C01/C03），或只改表不改正文；
- 删掉原始来源已有的字段来"排版简洁"（C09）；
- `status` 手写、`pass` 不看审计。

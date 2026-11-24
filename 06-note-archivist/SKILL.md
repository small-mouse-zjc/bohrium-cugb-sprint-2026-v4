---
name: note-archivist
description: 文献总结与结构化笔记。按论文自身章节逐节抽原文句成笔记（每句带精确字符偏移锚点，审计端能反查），汇总成六字段阅读卡片并逐字段挂 note_id 支撑；未报告的字段写 not_reported 而不是编造。
---

# note-archivist

把一篇论文变成**能反查的逐节笔记 + 有据的阅读卡片**。核心约束只有一条：笔记里的每个句子都是原文切片，锚点是它在这份输入里的字符区间；审计脚本拿区间回原文切片比对，对不上就阻断。因此"笔记写得像不像原文"这件事不再靠自述，而是可以被第二个人一条命令复核。

## 什么时候用

- 拿到一篇（或一批）论文，需要"按它自己的章节"整理笔记，而不是套通用摘要模板；
- 需要把研究问题、数据、方法条件、主要发现、局限、前提假设做成可并排比较的卡片；
- 需要笔记能回到原文某节某段某字符位置，供他人核验或后续更新。

不适合：需要读懂图表像素内容、扫描件无文字层、需要跨文献综合评述（那属于综述任务，本 Skill 只做单篇结构化）。

## 输入

平台入口：`/input/case.json`（也兼容 `case.json`、`input/case.json`），可选 `/input/task.md`。

`case.json` 支持的三种形态（按优先级）：

1. `{"case_id": "...", "sections": [{"heading": "Methods", "page": 2, "text": "..."}]}` —— 最理想，章节与页码都由输入给定；
2. `{"case_id": "...", "pages": [{"page": 1, "text": "..."}]}` —— 按页给文本，脚本自行检测章节标题；
3. `{"case_id": "...", "text": "全文"}` —— 单段全文，脚本按行检测标题；检测不到就整篇当一节，并记 `no_section_headings` 不确定性。

也接受 `full_text` / `manuscript` 作为正文键，`title` / `name` / `content` / `paragraphs` 作为小节字段别名。字段缺失不猜内容，只记 `uncertainty`。

## 输出（`/app/output`）

| 文件 | 内容 |
|---|---|
| `result.json` | 主结果：`case_id`、`status`、`result.notes[]`、`section_alignment[]`、`reading_card`、`card_support`、`anchor_verification[]`、`artifacts`、`evidence[]`、`uncertainty[]`、`audit`、`metrics` |
| `notes.md` | 按章节组织的可读笔记，每条带 role 与 anchor |
| `reading_card.json` | 六字段卡片 + 每字段的 note_id 支撑 |
| `section_align.md` | 章节—笔记—锚点对照表与审计结论 |

### 单条笔记的字段

```json
{"note_id": "S3-N2", "section": "Materials and Methods", "section_index": 2, "role": "method",
 "quote": "Experiments were performed in a high-pressure cell at 12 MPa and 4 °C, ...",
 "anchor": "§3 ¶2 / p.2 [412-520]", "span": [412, 520], "page": 2, "para": 2}
```

`span` 是 `quote` 在 `doc.text`（由输入原样拼接而成）里的 `[start, end)`。`anchor` 是给人看的同一信息：节序 + 段序 +（有页码时）页码 + 字符区间。

六种 `role`：`problem` / `data` / `method` / `finding` / `limitation` / `premise`，其余句子记 `background`。

## 怎么跑

```bash
python scripts/run.py --input /input/case.json --output /app/output
```

`run.py` 自己完成：解析 → 逐节抽句 → 建卡片 → 审计 → 落盘 → 由产物判定 `status`。**不要手写 `result.json`**：`status` 与 `metrics` 都来自 `scripts/audit.py` 的实算结果。

单独复核（可交给第三方跑，不依赖生成过程）：

```bash
python scripts/audit.py   # 作为库：audit(result, doc) -> {blocking, advisory, rates, pass, codes}
python eval/metrics.py --result /app/output/result.json --case /input/case.json --base_dir /app/output/baseline
```

## 审计与阻断码

| 码 | 检查 | 含义 |
|---|---|---|
| N01 | `notes_too_short` | 结构化笔记 < 200 字符 |
| N02 | `section_count` | 笔记小节数与原文小节数不等 |
| N03 | `section_not_in_source` | 笔记小节名在原文找不到（自造章节） |
| N04 | `section_notes_empty` | 某节无笔记 |
| N05 | `section_anchor_empty` | 某节无锚点 |
| N06 | `card_field_empty` | 卡片六字段有空值（未报告应写 `not_reported`） |
| N07 | `anchor_unresolvable` | 笔记没有 span / quote，锚点无法反查 |
| N08 | `anchor_section_mismatch` | `text[span]` ≠ quote（偏移错），或引文落在别的小节 |
| N09 | `unsourced_numbers` | 笔记/卡片出现原文没有的数字 |
| N09b | `numbers_without_source_text` | 原文没有数字但笔记里有 |
| N10 | `note_not_verbatim` | 引文不是原文切片（复述/改写） |
| N11 | `card_field_unsupported` | 卡片字段没有 `card_support` |
| N11b | `card_support_unknown_id` | support 指向不存在的 note_id |
| N11c | `card_value_not_verbatim` | 卡片值不是原文句 |
| N12 | `section_without_note` | 原文某节一句笔记都没有 |

比率（`result.metrics`，分母为 0 一律 `null`，不写 1.00）：

`anchor_resolvability_rate`、`section_coverage_rate`、`verbatim_support_rate`、`card_support_rate`、`number_sourced_rate`。

`status` 判定：输入缺失/不可解析 → `rejected`；正文 < 50 字符 → `cannot_determine`；有阻断 → `needs_attention`；有字段 `not_reported` 或提示 → `partial`；全绿 → `success`。

## 方法要点

1. **句子边界用正则扫描而不是 `split`**：句子的 `start/end` 直接来自 `finditer`，`quote = text[start:end]`，从构造上保证逐字。
2. **角色靠标记词打分，不靠语义模型**：每类角色一组标记词（`we investigate` / `samples` / `performed` / `results show` / `limitation` / `assume`），加上"小节优先级"加成；同一节先覆盖不同角色，再按分数补足。
3. **卡片只搬运不复述**：每个字段取"角色匹配 + 小节优先级最高"的那条笔记，另挂一条跨节同角色笔记做对照；取不到就 `not_reported` 并进 `uncertainty`。
4. **审计与生成解耦**：`audit.py` 只吃 `result.json` + `case.json`，不 import 生成逻辑，任何人可独立复跑。

详见 `references/method.md`（抽取规则、角色标记表、锚点格式、审计判据）与 `references/output_contract.md`。

## 脚本查不了什么（盲区，必须人工或上层模型补）

- **图表/公式内的信息**：只处理文本层，图里的数值、公式符号不会被抽，也不会被 N09 覆盖（N09 只查文本里有没有这个数）。
- **双栏 PDF 被错误拼行**：本 Skill 不改行序；若输入本身是交错文本，笔记会忠实引用交错文本，正确但不可读，此时应记 `uncertainty` 并回到带版面信息的解析器。
- **章节语义切分**：无标题全文只按行特征检测，遇到"无编号、非大写、非规范名"的标题会漏；检测不到就降级为单节，不算错，但章节对齐只能做到全篇级。
- **笔记是否"重要"**：抽句是抽取式，覆盖与角色齐备，但不能判断这句话对该领域是否关键；需要更高层判断时，应由上层模型在 `quote` 之外另写解读，且解读不得混进 `quote`。
- **非英文/多语言**：角色标记表是英文词；中文/俄文论文仍能抽句与锚点（句子边界含 `。！？`），但角色会大量落到 `background`，卡片可能出现 `not_reported`。

## 依赖

Python 3.9+ 标准库（`re`/`json`/`argparse`）。无第三方包、无网络、无外部模型调用。

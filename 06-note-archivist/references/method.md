# 方法说明（06 note-archivist）

## 1. 输入的三种形态与偏移来源

`extract.build_doc(case)` 统一产出：

```python
doc = {
  "text": 原样拼接的全文（唯一事实来源）,
  "sections": [{"index", "heading", "start", "end", "body_start", "page"}],
  "paras":    [{"text", "start", "end", "section", "page"}],
  "warnings": [{"issue", "detail"}]   # 例如 no_section_headings / heading_missing
}
```

- `sections` 字段存在 → 小节名、正文、页码完全采信输入；
- 只有 `pages` → 按页拼接，字符偏移按页累计，`page` 随段落带上；
- 只有 `text` → `detect_sections()` 按行检测：`1 Introduction` / `2.3 Results` 这类编号标题，或 `Abstract|Introduction|Methods|Results|Discussion|Conclusion|Limitations|...` 这类规范名，或全大写短行。检测不到就把整篇当一节并记 `no_section_headings`（降级，不编造章节）。

`text` 的构造是 `heading + "\n" + body`，块间用空行连接；所有 `start/end` 都是在这份拼接字符串上的真实偏移——这是后面一切可复核性的前提。

## 2. 抽句：为什么用 `finditer` 而不是 `split`

```python
SENT_RE = re.compile(r"[^\n]{15,400}?(?:[.!?。！？](?=\s|$)|$)")
```

`sent = para_text[m.start():m.end()]`，即**句子字符串本身就是原文切片**。若改用 `split(".")` 再拼回，标点与空格会被改掉，`text[span] == quote` 立刻失效。长度门槛 30–240 字符，过滤标题行、公式行、残句。

## 3. 角色归类

| role | 标记词（节选） | 小节加成（示例） |
|---|---|---|
| problem | we investigate / this study / objective / research question / hypothes | Abstract、Introduction |
| data | sample(s) / dataset / core(s) / collected / n = / g wet | Methods、Results |
| method | performed / using / experiment / simulation / protocol / was carried out | Methods |
| finding | results show / indicat / suggest / observed / higher / lower / compared | Results、Discussion |
| limitation | limitation / caveat / cannot / does not / further work / remains unclear | Limitations、Discussion |
| premise | if / assuming / assume / under / provided that / only when | Methods、Discussion |

规则：同一句命中多类时，按 `(命中数降序, 偏好序)` 取一个 role；偏好序 `premise > limitation > method > finding > problem > data`——因为 `data` 最容易被 `12 MPa` 这类单位词误触发。数值单位（`wt%`、`MPa`、`°C`）**刻意不放进 data 标记**，避免把方法句全判成数据句。

每节 `per_section=3`（可由 `case.json.note_budget` 覆盖，1–6）：第一遍按"角色未出现"取高分句，第二遍补足；相距 <20 字符的句子视为同段重复，跳过。

## 4. 锚点格式

```
§{section_index+1} ¶{para_index} [/ p.{page}] [{start}-{end}]
例：§3 ¶2 / p.2 [412-520]
```

- `§/¶` 是人读定位（1 起），不受页码缺失影响；
- `p.N` 只在输入真的给了页码时出现，**不会凭空生成页号**；
- `[start-end]` 是机器定位，审计端用它切原文。

## 5. 卡片：只搬运，不复述

```python
ROLE_TO_FIELD = {problem→problem, data→data, method→method,
                 finding→findings, limitation→limitations, premise→premises}
SECTION_PRIORITY = {limitations: [limitation, discussion, conclusion], ...}
```

对每个字段：筛出该角色全部笔记 → 按"小节优先级 + 句内数值个数"排序 → 取第一条作为字段值，另挂一条**不同小节**的同角色笔记做跨节对照。字段值一定是某条笔记的 `quote`，因此 `card_value_not_verbatim`（N11c）不可能通过。

取不到该角色任何笔记 → 写 `not_reported`，同时进 `uncertainty`（如原文确实没写局限）。此时 `status=partial`，而不是把"无局限"伪装成结论。

## 6. 审计判据（可独立复跑）

`audit(result, doc)` 不 import 任何生成模块，只看 `result.json` 与 `doc`：

| 码 | 判据 |
|---|---|
| N07 | `notes[i]` 无 `span` 或无 `quote` |
| N08 | `span` 合法但 `text[s:e] != quote`（偏移错）；或 `quote` 落在 `section_index` 之外的小节 |
| N10 | `quote` 不是 `text` 的子串（复述/改写） |
| N09 | 笔记与卡片中出现的数字（排除 0–10、19xx/20xx 年份）不在原文数字集 |
| N11/N11b/N11c | 卡片字段无支撑 / 支撑 id 不存在 / 卡片值非原文子串 |
| N11d | 支撑笔记的 role 与字段要求的 role 不符（findings 不能只挂 data 句） |
| N13 | 字段有值，但笔记集合里没有该角色（值无角色来源） |
| N02/N03 | 小节数与原文不符 / 小节名归一化后不在原文 |
| N12 | 原文某节 `section_index` 无任何笔记 |

比率：

```
anchor_resolvability_rate = 通过 span+小节归属双检的笔记数 / 笔记数
section_coverage_rate     = 有笔记的小节数 / 原文小节数
verbatim_support_rate     = quote 是原文子串的笔记数 / 笔记数
card_support_rate         = 有支撑的已填字段数 / 已填字段数（全 not_reported 时为 null）
number_sourced_rate       = 有源数字数 / 笔记与卡片出现的数字数
role_coverage_rate        = 出现的六类 role 数 / 6
```

分母为 0 一律 `null`。

## 7. 三个已知盲区

1. **版面**：双栏 PDF 若被上游拼成交错行，抽句会忠实引用交错文本（N07 全绿也可能读不懂）。本 Skill 不重排版式，只在 `uncertainty` 里提示。
2. **图表/公式**：文本层之外的信息不抽取；N09 只保证"出现的数字在原文有"，不保证"原文所有数字都被记下"。
3. **重要性判断**：抽取式笔记覆盖角色与章节，但无法判断某句在该领域的分量；需要解读时应由上层模型另写，且不得混入 `quote`（否则 N10 直接拦下，这是刻意的）。

## 8. 数字比对口径（为什么不是"排除 0–10"）

- 结构数字（章节号 `Section 2`、图号 `Fig. 3`、年份 `2020`、页码）不计；
- 但带单位/量词/前缀的小数字是**数据**，必须计入：`12 MPa`、`3 samples`、`n = 4`、`重复 3 次`、`共 30 个样品`、`3.5 wt%`。
- 否则 `n = 7` 这种编造的小样本量会被"0–10 排除"规则放过，`number_sourced_rate` 也会虚高。

## 9. 自检覆盖（27 条）

正例两率、N01–N12 全部注入（含 N08 偏移错一位、N08b 引文进错节、N11b/N11c）、无标题全文降级、正文过短 → `cannot_determine`、缺 case.json → `rejected`、空集比率 None、基线对照（五率差值 + 阻断码 + N09 值表）。

---
name: atomic-assertion-nanopub-export
description: 把论文结论拆成"一句一断言"，每条绑逐字证据，导出为 JSON-LD + TriG 四层结构（assertion/provenance/pubinfo/命名图）并立刻回解析校验，产出可机器判断真假、可回原文核对的结构化结论集。用于"结论要可复核、不能是整段摘要"的文献知识抽取任务。
---

# 一句一断言 + 标准序列化的结论集

## 0. 这个 Skill 只做一件事

把一篇文献的结论变成**原子断言集合**：每条只有主体-关系-客体-限定，每条都有**逐字原文引文**与段落号，导出成四层 JSON-LD/TriG，并当场回解析证明结构可读。

不做：整段摘要、综述、翻译、文献推荐、RDF 推理与签名发布。遇到这些请求直接说明超出范围。

## 1. 何时触发

触发：用户要求"把结论结构化""抽取三元组/断言""可核对的 knowledge graph""导出 JSON-LD/TriG/Nanopub"中的任意一项。
不触发：只要摘要或要点列表、只要 Markdown 表格、要求自由发挥的综述写作。

## 2. 输入与输出

输入（平台约定 `/input/`）：`materials/*` 原文（PDF/XML/纯文本）、`case.json`、`task.md`。
先用 `scripts/nanopub.py` 之前，**自己**把原文段落整理成：

- `sources.json`：`{sources:[{source_id, paragraph_id, text}]}`（`paragraph_id` 用 JATS 段落号，无则自定稳定编号，**不要编页码**）
- `assertions.json`：`{case_id, paper:{title,year,doi|doi_reason}, assertions:[...]}`

输出（`/app/output/`）：

| 文件 | 内容 |
|---|---|
| `result.json` | 契约字段 `case_id` + `status` + `artifacts` + `metrics`，**由 `scripts/run.py` 产出**（数字取自 `validation.json`） |
| `assertions.json` | 校验后的断言清单（含 `evidence` 与 `confidence/derivation`） |
| `nanopub.jsonld` | `@context` + 四层结构 |
| `nanopub.trig` | 每条断言一个命名图 |
| `validation.json` | 原子率/逐字率/来源率/回解析 + 逐条违规码 |

`status` 只能取 `success / partial / cannot_determine / rejected`，全部由 `scripts/run.py` 按产物判定：`success` 需 `pass=true`、断言 ≥3 条、TriG 回解析成功；有违规 → `partial`；缺断言文件 → `rejected`。

## 3. 流程（4 步）

**第 1 步 拆断言（你来做）**
一句一断言。判据：切句后只有 1 句；不含 `并且/而且/以及/；/and/此外`；主体与客体不同且都非空。
"约/可能"不进主句：写进 `qualifier`，或 `derivation=inferred`。

**第 2 步 绑逐字证据（你来做）**
`evidence.quote` 必须从原文**复制粘贴**，不改字、不合并两句、不用省略号。长度 10–400 字符，且必须包含主体或客体的表面形式。

**第 3 步 机器校验 + 导出（脚本，必跑）**
```
python scripts/nanopub.py build --assertions work/assertions.json --sources work/sources.json --out /app/output
```
违规码：N01 非原子、N02 引文非连续子串、N03 长度越界、N04 证据不含主体/客体、N05 来源不全、N06 关系词越界、N07 重复断言、N08 回解析不一致。

**第 4 步 修到全绿再交付**
逐条修 `validation.json` 的违规后重跑；任一硬指标 < 1.00 时 `status` 最多 `partial`，并在 `result.json` 写清剩余问题。

## 4. 关系词表（封闭 10 个）

`increases / decreases / supports / contradicts / uses / measured_by / located_in / composed_of / exceeds / has_value`
需要新关系时，在 `assertions.json` 顶部写 `relation_extensions`，`nanopub.py` 会真实并入受控词表，不许临时造词。

## 5. 预算与降级（64 请求 / 900 秒 / 单次 16384 tokens）

- 优先级：证据逐字 > 原子性 > 覆盖条数 > 关系词丰富度。
- 长文先抽 `Results / Conclusions`，再抽 `Methods` 中的关键条件；每抽 20 条落盘一次。
- 剩余请求 < 8 时停止新增，转第 3 步校验并交 `partial`。

## 6. 异常处置

| 情况 | 处置 |
|---|---|
| 断言跨两段 | 拆成两条，各绑各自段落；不许跨段拼接引文 |
| 结论只在图/表里 | 不编造引文；`status=partial`，写 `uncertainties="结论位于图表，正文无对应句"` |
| 扫描件无文字层 | 不猜；`cannot_determine` + 建议 OCR |
| 同一结论多篇支持 | 每篇一条断言，`derivation=direct`，不合并成"多篇一致" |
| 方向存疑（增/减不明） | `derivation=inferred` + `confidence=low`，`qualifier` 写明依据 |

## 7. 自检
```
python examples/selftest.py
```
注入 4 类缺陷（并列句、改写证据、缺段落号、重复断言），要求全部命中；未命中即校验器失效。

## 8. 边界

- 不做数字签名，不声称已发布到 Nanopub 网络。
- 不伪造 DOI、页码、引文。
- 回解析通过只证明结构可读，不证明结论为真。

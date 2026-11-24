---
name: glossary-locked-bilingual-translation
description: 把一篇真实文献切成带稳定编号的段落，先锁死术语表再逐段翻译，输出段落级双语对照与可机器复核的质检报告（术语一致率、段落覆盖率、数字/引用保真率）。用于"术语必须全篇统一、译文必须能指回原文"的文献翻译任务。
---

# 术语锁定的段落级双语对照

## 0. 这个 Skill 只做一件事

把**一篇文献**变成**段落级双语对照**：每个源段落有稳定编号与页码定位，每个目标段落都能回指它，术语在全篇强制统一，最后给出可计算的质检报告。

不做：全文润色、摘要、扩写、读后感、多篇综述。遇到这类请求直接说明超出范围。

## 1. 何时触发

触发：用户要求翻译论文/文献/PDF/长文，且关注**术语统一**、**不要漏段**、**双语对照**、**译文可核对**中的任意一项。
不触发：单词查询、短句翻译、非文献类文本（合同/邮件/新闻）、要求"意译成一篇通顺中文"的改写任务。

## 2. 输入与输出

输入（按平台约定）：`/input/case.json`、`/input/task.md`，材料可能是 PDF、纯文本或已有段落 JSON。
读取前先 `python scripts/pdf_to_paras.py --in <材料> --out /app/work/paras.jsonl`，不要凭文件名猜内容。

输出（`/app/output/`）：

| 文件 | 内容 |
|---|---|
| `result.json` | 平台契约字段 `case_id` + `status` + `artifacts` + `metrics`，由 `scripts/run.py` 产出（指标取自 `qc.json`，不手填） |
| `bilingual.json` | 逐段结构：`id/page/section/source_span/source/target/terms/status/basis/risk` |
| `bilingual.md` | 人读版：`[P0001] p.2 §Results` 原文 / 译文 交叠排列 |
| `glossary.csv` | 锁定后的术语表：`source,translation,pos,occurrences,paragraph_ids,lock` |
| `qc.json` + `qc_report.md` | 质检结果，含四项比率与逐条违规 |

`scripts/run.py --input /input --output /app/output` 是平台入口；`status` 只能取 `success / partial / cannot_determine / rejected`，由产物判定：`qc.pass=true` 才 `success`，有译文未过门槛 `partial`，无文字层 `cannot_determine`，缺原文/`case.json` `rejected`。`case.json` 若给出 `output_contract`，以它为准，本文件字段作兜底。

## 3. 流程（5 步，禁止跳步）

**第 1 步 取段落（脚本，不靠模型切分）**
```
python scripts/pdf_to_paras.py --in <pdf|txt> --out /app/work/paras.jsonl
```
产出每段的 `id`（P0001 递增，**全篇唯一，翻译后不得重排**）、`page`、`bbox`、`col`、`section`。
PDF 无文字层（`chars_per_page < 50`）时脚本会置 `status=no_text_layer`，此时**停止翻译**并在 `result.json` 写 `status=cannot_determine`、`uncertainties` 说明需要 OCR，不许把空白页当正文。

**第 2 步 建并锁术语表（脚本 + 你判断）**
```
python scripts/glossary.py extract --paras /app/work/paras.jsonl --out /app/work/glossary_candidates.csv
python scripts/glossary.py lock --in <你填好的 glossary_candidates.csv> --out /app/output/glossary.csv
```
你必须为每个候选术语填**唯一译名**。`lock` 会拒绝：空译名、同一源术语两个译名、同一译名对应两个源术语（同义合并需你在 `note` 里写理由）。
规则：术语表一旦锁定，**后续所有段落必须逐字使用表内译名**，包括标题、图注、表头、结论。表外语汇按学科惯例译，并记入 `glossary.csv` 的 `lock=free` 行，便于复查。

**第 3 步 逐段翻译（你来做，脚本不做）**
按 `id` 顺序，每批 6–10 段一次请求，携带：该批原文、已锁定术语表、上一批末尾 2 段作为上下文、以及"不得改动编号"的约束。
每段必须产出：`target`（完整译文，不许写"同上""略"）、`terms`（本段实际用到的锁定术语）、`basis`（一句话译法依据，例如"按术语表锁定为'水合物稳定带'"）、`status`（`ok/uncertain/untranslatable`）。
原文中的数字、单位、公式、图表编号、文献标记（`[12]`、`(Wang et al., 2021)`、`Fig. 3`、`Eq. (2)`）**原位保留**，不做本地化改写。

**第 4 步 机器质检（脚本，必须跑）**
```
python scripts/qc.py --paras /app/work/paras.jsonl --bi /app/output/bilingual.json --glossary /app/output/glossary.csv --out /app/output
```
硬门槛（任一不满足，`status` 最多写 `partial`）：

| 指标 | 门槛 | 算法 |
|---|---|---|
| 段落覆盖率 | ≥ 0.98 | 有非空 `target` 的源段落 / 源段落总数；`status=untranslatable` 但保留原文片段的段仍计入（它是降级不是漏译） |
| 术语一致率 | = 1.00 | 段落内出现锁定术语时，译文含其锁定译名的比例；中文按最长匹配遮蔽，`天然气水合物` 出现处不再顺带要求 `水合物` 的译名 |
| 数字保真率 | ≥ 0.95 | 源段 `(数值, 紧邻单位)` 多重集与译文多重集的计数匹配比例：只查「数字出现过」会放过 3.5 wt% ↔ 4 °C 互换和重复数值丢一份 |
| 引用标记保真率 | = 1.00 | `[n]`/`Fig.`/`Table`/`Eq.` 标记保留比例 |
| 未确定标注率 | = 1.00 | `status != ok` 的段落必须带 `risk` 说明 |
| 译法依据覆盖率 | ≥ 0.90 | 非空 `target` 且 `status != untranslatable` 的段落含非空 `basis` 的比例（契约必填字段，缺了无法核「凭什么这么译」） |

**第 5 步 回填与交付**
把 `qc.json` 的 `violations` 逐条修掉（缺译名就差术语表、漏段就补译、丢数字就补回），再重跑第 4 步，直到过门槛或明确写清无法达标的原因。最后写 `result.json`，`metrics` 直接引用 `qc.json` 的数字，**不许手填**。

## 4. 预算与降级（64 请求 / 900 秒 / 单次 16384 tokens）

- 优先级：段落覆盖 > 术语一致 > 数字与引用保真 > 译文流畅。
- 长文超过 60 段时，先翻 `Abstract / Results / Conclusions`，再补 Methods，最后补 Related Work；每完成一批就落盘一次 `bilingual.json`，保证中断也有部分成果。
- 剩余请求 < 10 时停止新段落，转入第 4 步质检并交付 `partial`。

## 5. 异常处置

| 情况 | 处置 |
|---|---|
| 扫描件、无文字层 | `partial` + 指出页码 + 建议 OCR，不猜正文 |
| 双栏串行错乱（段落读起来是两栏拼接） | 先 `python scripts/pdf_to_paras.py --check-order` 看串栏警告，再用题 08 的列重排逻辑；仍错则在 `uncertainties` 标出受影响段落 |
| 公式/表格是图片 | 该段 `status=uncertain`，`risk=["公式为图片，未转写"]`，正文照译并保留编号 |
| 原文残缺、句子中断 | 该段 `status=untranslatable`，保留原文片段，不补写；该段不计入术语/数字/引用/长度四项译文保真比对（片段本身是源语言），覆盖率仍计入 |
| 参考文献只有编号无条目 | 保留 `[n]` 标记，`uncertainties` 记录"条目缺失，未核对" |

## 6. 自检

```
python examples/selftest.py
```
自检共 **15 条**。除三类注入缺陷（术语漂移、整段漏译、数字与引用丢失）外，还锁四类「存在性检查/口径偏差抓不到」的错：

- **数值互换**：把 P0002 的 `3.5 wt%` 与 `4 °C` 对调，数字与单位一个不少，`number_preservation` 掉到 0.94、报 `number_unit_mismatch`（硬违规）→ `pass=false`；
- **`basis` 全删**：12 段 `missing_basis`、`basis_coverage=0.00` → `pass=false`；
- **降级段口径**：`status=untranslatable` + 非空原文片段仍计入覆盖率（1.00），且不参与术语/数字/引用/长度比对（片段是源语言原文，参与比对必然误判），只受 `risk` 与 `basis` 约束；
- **父子术语**：术语表同时有 `天然气水合物` 与 `水合物` 时，只出现长术语的段落不误判 `term_drift`（遮蔽式最长匹配）。

未命中即视为质检器失效，不得提交。

## 7. 边界

- 不生成"看起来像译文"的摘要来冒充全文。
- 不为了让句子通顺而增删事实、数字、限定条件。
- 术语表是**强制约束**，不是提示词建议；表外自由译法必须留痕。

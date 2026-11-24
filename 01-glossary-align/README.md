# 01 · 术语锁定的段落级双语对照

**一句话**：把一篇文献切成"编号不可变"的段落，先锁死全篇术语表，再逐段翻译，最后用脚本算出五项可复算的质检比率——术语必须全篇统一，译文必须能指回原文。

这个包只做这一件事。不做摘要、不做润色、不做扩写、不做整篇综述；遇到这类请求直接说明超出范围。

---

## 1. 为什么是这个单点

基础 Agent 在真实文献翻译上有四个可反复观察到的失败，且互相独立：

1. **术语漂移**：`gas hydrate` 在标题译"天然气水合物"、正文译"气体水合物"、图注又译"水合物"，同一篇文献三种译名。
2. **段落不全**：跨页、跨栏、跨章节时漏段或重复，读者拿不到完整正文。
3. **事实被改写**：数字、单位、公式编号、文献标记被"顺手"本地化或省略。
4. **不可核验**：译文说得通，但指不回原文哪一段、哪一句，也没写译法依据。

v1/v2 的教训是功能摊得太宽——术语、摘要、问答、润色、图表说明都做了一点，每项都停在"看起来能用"。评分看的是**可验证的改善**，摊大饼反而拿不到任何一项的满分。v3 因此只保留"术语一致 + 段落完整 + 可核验"这一条主链，并把它做成可执行、可复算的管线。

## 2. 交付物

| 文件 | 内容 | 谁生成 |
|---|---|---|
| `result.json` | 平台契约字段 `case_id` + `status` + `artifacts` + `metrics`。**由 `scripts/run.py` 产出**，指标从 `qc.json` 拷，不手填 |
| `bilingual.json` | 逐段结构：`id/page/section/source_span/source/target/terms/status/basis/risk` | 模型（翻译） |
| `bilingual.md` | 人读版：`[P0001] p.2 §Results` 原文/译文交叠 | 脚本 |
| `glossary.csv` | `source,translation,pos,occurrences,paragraph_ids,lock` | 脚本 + 模型填译名 |
| `qc.json` / `qc_report.md` | 五项比率、逐条违规、门槛判定 | 脚本 |

`status` 只取 `success / partial / cannot_determine / rejected`，并在 `result.json` 写清原因与可人工接管的位置。若 `case.json` 给了 `output_contract`，以它为准。

## 3. 管线（5 步，脚本与模型分工固定）

**第 1 步 取段落（脚本，不靠模型切分）**

```
python scripts/pdf_to_paras.py --in <pdf|txt> --out /app/work/paras.jsonl
```

- 读取顺序 `fitz`（PyMuPDF）优先，`pypdf` 兜底，纯文本直读；
- 双栏按 x 坐标分带，先左栏整栏再右栏，避免"左栏末句接右栏首句"；
- 页眉页脚按"上下 7% 区域 + 跨页重复"剔除，并记入 `dropped`；
- 行末连字符拼接（`micro-` + `structure` → `microstructure`）；
- 段号 `P0001` 递增，**翻译后不得重排**。

分工理由：切段是确定性工作，模型做会不稳定（同一 PDF 两次切出不同段数），而段号一旦漂移，后面所有回指都失效。

**第 2 步 建并锁术语表**

```
python scripts/glossary.py extract --paras /app/work/paras.jsonl --out /app/work/glossary_candidates.csv
python scripts/glossary.py lock --in <填好译名的候选表> --out /app/output/glossary.csv
```

`extract` 收三类候选：全大写缩写、反复出现的名词短语、括号内定义的术语。`lock` 强制三条规则，任一违反即拒绝写入：

- 译名为空；
- 同一源术语出现两个译名；
- 同一译名对应两个源术语（同义合并必须在 `note` 写理由）。

**术语表是强制约束，不是提示词建议**：锁定后所有段落逐字使用表内译名，标题、图注、表头、结论一视同仁；表外语汇按学科惯例译，并记 `lock=free` 行留痕。

**第 3 步 逐段翻译（模型做，脚本不做）**

按 `id` 顺序，每批 6–10 段，携带：本批原文、已锁定术语表、上一批末 2 段作为上下文、以及"不得改动编号"的约束。每段必须给：

- `target`：完整译文，不许"同上""略"；
- `terms`：本段实际用到的锁定术语；
- `basis`：一句话译法依据；
- `status`：`ok / uncertain / untranslatable`。

数字、单位、公式、图表编号、文献标记（`[12]`、`(Wang et al., 2021)`、`Fig. 3`、`Eq. (2)`）**原位保留**。

**第 4 步 机器质检（脚本，必须跑）**

```
python scripts/qc.py --paras /app/work/paras.jsonl --bi /app/output/bilingual.json \
  --glossary /app/output/glossary.csv --out /app/output
```

**第 5 步 回填**

按 `qc.json` 的 `violations` 逐条修（缺译名→补术语表；漏段→补译；丢数字→补回），重跑第 4 步直到过门槛，或明确写清无法达标的原因。`result.json` 的 `metrics` 只允许引用 `qc.json` 的数字，不许手填。

## 4. 质检口径

| 指标 | 定义 | 门槛 |
|---|---|---|
| 段落覆盖率 | 有非空 `target` 的源段落 / 源段落总数 | ≥ 0.98 |
| 术语一致率 | 段落出现锁定术语时，译文含其锁定译名的比例 | = 1.00 |
| 数字保真率 | 源段 `(数值, 紧邻单位)` 多重集与译文多重集的计数匹配比例（防数值互换、防重复数值丢失） | ≥ 0.95 |
| 引用标记保真率 | `[n]` / `Fig.` / `Table` / `Eq.` 标记保留比例 | = 1.00 |
| 未确定标注率 | `status != ok` 的段落必须带 `risk` 说明 | = 1.00 |

任一硬门槛不满足，`status` 最多写 `partial`。

## 5. 实测证据（自建演示材料，非平台案例）

`examples/demo/source.txt` 是一篇 7 段正文 + 5 个章节标题的水合物文献式样文本，`examples/expected/` 是真实跑出的产物：

- **12 段（7 正文 + 5 章节标题）全部有译文**，覆盖率 1.00；标题用 `H00n` 编号单独成段，不再被静默丢弃；
- 抽出并锁定 **16 条术语**，执行 **35 次术语检查**，一致率 1.00；
- **33 个数字标记**、**7 处引用标记**全部原位保留，两项保真率均 1.00；
- 未确定段全部带 `risk`，标注率 1.00；
- `qc.json` 的 `failed`、`violations`、`hard_violations` 均为 0，`pass=true`。

缺陷注入自检（`python examples/selftest.py`）要求质检器对三类人为破坏全部命中，否则视为质检器失效、不得提交：

| 注入 | 预期 |
|---|---|
| F1 术语漂移（把一段的锁定译名换掉） | 报术语不一致 |
| F2 整段漏译（删掉一段 `target`） | 报覆盖率不足 |
| F3 数字与引用同时丢失 | 同时报 `number_lost` 与 `citation_lost` |

自检 **16 条**断言全绿。除三类注入外，重点锁两条「存在性检查抓不到」的错：**数值互换**（`3.5 wt%` ↔ `4 °C` 对调，数字与单位一个不少，`number_preservation` 掉到 0.94 并报硬违规 `number_unit_mismatch`）与 **`basis` 全删**（12 段 `missing_basis`、`basis_coverage=0.00`，`pass=false`）。第二轮再补两条口径修正：**降级段口径**（`untranslatable` + 非空原文片段仍计入 coverage，且豁免术语/数字/引用/长度四项比对）与**父子术语遮蔽**（只出现 `天然气水合物` 时不误判 `水合物`）。另覆盖：平台入口（`case.json → result.json`，12 段含 5 标题）、缺译文草稿时 `status=partial`、硬违规卡 `pass`（`number_unit_mismatch` + `dup_target` 同时命中时 `hard_violations>0`、`pass=false`）、基线对照（Skill `pass=true` vs 基线 `pass=false`，术语一致率差 +80.00%）、缺 `qc.json` 的基线段记 `None` 而不崩溃。演示输入是纯文本，`paras.jsonl.meta.json` 明确记录 `warnings: 纯文本输入无版面信息，页码为估算`——不把估算页码当真实页码。

**上岗入口**：`python scripts/run.py --input /input --output /app/output`。它读 `case.json` 的 `source / glossary / bilingual`（字段名容错），依次跑取段 → 术语锁定 → 质检，写 `result.json`；`status` 由实际产物判定：`success` 需 `qc.pass=true`；有译文但未过门槛为 `partial`；无文字层为 `cannot_determine`；缺原文/`case.json` 为 `rejected`。**没有译文草稿时不冒充成功**，只交 `paras.jsonl` 与 `glossary.csv` 并写 `partial`。

## 6. 异常与降级

| 情况 | 处置 |
|---|---|
| 扫描件、无文字层（PDF 每页均字符 < 50，或纯文本近乎为空） | `status=cannot_determine`，指出页码，建议 OCR，不猜正文 |
| 双栏串行错乱 | 先 `--check-order` 看串栏警告，再借用 08 的列重排逻辑；仍错则在 `uncertainties` 标受影响段落 |
| 公式/表格是图片 | 该段 `status=uncertain`，`risk=["公式为图片，未转写"]`，正文照译并保留编号 |
| 原文残缺、句子中断 | `status=untranslatable`，保留原文片段，不补写 |
| 参考文献只有编号无条目 | 保留 `[n]`，`uncertainties` 记"条目缺失，未核对" |
| 长文 > 60 段 / 请求预算不足 | 先 Abstract/Results/Conclusions，再 Methods，最后 Related Work；每批落盘；剩余 <10 请求转质检并交 `partial` |

## 7. 快速开始

```bash
# 0) 平台一键（读 /input/case.json，写 /app/output/result.json）
python scripts/run.py
# 1) 抽段
python scripts/pdf_to_paras.py --in paper.pdf --out work/paras.jsonl
# 2) 抽术语候选（人工填唯一译名）
python scripts/glossary.py extract --paras work/paras.jsonl --out work/candidates.csv
python scripts/glossary.py lock --in work/candidates.csv --out output/glossary.csv
# 3) 逐段翻译，写 output/bilingual.json（字段见 SKILL.md）
# 4) 质检
python scripts/qc.py --paras work/paras.jsonl --bi output/bilingual.json \
  --glossary output/glossary.csv --out output
# 5) 自检
python examples/selftest.py
```

依赖：Python 3.10+、PyMuPDF（优先）、pypdf（兜底）；无网络依赖，不调用任何外部 API。

## 8. 目录结构

```
01-glossary-align/
├── SKILL.md                 # Agent 触发与执行契约
├── README.md                # 本文件
├── scripts/                 # pdf_to_paras.py / glossary.py / qc.py
├── references/method.md     # 方法说明与设计取舍
├── eval/                    # rubric.yaml / metrics.py / protocol.md
├── baseline/cases.md        # 对照口径与缺陷注入清单
├── examples/
│   ├── demo/                # 可复现的演示输入
│   ├── expected/            # 真实运行产物（qc.json 等）
│   └── selftest.py          # 缺陷注入自检
└── environment/resources.yaml
```

## 9. 换学科怎么改

1. 术语候选规则在 `glossary.py` 的抽取函数里，按学科加词缀/词性模式即可，不改 QC；
2. 术语表 CSV 列固定，可把已有双语术语库直接并进来（同名列合并，冲突行进 `lock` 拒绝）；
3. 门槛按任务严格度调 `qc.py` 的覆盖率下限，但**术语一致率与引用保真率不建议降到 1.00 以下**；
4. 新增指标（如"限定词保真率"）时，同时在 `eval/metrics.py` 与 `eval/rubric.yaml` 登记，避免自述与实测脱节。

## 10. 声明

- 演示材料为自建文本，**非平台固定案例**；
- 本包未在平台提交运行，不声称任何平台得分；
- 不伪造术语表、不伪造 QC 数字；所有比率可由 `qc.py` 从产物重算。

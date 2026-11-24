# 02 · 学术语言润色（academic-polish）

保源最小润色：只改表达，不改主张与事实。**包的核心不是"写得好"，而是"能机器证明事实没被改"。**

## 一句话

`python scripts/run.py --input /input --output /app/output` → `result.json` + `polished.md` + `audit.json` + `diff_audit.md`，`status` 由产物判定。

## 结构

```
02-academic-polish/
├── SKILL.md                       # 平台手册：输入 schema / 状态判定 / F01–F10 违规码 / 守恒表
├── scripts/
│   ├── run.py                     # 平台入口：case.json → 润色/审计 → result.json
│   ├── polish.py                  # 最小编辑引擎（只做安全替换，记录每条改动）
│   ├── facts.py                   # 事实标记抽取（数字+单位、引用、限定、否定、比较级、强断言）
│   ├── fact_ledger.py             # 逐句对齐 + 逐条改动核验（F01–F10 / A01–A05）
│   ├── term_check.py              # 术语一致性（T01）
│   └── guard.py                   # 结构校验（字段、产物存在性）
├── eval/
│   ├── metrics.py                 # 保留率 + 与基线差值（缺数据记 None）
│   ├── rubric.yaml / protocol.md
├── examples/
│   ├── demo/case.json             # 自建演示稿（非平台案例）
│   ├── baseline.py                # 裸 Agent 基线（丢单位、吞引用、反写否定）
│   ├── expected/                  # 真实 run 覆盖的 result/audit/polished/diff
│   └── selftest.py                # 14 条断言
├── references/output_contract.md
└── baseline/cases.md
```

## 关键设计

1. **两种执行模式**：`case.json` 给了 `polished_text` 就只审计不改写（`mode=llm`）；没给就由最小编辑引擎产出（`mode=minimal-edit`）。两条路径共用同一套台账。
2. **数字+单位成对比较**：`3.5 wt%` 与 `3.5%` 是两个不同标记，改单位判 F01；`0 to` 这类普通词不会被误当单位（STOP 表）。
3. **逐句一对一匹配**：源句与润色句用相似度做双射认领，每个润色句只能被一个源句占用，避免近义双句删除后被另一句顶替；`sentence_dropped`（F08）因此不再漏检。
4. **限定/否定按词边界计数**：`may/might/could/suggest/approximately` 数量减少即 F04；计数用 `(?<!\w)…(?!\w)` 边界，`may,` / `not;` / `significantly.` 这类紧跟标点的词同样计入。新增强断言（`found→proved`、`observed→demonstrated`）不论原文是否有 hedge 都触发 F05。
4. **改动必须可回指**：`changes.original` 要在原文里找得到，`revised` 要在润色稿里找得到；改了数字/引用必须 `fact_changed: true`，否则 F10。
5. **逐句对齐防偷句**：每句原文对润色稿做相似度对齐，<0.45 判整句丢失（F08），孤立的润色句判凭空加句（F09）。
6. **事实状态**：`kept/normalized/changed/removed/added` 五类，`fact_preservation_rate` 与 `fact_unchanged` 由脚本反推，"原文无需修改"不由 LLM 手填。
7. **零分母记 None**：原文没有数字/引用/限定词时，对应保留率 `None`，不写 1.00；`terms` 未给时术语一致率 `None`。

## 实测（demo，自建）

| 指标 | 本包 | 裸 Agent 基线 |
|---|---|---|
| number_retention | 1.0000 | 0.8571 |
| citation_retention | 1.0000 | 0.0000 |
| hedge_retention | 1.0000 | 0.0000 |
| negation_retention | 1.0000 | 0.0000 |
| fact_preservation_rate | 1.0000 | 0.6667 |
| status | success | pass=false（4 项阻断） |

自检：`python examples/selftest.py` → 36 条全绿（含强→强同义放行、近义双句删一句必报 F08）。

**加法侧补强（2026-11-25，评审指出"只抓删、不抓加"）**：旧实现只算 `neg_drop`/`cmp_drop`（删否定、删比较级），于是"把 *The hydrate layer thickens* 改成 *does not thicken*"（结论反转成反义）与"凭空加 *more than expected*"都是 0 阻断。现在补上同构的加法检查：`negation_added`（F06b）、`comparative_added`（F07b）；`fact_delta` 的软标记集合收窄为 `hedge/int`，`neg/cmp` 一律计入事实变化，所以"反转却声明 `fact_changed:false`"会被 F10 抓住，而 `can→may` 这类情态收敛仍不误报。

**本轮补强（2026-11-25，评审指出的强度红线漏洞）**：① F05 以前只在"删了弱词/推测词"时才判升级，于是"往中性句里塞 clearly"（没有弱词可删）与 `We observed → It is well known`（弱词仍在别处）都能全绿通过——现在改为 `strong_new and (hedge_drop or weak_drop or not strong_drop)`：新增强断言且没有对应的强断言被替换就阻断，`proved→demonstrated` 这类强→强同义替换仍放行；`STRONG` 补入 `well known / well-known / widely accepted / established fact / it is known` 等"断言为常识"型短语，`clearly / undoubtedly / definitively / certainly / conclusively` 同时纳入 `INTENSITY`（F12b 才抓得到凭空加的程度副词）。② 条目级 `fact_tokens` 以前只含数字+引用，`may → 无` 这类删减在 changes 清单里声明 `fact_changed:false` 也不被抓——现在把限定/否定/比较级/程度副词一并计入（`fact_delta()` 统一口径：丢任何事实标记或凭空多出数字/引用才算变了，单纯 `maybe can→may` 的情态规范化不算），F10 与句级"事实标记一致/有变化"共用同一判定，不再自相矛盾。自检相应 +5 条（32 条）。



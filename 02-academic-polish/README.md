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
3. **限定/否定按计数比**：`may/might/could/suggest/approximately` 数量减少即 F04；`may` 换成 `proves` 同时触发 F05。
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

自检：`python examples/selftest.py` → 18 条全绿。

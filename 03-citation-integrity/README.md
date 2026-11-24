# 03 · 引用管理（citation-integrity）

引用-文献闭环、去重干净、元数据真实可回查。包的核心是**编号连锁重排 + 元数据零编造**能被机器验证。

## 一句话

`python scripts/run.py --input /input --output /app/output` → `result.json` + `manuscript.md` + `bibliography.json` + `cite_chain.md`，`status` 由四方审计判定。

## 结构

```
03-citation-integrity/
├── SKILL.md                    # 输入 schema / 状态判定 / C01–C13 阻断码 / 指标
├── scripts/
│   ├── run.py                  # 平台入口：case.json → 重排/审计 → result.json
│   ├── renumber.py             # 重排引擎：首次出现排序、去重合并、claim 映射
│   ├── cite_chain.py           # 四方审计：正文↔文献表↔映射↔原始来源
│   └── guard.py                # 结构校验
├── eval/metrics.py             # 三项比率 + 基线差值（缺数据记 None）
├── examples/
│   ├── demo/case.json          # 自建演示稿（非平台案例）
│   ├── baseline.py             # 裸 Agent 基线（粗合并 / 留缺号 / 编 DOI / 删卷期）
│   ├── expected/               # 真实 run 的 result/manuscript/bibliography/cite_chain
│   └── selftest.py             # 25 条断言
└── references/output_contract.md
```

## 关键设计

1. **编号连锁重排**：新编号按正文首次出现顺序生成，正文标记与 `number_mapping` 同一次重写产出，杜绝"只改表不改文"。
2. **去重三条件**：作者姓+首字母、年份、标题规范化相似度 >0.9；**DOI 不同不合并**（C10 专门抓误并会议版/期刊版）。
3. **元数据逐字**：输出条目的每个字段与原始来源逐字段比对，缺值留空并进 `uncertainty`；填了原始没有的值即 C08，删掉原始有的值即 C09。
4. **claim 映射**：正文每句引用 → `claim_source_map`，未覆盖即 C11；`source_ids` 用新编号、`from_ids` 保留原编号。
5. **未引用条目**：不静默删除，写入 `unused` + `uncertainty`（A01）。
6. **author-year 风格**：正文 `(Smith et al., 2020)` 按"作者姓+年份"解析到 key，重写后仍可审计。
7. **零分母记 None**：无引用或无文献表时比率为 `None`。

## 实测（demo，自建）

| 指标 | 本包 | 裸 Agent 基线 |
|---|---|---|
| citation_closure_rate | 1.0000 | 1.0000 |
| metadata_verbatim_rate | 1.0000 | 0.8519 |
| claim_map_coverage | 1.0000 | 0.0000 |
| 阻断 | 无 | C02/C09/C10/C11 |

自检：`python examples/selftest.py` → 25 条全绿。

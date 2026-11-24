# 03 · 引用审计方法（可复现说明）

## 1. 引用解析

| 风格 | 正则 | 解析单位 |
|---|---|---|
| numeric | `\[(\d+(?:\s*[-–,]\s*\d+)*)\]` | `[3]`、`[2,4]`、`[5-7]` 展开为单个编号 |
| author-year | `\(([A-Z][A-Za-z\-]+)(?: et al\.| (?:&|and) [A-Z][A-Za-z\-]+)?,\s*(\d{4})\)` | 作者姓 + 年份 → 查文献表 key |

## 2. 去重判据（三条同时成立）

1. 作者姓与首字母一致（`Smith J.` → key `smith j`；`Smith J.` 与 `Smith R.` 不得合并）；
2. 年份一致；
3. 标题规范化（小写、去标点、去多余空格）后 `difflib` 相似度 > 0.9。

额外规则：
- 两条 DOI 都存在且不同 → **不合并**，记 `merge_conflict`（C10），并在 `uncertainty` 说明"会议版/期刊版"。
- 合并时保留非空字段更多的条目（`richer`），字段值逐字来自输入，不做拼接。

## 3. 编号重排

1. 扫描正文，按首次出现顺序收集 canonical 条目；
2. `new_id = order.index + 1`，正文标记同步改写（numeric 输出 `[n]`，author-year 输出 `(Name et al., year)`）；
3. `number_mapping` 记 `from_id → bib_id`，`claim_source_map.source_ids` 用新编号、`from_ids` 留原编号；
4. 未被引用的原始条目写入 `unused`（reason=`listed_not_cited`）与 `uncertainty`，不进新文献表。

## 4. 四方审计（`scripts/cite_chain.py`）

| 方 | 比对 |
|---|---|
| 正文 ↔ 文献表 | C01 悬空、C02 编号连续性、C03 首次出现顺序 |
| 文献表 ↔ 自身 | C04 重复残留、C05 key 冲突 |
| 映射 ↔ 正文/文献表 | C06 citation/bib_id/key 三方一致 |
| 文献表 ↔ 原始来源 | C07 条目不存在、C08 字段编造、C09 字段丢失、C10 DOI 不同被合并 |
| claim 映射 ↔ 正文 | C11 覆盖缺口 |

元数据逐字率：对每个输出条目按"作者+年份+标题>0.9"匹配原始条目，逐字段（作者/年份/标题/来源/DOI/卷期/页码/出版者/URL）比较；空对空算一致，空填值记 C08，有值删空记 C09。

## 5. 盲区（写进 `uncertainty`）

- **同名不同文献**：作者姓与年份相同、标题相似的完全不同论文，可能被误合（相似度阈值只能降误报，不能归零）；
- **预印本与正式版**：DOI 不同但实为同一工作的两个版本，按规则不合并，需人工决定；
- **元数据真伪**：脚本只能核对"与输入是否一致"，不能验证该文献是否真实存在（需要外部数据库检索）。

## 6. 复跑

```bash
python scripts/run.py --input examples/demo --output /tmp/o3
python examples/baseline.py --case examples/demo/case.json --out /tmp/b3
python eval/metrics.py --out_dir /tmp/o3 --base_dir /tmp/b3
python examples/selftest.py
```

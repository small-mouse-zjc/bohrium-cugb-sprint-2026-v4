# note-archivist（06 文献总结与结构化笔记）

把论文变成**逐节、逐句带偏移锚点**的笔记与六字段阅读卡片，并用一套能独立复跑的审计证明"笔记确实对得上原文"。

## 30 秒上手

```bash
python scripts/run.py --input /input/case.json --output /app/output
python examples/selftest.py          # 27 条断言
```

产物：`result.json`、`notes.md`、`reading_card.json`、`section_align.md`。

## 它解决的问题

常见失败是"通读摘要"：套四段模板、复述不引用、锚点写"全文"、缺局限、补一堆原文没有的数字。本 Skill 把四件事变成可机器判定的：

| 题面关注点 | 本作品做法 | 判定方式 |
|---|---|---|
| 对得上（章节骨架） | 小节名与顺序直接取自输入或从文本检测，不自造 | N02 / N03 / N12 |
| 留得住（要素齐备） | 每节按 role 抽句，卡片六字段必须有物 | N04 / N06 / N11 |
| 找得回（可回原文） | 每句带 `span=[start,end)`，`quote==text[span]` | N07 / N08 / N10 |
| 用得上（可复核复用） | `audit.py` 与生成逻辑解耦，任何人对同一 `result.json` 复跑 | 全部码 |

## 结构

```
scripts/extract.py   输入 → 带偏移的章节/段落文档（三种输入形态 + 标题检测降级）
scripts/notes.py     逐节抽句、角色归类、锚点生成、section_alignment 渲染
scripts/card.py      六字段卡片（只搬运原文句 + 挂 note_id 支撑）
scripts/audit.py     N01–N12 审计、五项比率、markdown 报告
scripts/run.py       平台入口：/input/case.json → /app/output/result.json（status 由审计判定）
eval/metrics.py      真跑 vs 基线差值表（缺数据 None）
examples/baseline.py 裸 Agent 基线（模板四节 + 复述 + 假锚点 + 编数字）
examples/demo/       自建演示案例（非平台案例）
examples/expected/   真跑产物快照 + 指标表
```

## 实测（自建演示案例，非平台分数）

| 指标 | 本 Skill | 裸 Agent 基线 | 差值 |
|---|---|---|---|
| 锚点可反查率 | 1.0 | 0.0 | +1.0 |
| 章节覆盖率 | 1.0 | 0.0 | +1.0 |
| 逐字支撑率 | 1.0 | 0.0 | +1.0 |
| 卡片有据率 | 1.0 | 0.6667 | +0.3333 |
| 数字有源率 | 1.0 | 0.5 | +0.5 |
| 六角色覆盖率 | 1.0 | 0.0 | +1.0 |

基线阻断码：N01/N02/N03/N06/N07/N09/N11/N12（模板四节与原文 6 节不符、复述句无锚点、卡片编造"30 个样品 / 重复 3 次"）。

## 边界（脚本查不了什么）

图表与公式内容、双栏错序的版面修复、无标题文本的语义切分、"这句话是否领域关键"——都不在本 Skill 能力内；遇到时写进 `uncertainty`，不写成事实。详见 `SKILL.md` 与 `references/method.md`。

## 依赖与许可

Python 3.9+ 标准库；无网络、无第三方包、无外部模型调用。可整包复制复用。

# 真实输出 2 — 证据定位式提问（本次方法）

> 模型：WorkBuddy（Tencent Hunyuan Hy），2026-11-25 本会话内生成。
> 输入：`inputs/excerpts.md` 全部 7 段带页码片段；提示词见 `prompts/02-evidence-first.md`。
> 以下为原样输出，未经润色。

---

## 1. 分变量、分算例的加速数值表

| 对象 | case A | case B | 依据 |
| --- | --- | --- | --- |
| ECLIPSE 300 平均模拟时间 | ~223 mins | ~140 mins | `ECLIPSE 300 average simulation time is ~223 mins for case A and ~140 mins for case B.` (p15) |
| 压力场 DMDc 最大重建时间 | ~1.28 mins | ~1.4 mins | `the largest pressure DMDc time is ~1.28 mins and ~1.4 mins for case A and case B` (p15) |
| 饱和度场 DMDc 最大重建时间 | ~33 mins | ~31 mins | `saturation time is ~33 mins and ~31 mins for case A and case B` (p16，跨页续句) |

摘要的「from several hours to minutes」(p1) 是上述结果的概括，不是单一数值。注意 p15 的句子在 `while the largest` 处断页，饱和度数字落在 p16。

## 2. 压力与饱和度不是一个量级

以 case A 为例：223 / 1.28 ≈ 174 倍；223 / 33 ≈ 6.8 倍。case B：140 / 1.4 = 100 倍；140 / 31 ≈ 4.5 倍。
即压力场是百倍量级，饱和度场只有个位数到十倍量级。把两者合并说成「数小时到数分钟」会掩盖这一差异 (p15, p16)。
注：这里的除法是我基于 p15 两个原始数字做的算术，不是论文直接给出的比值。

## 3. 本文结果 vs 文中引用的他人结果

- **本文**：油藏模型 `over 130,000 cells` (p1)，p36 复述 `more than 130,000 cells mesh and is highly heterogeneous`。
- **引文**：`The computation time of one million grid blocks drops from 6766 to 177 seconds and from 279 to 28 seconds for one hundred thousand grid blocks [20]` (p3，文献综述)。这是作者引用文献 [20] 的 CRM/前人工作数字，**不是本文 DMD 模型的结果**，与 p15–p16 的结果章节相隔十余页。
- 混淆风险：两者都出现「十万级网格」和「秒/分钟级时间」，若只把检索到的片段喂给模型而不带页码与 `[20]` 标号，很容易把 279→28 秒写成「本文把 10 万网格从 279 秒降到 28 秒」。本次核查第一次就踩了这个页码错误，修正过程见 `verification/check-record.md`。

## 4. 成立条件

| 条件 | 值 | 依据 |
| --- | --- | --- |
| 工况 | case A 单井注入；case B 注入 + 采水保压 | p8, p36 |
| 初始温度 / 压力 | 56 °C / 241 bars | p8 |
| 时间步 | 5200 个 7 天（周）Δt 步长；780 个注入/生产时间步 | p8 |
| 模拟跨度 | 注入 15 年 + 关井监测 85 年 = 100 年 | p1, p12 |
| 训练数据 | ECLIPSE 300 的 runs 2, 5, 7, 10 分别独立训练 | p12 |
| 验证方式 | 与「未参与训练」的 run 的原始快照对比 | p12 |
| 训练时间尺度 | weekly / monthly / yearly 三种压力与饱和度场 | p1, p16 |
| 对比对象 | ECLIPSE 300（原文 Table 1 / A2 / A3） | p15, p16 |

## 5. 未验证 / 局限（作者自述）

- `to make the procedure we suggest in this study more reliable, it needs to be applied to multiple reservoirs.` (p36) —— 只在**一个**高度非均质海上油藏模型上验证，未推广到多个油藏。
- `having restrictions during optimization, e.g., surface facilities and injectivity might lead to differences ... This may cause DMD to have lower accuracy and, therefore, needs to be investigated further.` (p36) —— 存在地面设施/注入能力约束时精度可能下降，作者明确列为待研究。
- 片段未提供：DMDspc 各时间尺度的逐项数值、误差指标的具体数值（这些在 Table A2/A3，本次摘录未包含），故不报告。

## 6. 只依据 p1 摘要会丢掉什么

会丢掉：①压力与饱和度加速比相差一个数量级；②case A/B 的分组与各自基准耗时；③「>130,000 cells」与引文「100,000 grid blocks」的来源区分；④5200/780 时间步、56 °C/241 bars 等实验设置；⑤训练用 runs 2/5/7/10、用未训练 run 验证这一泛化前提；⑥作者自述「仅单油藏、需多油藏验证」与注入约束下的精度风险。摘要给出的是方向性结论，正文给出的才是可照着复现的条件。

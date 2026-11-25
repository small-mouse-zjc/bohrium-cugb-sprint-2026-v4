# 逐条原文核查记录

核查方式：用 PyMuPDF 打开 arXiv:2407.20541v4 的 49 页 PDF，对下表每条引句在标注页做字符串比对；机器结果见 `verification/result.json`，真实运行日志见 `run.log`。人工复核结论写在「判定」列。

| # | 核查点 | 标注页 | 引句（片段） | 判定 |
| --- | --- | --- | --- | --- |
| 1 | 摘要的笼统表述 | p1 | `from several hours to minutes` | 命中。该句确在 p1，且未给分变量数值 |
| 2 | 本文网格规模 | p1 | `over 130,000 cells` | 命中。p36 复述 `more than 130,000 cells mesh` |
| 3 | 初始条件与时间步 | p8 | `56oC and 241 bars`、`5200 seven days`、`780 injection/production` | 均命中 p8 |
| 4 | 训练 / 验证划分 | p12 | `we used ECLIPSE 300 runs 2, 5, 7, and 10 individually` | 命中 p12；同页含 `780 time steps or 15 years` 与 100 年模拟跨度 |
| 5 | ECLIPSE 基准耗时 | p15 | `~223 mins for case A and ~140 mins for case B` | 命中 p15 |
| 6 | 压力 DMDc 耗时 | p15 | `~1.28 mins and ~1.4 mins` | 命中 p15 |
| 7 | 饱和度 DMDc 耗时 | p16 | `~33 mins and ~31 mins` | 命中 p16；句子自 p15 末 `while the largest` 跨页续来，行首 `16` 是页脚页码混入 |
| 8 | 引文数字来源 | p3 | `279 to 28 seconds for one hundred thousand grid blocks [20]` | 命中 p3 文献综述，带 `[20]` 标号，确为引文而非本文结果；与结果章节相隔十余页 |
| 9 | Table 1 标题 | p16 | `Average reconstruction times across forecast DMDc and DMDspc models` | 命中 p16，确认分 pressure / CO2 saturation 与 weekly/monthly/yearly |
| 10 | 平均值交叉验证 | p36 | `Average saturation times are 31.61` | 命中 p36；与片段 4b 的 ~31–33 mins 量级一致，可交叉验证 |
| 11 | 作者自述局限 | p36 | `it needs to be applied to multiple reservoirs` | 命中 p36；同页含 injectivity 约束下精度可能下降的表述 |

## 核查发现

1. 两次输出的差异不是「对错」而是**信息粒度**：Baseline 复述了摘要，证据定位式补上了 p8/p12/p15/p16/p36 的成立条件。
2. 最容易出错的是第 8 条：p3 文献综述的 `279 to 28 seconds` 与 p1 的 `>130,000 cells` 数字形态相近，若只把检索片段喂给模型而不带页码与 `[20]` 标号，极易张冠李戴。核查确认该句带 `[20]` 且远在结果章节之前。
3. 第 6/7 条确认「分钟级」对压力场是 ~1.3 分钟（p15）、对饱和度场是 ~31–33 分钟（p16），同属「分钟」但加速比差约一个数量级。这是摘要压缩损失最大的地方。

## 真实修正记录（本次实践的一部分，不是事后粉饰）

`reproduce.py` **第一次运行结果是 9/11**：`p15-saturation` 与 `p15-citation` 两条未命中。逐页回查后发现两处都是**我手工转录时的页码误标**，不是 PDF 内容有误：

- `~33 mins and ~31 mins` 实际在 **p16**，因为原句从 p15 末尾 `while the largest` 跨页；PDF 提取还把页脚 `16` 混进了正文行首，形成 `16 saturation time ...`。
- `279 to 28 seconds` 实际在 **p3 文献综述**，我凭「看起来像结果」误标成了 p15。

修正动作：把两条检查的页码改为 16 与 3，把 `inputs/excerpts.md` 拆成 4a(p15)/4b(p16)/5(p3)，同步修正正文与输出中的页码，并补入 p36 平均值作为交叉验证（第 10 条）。修正后重新运行，12/12 全部命中，结果见 `verification/result.json`。

这件事本身支撑了本文的结论：**「给数字挂页码」不是形式主义，它会真的把错误暴露出来**；而页脚污染、跨页断句是 PDF 文本提取的常见噪声，做证据定位时必须保留原始上下文再判断。

## 本次核查没做的事（如实说明）

- 没有重跑 ECLIPSE 300 或 DMD 训练，因此不验证论文数值本身的正确性，只验证**我们引用的文字与页码一致**。
- 没有做多次重复采样或统计检验，因此不对「哪种提示词普遍更好」下结论。
- Table A2/A3 的逐项数值未摘录，故两次输出都未报告 DMDspc 的细项，也未声称已核查。

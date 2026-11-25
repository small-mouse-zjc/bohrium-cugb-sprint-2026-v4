# 论文合法原文片段（逐字转录，含页码）

> 说明：以下 7 段均从 arXiv:2407.20541v4 的 PDF 用 PyMuPDF 逐页提取后转录，用于核查。
> 页码为 **PDF 物理页码（1-based）**，不是论文印刷页码。断词处的连字符按原文保留。

## 片段 1 — p1，摘要（Baseline 唯一输入）

> Data-driven and non-intrusive DMDc and DMDspc models successfully expedite CO2 fluid flow forecast and optimization, aiding in the acceleration of risk assessment and overall decision-making for geological CO2 storage, while requiring fewer computational resources than traditional high-fidelity reservoir simulators, machine learning, and reduced physics proxy models. ... DMDc and DMDspc models were trained independently with weekly, monthly, and yearly commercial simulator pressure and CO2 saturation fields. The domain of interest is a large-scale, offshore, highly heterogeneous reservoir model with over 130,000 cells. DMDc/DMDspc snapshot recon- struction came with significantly reduced runtimes, from several hours to minutes. Two operation cases were considered: 1. CO2 injection and 2. CO2 injection and water production for pressure maintenance. Injection/production occurs for the first 15 years while the plume is monitored for the next 85 years.

## 片段 2 — p8，模型与时间步设置

> • Initial reservoir temperature and pressure of 56oC and 241 bars, respectively • 5200 seven days (weekly) Δt time-steps • 780 injection/production time-steps
>
> 同页还列出：两种工况 case A（单井注入 CO2）与 case B（一口 CO2 注入井 + 一口采水井用于压力保持）。

## 片段 3 — p12，训练 / 验证划分

> With regards to training DMDc and DMDspc, we used ECLIPSE 300 runs 2, 5, 7, and 10 individually. Regarding validation, the reconstructed snapshots of the DMD models were compared against the original snapshots of the runs that the DMD models were not trained on. We did this to quantify a model's ability ...
>
> 同页：Each simulation run includes 780 time steps or 15 years of injection time. For the remainder of the 100 years of simulation time, the wells are shut in to allow for pressure and CO2 saturation monitoring.

## 片段 4a — p15，精确运行时间（前半句）

> The forecast models' computational times are shown in Table A2 and Table A3 across each scale, case, variable, and period. Both DMDc and DMDspc are faster than the ECLIPSE 300 in every case, even when the two variables are computed sequentially, as shown in Table 1. ECLIPSE 300 average simulation time is ~223 mins for case A and ~140 mins for case B. In contrast, for the entire simulation period, the largest pressure DMDc time is ~1.28 mins and ~1.4 mins for case A and case B, respectively, while the largest

## 片段 4b — p16，跨页续句（饱和度数值在这里）

> 16 saturation time is ~33 mins and ~31 mins for case A and case B, respectively. Both DMDc times are less by far, so they are the largest well-active DMDc times (less than 0.5 mins) from their respective ECLIPSE 300 times of ~45 mins and ~33 mins for case A and case B, respectively.

> **提取注意**：PDF 提取出的行首 `16` 是**页脚页码混入正文**，不是句子内容。这句话从 p15 末的 `while the largest` 续到 p16。首次核查把整句都标成 p15 导致字符串匹配失败，修正记录见 `verification/check-record.md`。

## 片段 5 — p3，文中引用的他人结果（易混淆点）

> ... Addition- ally, their results showed that the higher the number of grid blocks, the higher the computational efficiency. The computation time of one million grid blocks drops from 6766 to 177 seconds and from 279 to 28 seconds for one hundred thousand grid blocks [20]. Holanda et al. (2018) report that typical CRM simula- tions for reservoirs often take between 1 to 2 hours or more ...

> **重要**：这段位于 **p3 文献综述**，是作者引用 [20] 等前人的数字，**不是本文模型的结果**，与 p15–p16 的结果章节相隔十余页。本文模型是 p1 的「over 130,000 cells」。首次核查误标为 p15，已修正。

## 片段 6 — p16 与 p36，Table 1 标题、平均值与作者自述局限

> p16：Table 1 – Average reconstruction times across forecast DMDc and DMDspc models for pressure and CO2 saturation at weekly, monthly, and yearly time scales for case A: CO2 injection and case B: CO2 injection and water production
>
> p36（作者给出的平均值，可交叉验证片段 4a/4b）：for the entire simulation period DMDc (DMDspc) average pressure reconstruction times are weekly 1.34 (1.05) mins, monthly 0.29 (0.16) mins, and yearly 0.02 (0.01) mins. Average saturation times are 31.61 (20.37) mins, monthly 6.87 (6.41) mins, and yearly 0.08 (0.08) mins.
>
> p36：The large-scale offshore reservoir model used includes more than 130,000 cells mesh and is highly heterogeneous. However, to make the procedure we suggest in this study more reliable, it needs to be applied to multiple reservoirs. Two cases were considered: case A, which uses a single well that injects CO2, and case B, which uses one CO2 injection well and one water production well for pressure maintenance. ... having restrictions during optimization, e.g., surface facilities and injectivity might lead to differences between consecutive well rates' values. This may cause DMD to have lower accuracy and, therefore, needs to be investigated further.

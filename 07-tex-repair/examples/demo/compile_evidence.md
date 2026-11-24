# 真实编译证据（07）

## 环境
- 机器：云主机（Linux），TeX Live 2022/dev/Debian
- 引擎：pdfTeX 3.141592653-2.6-1.40.22
- 命令：`pdflatex -interaction=nonstopmode -file-line-error -output-directory=<OUT> main.tex`，有 `\bibliography` 时再 `bibtex main` 后复编两轮

## 修复版（本包 `examples/demo/fixed`）
- 结果：`errors=0`、`undefined=0`、`rerun=0`、`Pages=2`
- 说明：先编一轮 → bibtex → 复编两轮，引用与交叉引用全部收敛
- 结论：模板必填项齐全、可编译、可继续编辑

## 损坏版（本包 `examples/demo/broken`，两轮后仍失败）
| 类型 | 条数 | 位置 |
|---|---|---|
| E10 缺 `$` | 2 | main.tex:13、14 |
| E01 未定义命令 | 2 | main.tex:19 `\toprule`、23 `\bottomrule` |
| E02 文件未找到 | 1 | main.tex:30 `figs/result.pdf` |
| E03 宏包报错 | 1 | pdftex.def 对缺图报错 |
| E05 引用未定义（警告） | 1 | `fig:res` |
| E06 引文未定义（警告） | 1 | `wang2020` |

## 多文件案例（本包 `examples/demo/multi`，2026-11-24 实测）
`main.tex` 用 `\input{sections/intro}`、`\input{sections/method}` 拆两章，含 1 图 2 表、`\citep/\citet` 跨文件引用；`intro.tex` 里故意放了一条注释，内含 `\toprule` 与 `\cite{ghost2099}`。

- `scripts/run.py` 端到端：`status=success`、`violations=0`、`errors=0`、`converged=true`、`bibtex_runs=1`、`pages=2`
- 注释里的宏与假引文**没有**被 T03/T05 误报（静态检查逐行剥 `%` 后再扫）
- 结论：多文件 + 子目录图 + natbib 引用能真实收敛，不只在单文件玩具上成立

## 基线对照（裸 Agent vs 本 Skill，同一台机器、同一工程）
"基线"= 单轮 `pdflatex`、不跑 bibtex、不做静态体检（`examples/baseline.py`）；"Skill"= `scripts/run.py` 全流程。差值由 `eval/metrics.py --out_dir <skill> --base_dir <baseline>` 直接算出。

| 指标 | Skill（fixed） | 基线（fixed） | Skill（broken） | 基线（broken） |
|---|---|---|---|---|
| 模板违规 | 0 | 未检查 | 10（T01×1/T02×2/T03×2/T04×1/T05×1/T06×1/T07×1/T08×1） | 未检查 |
| 编译错误 | 0 | 0 | 10 | 10 |
| 编译警告 | 0 | 6（引文/交叉引用未解析） | 4 | 4 |
| 收敛 | true | false | false | false |
| 构建状态 | success | partial | partial | partial |
| 轮次 / bib 处理 | 3 / 1 | 1 / 0 | 3 / 0 | 1 / 0 |
| 页数 | 2 | 2 | 2 | 2 |

读法：修复版上基线单轮就"出了 PDF"，但 6 条警告、`converged=false`，交稿时表现为 `[?]` 引文；Skill 多花 2 轮 + 1 次 bibtex 换来 `converged=true`。损坏版上两边错误数都是 10，差别在 Skill 在**编译前**就用 8 条规则定位了 10 处问题（含文件与行号），基线要编译一遍才知道错，且不知道模板项缺什么。

## 与本机的关系
本机 Windows 无 TeX，`scripts/build.py` 会返回 `status=static_only` 并注明"未执行真实编译"。上表是在云主机上用同一编译命令与轮次逻辑实测的结果；日志片段存于 `examples/demo/fixtures/pdflatex_2022_broken.log`，供 `logdiag.py` 回归。

## 不声明
未在平台正式案例上运行；不声称任何分数。

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

## 与本机的关系
本机 Windows 无 TeX，`scripts/build.py` 会返回 `status=static_only` 并注明"未执行真实编译"。上表是在云主机上用同一编译命令与轮次逻辑实测的结果；日志片段存于 `examples/demo/fixtures/pdflatex_2022_broken.log`，供 `logdiag.py` 回归。

## 不声明
未在平台正式案例上运行；不声称任何分数。

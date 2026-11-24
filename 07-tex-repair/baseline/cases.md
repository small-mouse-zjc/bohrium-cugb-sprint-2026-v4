# 基础 Agent 的典型失败（07）

| # | 失败模式 | 现象 | 本包判据 |
|---|---|---|---|
| F1 | 模板宏不匹配 | 投稿模板要 `\documentclass{...}`+特定宏包，稿子用另一套 | T01–T08 静态规则（本包 broken 命中 10 处） |
| F2 | 缺图/缺 bib | `\includegraphics{figs/result.pdf}` 文件不存在 | E02 + 构建前置检查 |
| F3 | 表格宏缺失 | `\toprule` 未定义 | E01，定位 `main.tex:19/23` |
| F4 | 交叉引用未解析 | `??` 满页 | 二次编译未收敛 → rerun 判定 |
| F5 | 把警告当错误/把错误当通过 | 日志不读，凭感觉说"应该能编译" | `logdiag` 分级 E/W，`converged` 显式输出 |
| F6 | 无 TeX 环境仍声称编译成功 | 没有 pdflatex 却报 success | 无引擎 → `static_only`，不谎称通过 |

真实证据：云主机 TeX Live 2022 实编（`examples/demo/compile_evidence.md`），fixed 0 错 0 未定义 2 页；broken 保留真实日志片段供回归。

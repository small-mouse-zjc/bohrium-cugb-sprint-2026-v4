---
name: latex-template-fit
description: 把已有 LaTeX 稿件迁入指定模板：先做静态合规检查（必填项、宏包、交叉引用、表格列数、图路径），再按轮编译并把日志错误定位到文件/行号/根因，修完复编至收敛，最后输出可重复的构建清单。用于 LaTeX 投稿前的模板适配与编译修复。
---

# 模板适配 + 编译收敛

## 0. 单点

**"模板要求 ↔ 稿件实际"的逐项对齐**，加上**编译日志的根因定位**，最后**构建清单**让别人能复现同一份 PDF。不追求排版美化。

## 1. 何时触发

"套期刊模板""编译不过""Overfull 太多""改完还是报错""换机器编译结果不一样"。
不触发：纯公式排版咨询、纯文献翻译、Word 转 LaTeX 的内容改写（可先转再套本流程）。

## 2. 输入与输出

输入：`/input/case.json`、`/input/task.md`、稿件（main.tex + 子文件 + .bib + 图片）、模板（.cls/.sty 或 template.yaml）。

输出 `/app/output/`：

| 文件 | 内容 |
|---|---|
| `main.tex` 等 | 修复后的可编译源码（保留原有结构，不整体重写） |
| `texfit.json` | 静态合规检查结果（规则 id、文件、行号、修法） |
| `logdiag.json` | 编译日志结构化诊断（根因、行号、是否级联） |
| `build_manifest.json` | 引擎与版本、命令、轮次、输入哈希、产物路径、状态 |
| `result.json` | 契约字段 + `case_id` + `status` + `metrics` |

## 3. 流程

**第 1 步 静态体检（先查再说，别急着编译）**
```
python scripts/texfit.py --project work/paper --template work/template.yaml --out /app/output
```
查这些（每条给文件:行号 + 修法）：

| 规则 | 内容 |
|---|---|
| T01 | `\documentclass` 与模板类别/选项一致（如 `[11pt]{article}`） |
| T02 | 模板必填项齐全（标题、作者、摘要、关键词、指定章节、参考文献样式） |
| T03 | 用了宏但没加载对应宏包（`\toprule`→booktabs，`\includegraphics`→graphicx 等） |
| T04 | `\ref/\eqref` 指向不存在的 `\label` |
| T05 | `\cite` 键不在 `.bib` 中 |
| T06 | `tabular` 列格式与行内 `&` 数不一致（编译不一定报错，但会错位） |
| T07 | `\includegraphics` 路径不存在 |
| T08 | 必填章节缺失或编号与模板要求不符 |

**第 2 步 编译一轮并诊断（有 TeX 就真编，没有就明说）**
```
python scripts/build.py --project work/paper --out /app/output --rounds 3
```
- 有 `latexmk/pdflatex/xelatex`：按 `-interaction=nonstopmode -file-line-error` 编译，读到 `Rerun` 就再编一轮，最多 3 轮。
- 没有 TeX：`status=static_only`，只出静态检查结果并注明"未做真实编译"，**不许写"编译通过"**。
诊断把日志映射到 `E01–E10`（见 `references/error_catalog.md`），并标出**级联错误**：同一文件 20 行内的后续报错通常由第一条引起，修第一条再看。

**第 3 步 修复（按根因改，不按报错顺序改）**
优先级：E02 缺文件/宏包 → E01 未定义命令 → E10 缺 `$` → E05/E06 引用 → 版式警告（E08）。
每改一处，重新跑第 2 步，直到 `errors=0` 且 `rerun=false`。

**第 4 步 收敛与清单**
`build.py` 在收敛时写 `build_manifest.json`：引擎与版本、完整命令、轮次、主文件/子文件/.bib 的 sha256、产物路径与页数（可用 `pdfinfo`，没有就留空）。**换机器照这个清单能复现同一产物**。

**第 5 步 交付**
`result.json` 的 `status`：`success`（编译通过且模板项齐全）/ `partial`（编译通过但模板项缺，列出缺项）/ `cannot_determine`（无 TeX 且静态检查无法判定）/ `rejected`（输入不是可编译工程）。

## 4. 预算与降级

64 请求 / 900 秒。静态检查不耗请求；编译轮次受 900 秒限制，长文档先只编主文件，子文件语法用静态检查兜底。剩余 <5 请求时停在"已修错误 + 未修清单"，交付 `partial`。

## 5. 异常

| 情况 | 处置 |
|---|---|
| 缺宏包/字体 | 报 E02 并给出包名；无权限安装时在清单里写明"需在镜像中预装" |
| 模板 .cls 缺失 | 停止编译，`status=cannot_determine`，列出缺失文件 |
| 报错级联严重（>50 条） | 先修第一条 E01/E02，再重编，不逐条硬改 |
| Overfull 无法消除 | 记录具体行与溢出量，标"版式警告，非错误"，不靠缩字号掩盖 |
| 中文/字体问题 | 报 E09，建议 `ctex` 或 `xeCJK`，不擅自换引擎 |

## 6. 自检

```
python examples/selftest.py
```
要求：损坏工程被静态检查抓出 ≥6 条并给出修法；修复版 0 违规；用真实日志样本验证 `E01/E02/E05/E06/E08` 分类与行号定位；无 TeX 时 `build.py` 必须报 `static_only` 而不是假称通过。

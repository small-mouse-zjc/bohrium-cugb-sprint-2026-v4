# 07 · LaTeX 模板适配与编译收敛

**一句话**：先做"模板要求 ↔ 稿件实际"的静态逐项体检（T01–T08），再按轮真实编译并把日志错误定位到文件/行号/根因（E01–E10），修到 `errors=0` 且 `rerun=false`，最后输出一份别人照做能得到同一份 PDF 的构建清单。

只做这一件事：不追求排版美化，不做纯公式排版咨询、纯翻译、Word 转 LaTeX 的内容改写。

---

## 1. 为什么是这个单点

投稿前最耗时的不是"写"，而是"套模板 + 编译报错"。基础 Agent 的典型失败是**按报错顺序硬改**：第一条 `Undefined control sequence` 其实只是漏了 `booktabs`，它却去改后面的表格；结果错误越改越多。第二类失败是**声称编译通过**：机器上没有 TeX，静态看了一遍就说"已修复、可编译"。

v3 因此定死两条：**先静态体检再编译**，**没有 TeX 就明说 `static_only`**。这两条都能被产物审计，不靠自述。

## 2. 交付物

| 文件 | 内容 |
|---|---|
| `main.tex` 等 | 修复后的可编译源码，保留原结构，不整体重写 |
| `texfit.json` | 静态合规结果：规则 id、文件、行号、修法 |
| `logdiag.json` | 编译日志结构化诊断：错误码、根因、行号、是否级联 |
| `build_manifest.json` | 引擎与版本、完整命令、轮次、`bibtex_runs`、输入 sha256、产物路径与页数，以及 `status/converged/rerun_required/errors` |
| `result.json` | 契约字段 `case_id` + `status` + `metrics`，由 `scripts/run.py` 产出（平台入口：读 `/input/case.json`） |

## 3. 静态规则 T01–T08

| 规则 | 检查内容 | 为什么编译不一定报错但必须查 |
|---|---|---|
| T01 | `\documentclass` 类别与选项是否符合模板（如 `[11pt]{article}`） | 字号/版式不符，编译照样成功 |
| T02 | 模板必填项：标题、作者、摘要、关键词、指定章节、参考文献样式 | 缺项常被期刊直接退稿 |
| T03 | 用了宏但没加载宏包（`\toprule`→booktabs、`\includegraphics`→graphicx） | 未定义命令的错误根因 |
| T04 | `\ref/\eqref` 指向不存在的 `\label` | 输出 `??`，不报错 |
| T05 | `\cite` 键不在 `.bib` 中 | 输出 `[?]` |
| T06 | `tabular` 列格式与行内**未转义** `&` 数不一致（`\&` 不算分隔；行号取源码真实行） | 表格错位，不报错 |
| T07 | `\includegraphics` 路径不存在 | 编译期才炸 |
| T08 | 必填章节缺失或编号不符 | 结构不合规 |

## 4. 编译诊断 E01–E10

`logdiag.py` 把日志映射到固定错误目录，并判定级联：同一文件内、行差 ≤3 且错误码相同的后续报错，标 `cascade_of` 指向首条，避免逐条硬改。

| 码 | 含义 |
|---|---|
| E01 | Undefined control sequence（命令拼错/缺宏包） |
| E02 | File not found（图片、`.sty`、`.bib` 缺失） |
| E03 | 宏包内部报错（如 `pdftex.def` 对缺图） |
| E04 | 环境未闭合 |
| E05 | 引用未定义（`\ref` 警告） |
| E06 | 引文未定义（`\cite` 警告） |
| E07 | 表格列数/对齐错误 |
| E08 | Overfull/Underfull（版式警告，非错误） |
| E09 | 字体/中文编码（建议 `ctex` / `xeCJK`） |
| E10 | Missing `$`（正文出现 `_ ^` 等数学符号） |

修复优先级：E02 缺文件/宏包 → E01 未定义命令 → E10 缺 `$` → E05/E06 引用 → E08 版式警告。

## 5. 流程

**第 1 步 静态体检（先查再说，别急着编译）**

```
python scripts/texfit.py --project work/paper --template work/template.yaml --out /app/output
```

**第 2 步 编译一轮并诊断**

```
python scripts/build.py --project work/paper --out out --rounds 3
# 平台入口（读 /input/case.json，一次串完三步并写 result.json）
python scripts/run.py --input /input --output /app/output
```

- 引擎默认 `pdflatex`，其次 `xelatex`；`latexmk` 只有显式 `--engine latexmk` 才用（给 latexmk 传 `-halt-on-error=false` 这类 pdflatex 旗标它会直接 `Bad options specified`）；
- 首轮后若工程有 `.bib`，自动 `bibtex`（`BIBINPUTS` 指向工程目录）再复编，否则引文恒为 `[?]`、`converged=false`；
- 没有 TeX：`status=static_only`，只出静态结果并注明"未执行真实编译"，**不许写"编译通过"**。

**第 3 步 按根因修复**，每改一处重跑第 2 步，直到 `errors=0` 且 `rerun=false`。

**第 4 步 收敛与清单**：写 `build_manifest.json`（引擎与版本、命令、轮次、`bibtex_runs`、主文件/子文件/`.bib` 的 sha256、产物与页数、`converged`）。换机器照清单能复现同一产物。

**第 5 步 交付**（`run.py` 按同一口径判定，不手填）：`success` 需 `violations=0` 且 `errors=0` 且 `converged=true` 且 PDF 存在；`partial` 是有 PDF 但引用未收敛/模板项缺；`cannot_determine` 是无 TeX 只剩静态结论；`rejected` 是缺 `main.tex`。

## 6. 实测证据（自建工程 + 真实 TeX 日志，非平台案例）

静态检查（`examples/demo/broken`）：

- 命中 **T01–T08 全部 8 类、共 10 处**：T01×1（缺 `11pt`）、T02×2（缺 `\bibliographystyle` 与样式）、T03×2（`\toprule/\bottomrule` 未加载 booktabs）、T04×1（`fig:res` 无 label）、T05×1（`wang2020` 不在 bib）、T06×1（列格式 3 列、行内 2 列）、T07×1（`figs/result.pdf` 不存在）、T08×1（缺 Conclusions）；
- 修复版 `texfit.json` 违规 **0**。

真实编译（云主机 Linux，TeX Live 2022 / pdfTeX 3.141592653-2.6-1.40.22）：

| 对象 | 结果 |
|---|---|
| 修复版 | `status=success`、`errors=0`、`converged=true`、`bibtex_runs=1`、`Pages=2`（pdflatex → bibtex → 复编两轮，共 3 轮） |
| 损坏版 | 两轮后仍失败：E10×2（main.tex:13/14）、E01×2（:19/:23）、E02×1（:30）、E03×1、E05×1、E06×1 |

日志片段存于 `examples/demo/fixtures/pdflatex_2022_broken.log`，供 `logdiag.py` 回归；完整证据见 `examples/demo/compile_evidence.md`。

本机（Windows，无 TeX）跑 `build.py` 时，产物 `build_manifest.json` 是 `engine=none, status=static_only, converged=false, note="本机无 pdflatex/xelatex/latexmk，未执行真实编译；只做静态检查，不得声称编译通过"`——这是**设计行为**，不是失败。

缺陷注入自检（`python examples/selftest.py`）**10 条断言全绿**，两台机器都跑过：Windows（无 TeX）与云主机（TeX Live 2022）——损坏工程 8 规则/10 处违规且给修法、修复版 0 违规、真实日志 E01/E02/E05/E06/E08 分类与行号正确、有 TeX 时 `status=success & converged=true & bibtex_runs=1 & pages=2`、无 TeX 时返回 `static_only` 不假称通过；并额外验证 `run.py` 由 `case.json` 产出合法 `result.json`、**T06 不把 `\&` 当列分隔且报真实行号**、**字体日志真报 E09 并给 `ctex/xeCJK` 修法**、**平台布局下 `input/template.yaml` 的 `source_date_epoch` 真落到编译清单**（本轮补强）。

> 2026-11-24 深夜修订：上一版 `build.py` 把 `latexmk` 排在默认第一位且给它传了 pdflatex 专用旗标，在有 latexmk 的机器上直接 `Bad options specified`；pdflatex 路径又从不跑 `bibtex`，导致引文恒为 `[?]` 而 `status` 仍写 `compiled`。现已改为 pdflatex 优先、自动 bibtex、`status` 按 `errors=0 & !rerun & pdf 存在` 判定，并新增 `scripts/run.py` 补上 `/input/case.json → /app/output/result.json` 的平台入口。本节数字全部来自修订后的实跑。

## 7. 异常与降级

| 情况 | 处置 |
|---|---|
| 缺宏包/字体 | 报 E02 并给包名；无权限安装时在清单写"需在镜像中预装" |
| 模板 `.cls` 缺失 | 停止编译，`cannot_determine`，列出缺失文件 |
| 级联报错 >50 条 | 先修首条 E01/E02 再重编，不逐条硬改 |
| Overfull 无法消除 | 记录行与溢出量，标"版式警告，非错误"，不靠缩字号掩盖 |
| 中文/字体问题 | 报 E09，建议 `ctex` 或 `xeCJK`，不擅自换引擎 |
| 预算不足（剩余 <5 请求） | 停在"已修错误 + 未修清单"，交付 `partial` |

## 8. 快速开始

```bash
python scripts/texfit.py --project work/paper --template work/template.yaml --out out
python scripts/build.py  --project work/paper --out out --rounds 3
python scripts/logdiag.py --log out/main.log --out out    # 单独分析已有日志
python examples/selftest.py
```

依赖：Python 3.10+；`texfit.py` 仅标准库（YAML 模板需 PyYAML，缺省可用 JSON 模板）；`build.py` 需 TeX 发行版，缺省降级为静态模式。

## 9. 目录结构

```
07-tex-repair/
├── SKILL.md
├── README.md
├── scripts/            # texfit.py（T01–T08）/ build.py（编译收敛）/ logdiag.py（E01–E10）
├── references/error_catalog.md
├── eval/
├── baseline/cases.md
├── examples/
│   ├── demo/
│   │   ├── broken/     # 含 10 处违规的工程
│   │   ├── fixed/      # 修复版（含 refs.bib、figs/result.pdf）
│   │   ├── fixtures/   # 真实 pdflatex 日志片段
│   │   └── compile_evidence.md
│   ├── expected/       # broken/fixed 两套 texfit/logdiag/build_manifest
│   └── selftest.py
└── environment/resources.yaml
```

## 10. 维护与扩展

- 新增静态规则：在 `texfit.py` 的规则表加 `T09…`，同时在 `references/error_catalog.md` 与 `eval/rubric.yaml` 登记；
- 新增错误码：在 `logdiag.py` 的正则表加 `E11…`，并补一条真实日志回归用例；
- 换期刊模板：只改 `template.yaml`（类别、必填项、章节名、参考文献样式），规则引擎不动；
- 多文件工程：`build.py` 以主文件为准，子文件用静态检查兜底，避免 900 秒预算被反复整编耗尽。

## 11. 声明

- `examples/demo` 的工程、模板为自建样例；日志片段来自真实 pdflatex 输出，**非平台案例结果**；
- 本包未在平台运行，不声称任何平台得分；
- 静态检查不替代真实编译，宏包内部语义错误只能靠日志判定。

**多文件案例（`examples/demo/multi`，实测）**：`main.tex` 用 `\input` 拆出 `sections/intro`、`sections/method` 两章，含子目录图、两张表、`\citep/\citet` 跨文件引用，并在注释里故意写了 `\toprule` 与 `\cite{ghost2099}` 作干扰。`run.py` 端到端结果：`status=success / violations=0 / errors=0 / converged=true / bibtex_runs=1 / pages=2`，注释里的伪违规没有误报。

**基线对照（同机同工程，`examples/baseline.py` = 单轮 pdflatex、不跑 bibtex、不体检）**：修复版基线 `partial / converged=false / 6 条引文警告 / 1 轮 / 0 次 bib`，本 Skill `success / converged=true / 0 警告 / 3 轮 / 1 次 bib`；损坏版两边都是 10 条错误，差别是本 Skill 在编译前就用 8 条规则定位了 10 处问题（含文件行号），基线编完才知道错。完整表见 `examples/demo/compile_evidence.md`，差值可用 `eval/metrics.py --out_dir <skill输出> --base_dir <基线输出>` 复算。

## 可复现产物（2026-11-25 补强）

`build_manifest.json` 现在记录**产物指纹**，不只是输入指纹：

| 字段 | 内容 |
|---|---|
| `pdf.sha256` | 产出 PDF 的完整 SHA-256 |
| `pdf.bbl_sha256` / `bbl` | bibtex 产出的 .bbl 指纹（跑过 bibtex 时） |
| `pdf.id_normalized` | 是否已把 pdfTeX 的 `/ID` 归一化为确定性值 |
| `compile_env` | `SOURCE_DATE_EPOCH` / `FORCE_SOURCE_DATE` / `reproducible` |

做法与理由：

1. **时间戳固定**：编译时注入 `SOURCE_DATE_EPOCH=1577836800`（2020-01-01，可用 `--epoch` 或项目 `template.yaml: source_date_epoch` 覆盖）与 `FORCE_SOURCE_DATE=1`，让 pdfTeX 的 `CreationDate`/`ModDate` 与 `\today` 都不随机器时间变。
2. **`/ID` 归一化**：pdfTeX 的 `/ID` 由输出路径与编译时刻参与生成，同一输入放到 `/tmp/a` 与 `/tmp/b` 编出来字节不同。`normalize_pdf_id()` 把它替换成 `sha256(输入哈希 + epoch)` 派生的 32 位十六进制串——等长原地替换，xref 偏移不动，`pdfinfo` 仍能正常读出 2 页。
3. **实测**：TeX Live 2022 云主机上两目录各编一次，`sha256sum` 完全相同（`dc2a5413…`），且等于清单记录值；回执见 `examples/expected/fixed/build_manifest.texlive2022.json`。

## 收敛门槛被回归测试锁住

`examples/selftest.py` 在有 TeX 的分支不再接受 `partial`：

```python
assert m["status"] == "success" and m["converged"] is True
assert m["errors"] == 0 and m["bibtex_runs"] >= 1 and m["rerun_required"] is False
assert m["pdf"]["sha256"]                      # 清单必须有产物指纹
```

再加两条反向用例：同一工程再编一次必须得到相同 `sha256`（字节级复现）；`--no-bibtex` 时必须降级为 `partial`/`converged=False` 且进程返回非 0——把"引文未解析不判成功"这条规则钉死。

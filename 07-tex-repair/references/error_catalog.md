# 错误目录（E01–E10）

| 码 | 名称 | 典型日志 | 根因 | 最小修法 |
|---|---|---|---|---|
| E01 | 未定义命令 | `Undefined control sequence` + `l.NN \toprule` | 命令拼错，或宏包没加载 | 补 `\usepackage{booktabs}`；核对拼写 |
| E02 | 文件未找到 | `File 'figs/result.pdf' not found` | 图片/子文件/宏包路径错或未安装 | 修正相对路径；补扩展名；装包 |
| E03 | 宏包报错 | `Package pdftex.def Error: ...` | 选项冲突、参数类型错 | 读 Error 后一句说明；核对模板选项 |
| E05 | 交叉引用未定义 | `Reference 'fig:res' ... undefined` | 缺 `\label`、键名错、轮次不足 | 补标签；再编一轮 |
| E06 | 引文键未定义 | `Citation 'wang2020' ... undefined` | 键不在 .bib 或没跑 bibtex/biber | 核对键名；跑 bib 处理后复编 |
| E08 | 版式溢出 | `Overfull \hbox (12.3pt too wide)` | 长公式/宽表超版心 | 拆行、缩表、改列宽；不缩字号掩盖 |
| E09 | 字体不可用 | `Font ... not loadable` | 缺字体或编码不匹配 | 用 ctex/xeCJK，或装字体 |
| E10 | 缺数学模式符 | `Missing $ inserted` + `l.NN ... x_1` | 正文里写了 `_ ^` 等数学符号 | 加 `$...$` 或转义 |
| E00 | 其他 | 未被以上规则匹配 | 需读上下文 | 保留原文，人工判断 |

## 级联判定
同文件、同一码、行号相差 ≤3 视为级联（前一条没修完导致的重复报错）。修第一条，再复编，不要逐条硬改。

## 修复顺序
E02（缺文件/包）→ E01（未定义命令）→ E10（缺 `$`）→ E03 → E05/E06（引用）→ E08（版式警告）。
理由：前四类会让后续报错成片出现，先修它们能把噪声消掉。

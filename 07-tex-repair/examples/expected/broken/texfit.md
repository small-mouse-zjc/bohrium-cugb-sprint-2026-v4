# 模板合规静态检查

- 结论: 未通过

| 规则 | 文件 | 行 | 说明 |
|---|---|---|---|
| T01 | main.tex | 1 | 缺少类选项 11pt |
| T02 | main.tex | 0 | 缺少必填命令 \bibliographystyle |
| T02 | main.tex | 0 | 缺少参考文献样式 plain |
| T03 | main.tex | 19 | 用了 \toprule，但未加载 booktabs |
| T03 | main.tex | 23 | 用了 \bottomrule，但未加载 booktabs |
| T04 | main.tex | 12 | \ref{fig:res} 没有对应 \label |
| T05 | main.tex | 28 | \cite{wang2020} 不在 .bib 中 |
| T06 | main.tex | 22 | 列格式 3 列，该行有 2 列 |
| T07 | main.tex | 30 | 图片不存在: figs/result.pdf |
| T08 | main.tex | 0 | 缺少章节 Conclusions |

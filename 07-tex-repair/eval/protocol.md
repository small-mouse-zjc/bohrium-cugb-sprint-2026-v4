# 对照协议（07）

## 平台侧
3 个固定案例，同工程同模板，基础 vs Skill，各 3 次重复；版式类相对项用组织方白板。本包不提供案例答案。

## 本包侧
1. **同输入**：同一 `main.tex`、同一 `template.yaml`、同一 TeX 版本与命令。
2. **指标**：模板违规数、命中规则数、编译错误数、警告数、是否收敛、轮次、构建状态。
3. **重复性**：同一工程重复编译，`texfit.json` 应逐字节稳定；`logdiag.json` 的错误集合应一致（行号允许 TeX 版本差异）。
4. **盲评**：只看修复后的 `main.tex` 与 PDF，不看诊断报告；评审按模板要求逐项核对。
5. **不声明**：不写"提升多少分"；真实编译证据只陈述本机/云主机实测事实。

## 指标定义
- 模板违规 = `texfit.json` 的 violations 条数（T01–T08）
- 编译错误 = 日志中 `file:line:` 形式的错误条数（警告单列）
- 收敛 = 无错误、无 Overfull 之外的重编提示、无 undefined references
- 构建状态 = `compiled / failed / static_only / rejected`

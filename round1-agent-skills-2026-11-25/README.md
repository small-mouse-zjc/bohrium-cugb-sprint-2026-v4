# 中国地质大学（北京）分站赛第一期作品

每个目录中的 `SKILL.md` 是独立 Agent Skill 的入口。配套 Python 脚本提供可复核的定位、导出或一致性检查。脚本不依赖模型 API 密钥。执行环境为 Python 3.9+，其中 PDF 方框提取需要 Poppler。OCR、Office 文件渲染与 LaTeX 编译使用赛事环境声明的工具。各 Skill 的最小示例采用合成输入。正式案例由赛事评测平台提供。

| 赛题 | 作品 |
| --- | --- |
| 文献文档解析 | [pdf-layout-audit](./pdf-layout-audit/SKILL.md) |
| 文献翻译 | [paper-translation-audit](./paper-translation-audit/SKILL.md) |
| 文献总结与结构化笔记 | [paper-evidence-notes](./paper-evidence-notes/SKILL.md) |
| Nanopublication | [evidence-nanopublications](./evidence-nanopublications/SKILL.md) |
| 文献知识图谱构建 | [paper-evidence-graph](./paper-evidence-graph/SKILL.md) |
| 学术语言润色 | [academic-edit-provenance](./academic-edit-provenance/SKILL.md) |
| 参考文献与引用管理 | [reference-integrity-audit](./reference-integrity-audit/SKILL.md) |
| 引言与相关工作写作 | [introduction-evidence-map](./introduction-evidence-map/SKILL.md) |
| 方法与实验章节写作 | [methods-reproducibility-map](./methods-reproducibility-map/SKILL.md) |
| LaTeX 写作与编译 | [latex-build-audit](./latex-build-audit/SKILL.md) |

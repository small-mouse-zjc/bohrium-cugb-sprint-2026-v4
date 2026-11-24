# 玻尔 CUGB 挑战赛 · v3 单点重做（2026-11-24）

针对 7 道低于 70 分的题（01 66.3333 / 04 62.0 / 05 64.3333 / 07 57.0 / 08 63.6667 / 09 63.0 / 10 63.6667）换思路重做：**每题只保留一个单点，把这一条主链做深、做牢，并用可复算的证据证明它真的能跑。**

v2 的做法是"在原包上继续加文件"，被否。v3 的判断是：这 7 题丢分不在素材不够，而在**每题都做了一个泛化功能，没有一项做到可验证的完成度**。因此每包只回答一个问题："这一件事，我能不能做到别人拿过去就能用、用完能核对？"

---

## 1. 七个单点

| 包 | 只做这一件事 | 交付的核心产物 |
|---|---|---|
| [01-glossary-align](01-glossary-align/) | 术语锁定 + 段落级双语对照 + 五项机器质检 | `bilingual.json` / `glossary.csv` / `qc.json` |
| [04-related-matrix](04-related-matrix/) | 工作×五维矩阵 → 由共同局限推空白 → 论断与贡献绑定 | `matrix.json` / `intro_draft.md` / `bind.json` |
| [05-repro-guard](05-repro-guard/) | 参数逐项溯源（四状态）+ 步骤四要素 + 复现九项 | `params.csv` / `audit.json` / `repro.json` |
| [07-tex-repair](07-tex-repair/) | 模板静态体检 T01–T08 + 编译日志根因 E01–E10 + 构建清单 | `texfit.json` / `logdiag.json` / `build_manifest.json` |
| [08-column-reflow](08-column-reflow/) | 双栏阅读顺序：通栏分带、带内左→右、页眉去重、断词合并 | `paragraphs.jsonl` / `reflow.json` |
| [09-nanopub-export](09-nanopub-export/) | 一句一断言 + 逐字证据 + JSON-LD/TriG 四层导出 + 回解析 | `nanopub.jsonld` / `nanopub.trig` / `validation.json` |
| [10-crosspaper-kg](10-crosspaper-kg/) | 跨篇别名归一（含"不得合并"显式判定）+ 边绑引文 + 四类查询 | `kg.json` / `queries_result.json` / `validation.json` |

每个包结构一致：`SKILL.md`（Agent 触发与执行契约）、`README.md`（为什么/怎么做/实测/边界）、`scripts/`（可运行实现）、`references/`（方法与错误目录）、`eval/`（`rubric.yaml` / `metrics.py` / `protocol.md`）、`baseline/`（对照口径与缺陷夹具）、`examples/`（`demo` 输入、`expected` 真实产物、`selftest.py` 缺陷注入）、`environment/resources.yaml`。

## 2. 实测（全部来自本地真实运行）

| 包 | 自建样例实测 | 缺陷注入 |
|---|---|---|
| 01 | 7 段全译、16 术语、35 次术语检查、28 数字、7 引用，五项比率全 1.00 | 术语漂移 / 整段漏译 / 数字+引用丢失，3/3 命中 |
| 04 | 6 篇 5 维填充 1.00、1 条空白（2 篇支撑）、1 处冲突、3 组、8 论断全挂引用、3 贡献全有证据 | 无引用 / 悬空引用 / 空白单支撑 / 贡献无证据，4/4 命中 |
| 05 | 3 参数全有源（定位到 file:line）、无源 0、冲突 0、九项 1.00、步骤 1.00、限制 1.00 | 参数冲突 / 凭空数值 / 缺清单项 / 步骤缺判断，4/4 命中 |
| 07 | broken 命中 T01–T08 共 10 处；fixed 在 TeX Live 2022 实编 `errors=0 / undefined=0 / 2 页` | 静态 8 类 + 日志 E10×2、E01×2、E02×1 等，6 类命中 |
| 08 | 23 块位置命中 1.00、逆序 0、相邻错位 0；朴素 y→x 基线 0.3043 / 20 / 18 | 真值对照 2 组 |
| 09 | 5 条断言原子/逐字/来源全 1.00，TriG 回解析 5 图 / 5 节点 / 5 引文一致 | 并列句 / 改写引文 / 缺段落号 / 重复，4/4 命中 |
| 10 | 19 提及→11 节点（6 跨篇）、1 条非合并、6 边引文 1.00、4 查询全有证据 | 未归一 / 冲突合并 / 改写引文 / 空查询 / 缩写无全称，5/5 命中 |

一条命令复核全部：

```bash
for d in 01-glossary-align 04-related-matrix 05-repro-guard 07-tex-repair \
         08-column-reflow 09-nanopub-export 10-crosspaper-kg; do
  (cd "$d" && python examples/selftest.py)
done
```

七个 `selftest.py` **7/7 通过**。

## 3. 评分维度怎么落物

每题 100 分 = 40 实际效果 + 25 使用增益（质量 15 / 效率 5 / 可验证 5）+ 15 创新（新增 5 / 改进 5 / 证据 5）+ 10 可靠体验 + 10 生态贡献。

| 维度 | 本仓对应实物 |
|---|---|
| 40 实际效果 | `scripts/` 可运行实现 + `examples/expected/` 真实产物（不是截图、不是描述） |
| 25 使用增益 | `eval/metrics.py` 对任意输入重算指标；`eval/protocol.md` 固定同输入对照口径 |
| 15 创新 | `baseline/cases.md` 列基础 Agent 的典型失败；`selftest.py` 注入并要求检测器必须命中 |
| 10 可靠体验 | `SKILL.md` 写触发/不触发、预算降级、异常处置；脚本缺输入显式报错，不静默通过 |
| 10 生态贡献 | 每包 README 含快速开始、输入输出字段表、限制与维护；`references/` 与 `resources.yaml` 可被复用 |

## 4. 包体合规

| 项 | 上限 | 实测 |
|---|---|---|
| 每包文件数 | 50 | 17–26 |
| 单文件大小 | 500 KB | 最大约 12.5 KB |
| 每包总量 | 2 MB | 最大约 70 KB |

## 5. 提交与评分状态

- 2026-11-24 晚已把 7 个包各提交一次（attempt：01 `104862`、04 `104863`、05 `104865`、07 `104866`、08 `104864`、09 `104857`、10 `104867`），提交时全部 `submitted / queued`。
- **截至本 README 更新时尚未出分**；本仓不声称任何平台得分，历史基线（66.3333 / 62.0 / 64.3333 / 57.0 / 63.6667 / 63.0 / 63.6667）只作对照。
- 回执与包哈希见 [`SUBMIT_RECEIPTS.md`](SUBMIT_RECEIPTS.md)。

## 6. 必须说清的边界

1. **构造与真实的边界**：07 的编译证据来自云主机 TeX Live 2022 实编（日志片段随包）；其余 6 包的 `examples/demo` 均为自建构造样例，已在各包 README 与 `result.json` 标注"非平台案例"。
2. **不伪造**：不伪造文献、不伪造术语表、不伪造比对数字；所有比率可由 `eval/metrics.py` 或对应脚本从产物重算。
3. **失败可解释**：脚本对缺 TeX、缺文字层、缺来源、空查询等情况给出明确状态（`static_only / partial / cannot_determine`），不把"没做"写成"通过"。

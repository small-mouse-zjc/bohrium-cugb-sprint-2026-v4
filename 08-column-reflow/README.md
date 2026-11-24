# 08 · 双栏论文的阅读顺序重排

**一句话**：只修阅读顺序——用通栏块把页面切成横向带，带内"左栏整栏 → 右栏整栏"，页眉页脚跨页去重，断词与续段合并，输出带页码与坐标的段落序列，供人按位置回查。

只做这一件事：不做表格结构、不做公式识别、不做 OCR。无可靠双栏证据时判 `layout=single`，绝不硬分栏。

---

## 1. 为什么是这个单点

PDF 提取工具按坐标返回文本块，最朴素的做法是"先按 y 再按 x"排序。双栏论文里这会得到：

> 左栏第 1 段 → 左栏第 2 段 → **右栏第 1 段** → 左栏第 3 段 → …

读起来就是"左栏最后一句接到右栏第一句"，整页文本看似完整，实际不可用。这是**顺序错误**，不是内容缺失，模型很难凭语义察觉，必须用版面结构修。v3 把它做成纯几何算法，并用**已知真值样本**验证，而不是"看起来顺了"。

## 2. 交付物

| 文件 | 内容 |
|---|---|
| `paragraphs.jsonl` | 每行 `{id,page,col,bbox,text,order_index}`，顺序即阅读顺序 |
| `reflow.json` | 页数、栏数判定、剔除的页眉页脚、串栏疑似位置、覆盖率 |
| `reflow.md` | 人读版：`[P0001] p.2 L` + 文本 |
| `result.json` | 契约字段 `case_id` + `status` + `metrics`，**由 `scripts/run.py` 产出**（有真值才复算） |

## 3. 算法

**第 1 步 版面判定**

```
python scripts/reflow.py --pdf paper.pdf --out /app/output --audit
```

- PyMuPDF 取块（`bbox` + 行文本）；
- 左栏块：`x1 < 0.55W`；右栏块：`x0 > 0.45W`；中间留白 ≥4pt 才判双栏；
- 通栏块：宽 > 0.6W，或横跨栏间留白（标题、摘要、跨栏图、宽表）；
- 无可靠双栏证据 → `layout=single`，并在 `reflow.json` 说明原因。

**第 2 步 排序（核心）**

1. 用通栏块按 `y` 切横向带（band）；
2. 每条带内：左栏自上而下 → 右栏自上而下；
3. 带与带之间按 `y` 递增。

这样标题在顶部、跨栏图在其所在高度插入，左右栏不会交错。三栏及以上按 `x` 聚类成 n 栏，仍按"带内左→右"。

**第 3 步 清理**

- 页眉页脚：上下 7% 区域内按三种形态剔除并记 `reason`：跨页逐字重复、页码形态（`Page N`/`N of M`/`N`）、跨页仅数字不同的短 running head（字号小于正文）——只认逐字重复会漏掉每页变化的页码；
- 断词：行末 `-` 直接拼接（`micro-` + `structure` → `microstructure`）；
- 同栏续段：上一块无句末标点、下一块小写开头、垂直间距 ≤1.6 倍字号时合并。

**第 4 步 审计**

`--audit` 报"同一页左栏末尾无句末标点直接转右栏"的串栏疑似位置，`suspicious` 非空即 `status=partial` 并列出段落 id。

## 4. 硬门槛

| 指标 | 门槛 |
|---|---|
| 段落覆盖率 | 正文块全部进入输出，无遗漏 |
| 串栏疑似数 | 0 |
| 页眉页脚泄漏 | 0 |
| 单页顺序可解释性 | 每段给出 `col` 与 `bbox`，人能按坐标核对 |

## 5. 实测证据（构造样本，已知真值，非平台案例）

`examples/tools/make_demo.py` 生成 2 页双栏 PDF（23 个文本块，每块带 `[[Pn]]` 标记）与 `truth.json`，`eval/measure.py` 按"位置命中率 / 逆序对 / 相邻错位"三项比对：

| 指标 | 本算法 | 朴素"先 y 后 x"基线 |
|---|---|---|
| 位置命中率 | **1.00** | 0.3043 |
| 逆序对 | **0** | 20 |
| 相邻错位 | **0** | 18 |
| `order_match` | **true** | false |

- 23 块全部提取，`layout=2-column`，`suspicious` 为空；
- 跨页重复的 2 条页眉各出现 2 次，共 4 条全部被剔除并记录（`Demo Journal of Reflow 2026 - preprint`、`Demo preprint, not for citation`）；
- 产物在 `examples/expected/reflow/` 与 `examples/expected/baseline/`，两份 `measure.json` 可直接复算。

自检 `python examples/selftest.py` **11 条**全绿：3 页演示（第 3 页为不规则双栏：左栏短、右栏长、半页宽块插栏中、跨块断词）与真值逐段一致（0 逆序、0 串栏、页眉页脚 6 条全剔除）；`micro-`+`structure` 合成 `microstructure`；朴素基线明显串栏（位置命中 39%、23 逆序、23 错位，作为对照不是分数）；平台入口 `case.json → result.json` 在正例给 `success`；没有真值时记 `partial` + `order_match=None`（不宣称通过）；缺 PDF 给 `rejected`；基线差值表 逆序 23→0、位置命中 39%→100%；缺 `truth.json` 时指标记 `None` 不崩；每页变化页码两页各一条按「页码形态」剔除、正文零泄漏；页边窄块 `role=note` 不进正文；跨页断句记 `continues_from`（上页末段 id）。`--audit` 已实装：串栏疑似 >0 或覆盖率 <95% 以退出码 3 失败，`run.py` 的 success 也卡 `suspicious==0` 与 `coverage>=0.95`。

## 6. 异常与降级

| 情况 | 处置 |
|---|---|
| 三栏及以上 | 按 x 聚类成 n 栏，带内左→右，栏数写入 `reflow.json` |
| 跨页续接 | 上页末段无句末标点、下页首段小写开头 → 下页首段记 `continues_from`（上页末段 id），`reflow.json.continues` 列明，不强行合并 |
| 边注/脚注 | 贴页边窄块（宽 ≤0.3W 且贴左右边）标 `role=note`/`col=note`，页末输出、不进正文；`note_blocks` 留坐标 |
| 图片型表格 | 块内无文本，仅记 bbox，不猜内容 |
| 栏间留白极小 | 判单栏并告警，避免误切 |
| 无文字层 | `cannot_determine` + 建议 OCR |
| 页数 >200 | 按页批处理并落盘 |

## 7. 快速开始

```bash
python scripts/reflow.py --pdf paper.pdf --out out --audit
python eval/measure.py --out out --truth truth.json     # 有真值时
python scripts/reflow.py --pdf paper.pdf --out base --baseline   # 朴素基线
python examples/selftest.py
```

依赖：Python 3.10+、PyMuPDF（fitz）。缺 PyMuPDF 时明确报错，不静默降级。

## 8. 目录结构

```
08-column-reflow/
├── SKILL.md
├── README.md
├── scripts/reflow.py        # 版面判定 + 分带排序 + 清理 + 审计
├── eval/                    # measure.py（真值比对）/ metrics.py / protocol.md / rubric.yaml
├── baseline/cases.md
├── examples/
│   ├── tools/make_demo.py   # 已知真值双栏 PDF 生成器
│   ├── demo/truth.json
│   ├── expected/reflow/     # paragraphs.jsonl / reflow.json / reflow.md / measure.json
│   ├── expected/baseline/   # 朴素基线产物（对照）
│   └── selftest.py
└── environment/resources.yaml
```

## 9. 维护与扩展

- 栏数上限：`reflow.py` 的聚类阈值可调（默认 2 栏，>2 走聚类分支），改动需同步 `references/method.md`；
- 新排版（如"栏内分节 + 侧栏"）：在版面判定阶段加区域标签，排序仍复用"带内左→右"；
- 真值样本可扩充：`make_demo.py` 支持指定页数/栏数/块数，`truth.json` 自动生成，便于加回归用例；
- 若要接 OCR，应作为前置步骤产出块文本，本脚本的角色不变。

## 10. 声明

- 样本由 `make_demo.py` 构造，**非真实论文、非平台案例**；
- 本包未在平台运行，不声称任何平台得分；
- 基线数字是算法对照，不是评分结果。

# 05 · 方法章节：参数有源 + 步骤可做 + 复现九项

**一句话**：把"配置 / 日志 / 代码里的真实参数"与"正文里写的数值"逐项对齐，标出无源值与冲突值；再把方法步骤写成"输入—操作—输出—判断"四要素，并检查复现清单九项是否齐全。三者任一缺失，章节就是"读得通、做不出来"。

只做这一件事：不做翻译、不做润色、不做摘要、不做结果讨论改写。

---

## 1. 为什么是这个单点

方法章节最常见的失分不是"文笔差"，而是**写出来的数没有出处**。基础 Agent 为了句子顺畅，会补一个"看起来合理"的学习率、批大小、温度；审稿人无从核对，复现直接失败。四类问题可以被机器抓出来：

1. **无源数值**：正文有值，配置/日志/代码里都找不到；
2. **冲突值**：正文写 0.001，配置写 0.0005；
3. **关键参数缺失**：来源有学习率/批量/种子，正文没写；
4. **步骤不可执行**：多步操作压成一句，没有输入、输出和判断条件。

v3 把"参数溯源"和"复现清单"做成两个独立脚本，避免"模型自查自己"的循环论证。

## 2. 交付物

| 文件 | 内容 |
|---|---|
| `methods.md` | 目标章节：方法步骤 / 实验设置 / 参数 / 数据 / 对照 / 复现与限制 |
| `params.csv` | 参数台账：`key,value,unit,source,source_locator,status` |
| `repro.md` | 复现清单（九项）与缺口 |
| `audit.json` | 参数与清单的核对结果，供 `result.json` 引用 |
| `result.json` | 契约字段 `case_id` + `status` + `metrics`，**由 `scripts/run.py` 产出**（取自 audit/repro） |

## 3. 参数四状态

| status | 条件 | 处置 |
|---|---|---|
| `sourced` | 正文值与来源一致 | 保留，写 `source_locator`（file:line） |
| `unsourced` | 正文有值、来源找不到 | **必须删掉或标"待作者确认"**，不许留成事实 |
| `conflict` | 正文值与来源不同 | 以来源为准改写；来源自身冲突时列两处并标"待确认" |
| `omitted` | 来源有、正文没写 | 关键参数（学习率/批量/种子/数据版本）必须补进正文 |

## 4. 流程

**第 1 步 建别名表（模型判断，必须来自材料）**

```json
{"params":[{"key":"learning_rate","aliases":["学习率","lr"],"unit":""},
           {"key":"batch_size","aliases":["批大小","batch"],"unit":""},
           {"key":"seed","aliases":["随机种子","seed"],"unit":""}]}
```

别名只收材料里真实出现的写法，不为凑数造同义词。

**第 2 步 抽来源、抽正文、对齐（脚本）**

```
python scripts/param_align.py --draft work/methods.md --params work/params.json \
  --sources work/config.yaml work/train.log work/model.py --out /app/output
```

脚本做三件事：按别名在来源里逐行抽 `key=value`（YAML / 日志 / Python 赋值三种写法）；按别名在正文里抽数值；再用单位词泛扫（`MPa / °C / s / epoch / %`）抓"正文里有数但别名表没覆盖"的漏网值，记 `unsourced_number`。

**第 3 步 写步骤与清单（模型写）**

每个步骤写成表：`步骤 / 输入 / 操作 / 输出 / 判断条件`。多步操作压成一句是主要失分点。

复现九项：代码版本、运行环境（OS/驱动/CUDA 或 Python 版本）、依赖与版本、硬件、数据获取方式、数据版本与划分、随机种子、启动命令、预计轮次/耗时。

**第 4 步 核对清单与步骤（脚本）**

```
python scripts/repro_check.py --manifest work/manifest.json --steps work/steps.json \
  --params /app/output/params.csv --out /app/output
```

**第 5 步 回填**

按 `audit.json` 的 `violations` 改：补来源、删无源值、补清单字段、把限制写到具体失效条件。

## 5. 硬门槛

| 指标 | 定义 | 门槛 |
|---|---|---|
| 有源参数率 | 正文参数中 `sourced` 的比例 | = 1.00 |
| 无源数值数 | `unsourced` + 泛扫出的无源数值 | = 0 |
| 冲突值数 | `conflict` 条数（全部转"待确认"可放行） | = 0 |
| 复现九项覆盖 | 九项中非空项比例 | = 1.00 |
| 步骤四要素完整率 | 四要素齐全的步骤比例 | = 1.00 |
| 限制条件具体率 | 每条限制含具体数值 + 条件/失效场景（只含"规模/条件"字样而无数值判 vague） | = 1.00 |

## 6. 实测证据（构造演示，非平台案例）

`examples/demo/` 是一份构造的实验配置（`config.yaml`、`train.log`、`model.py`）与方法草稿，`examples/expected/` 是真实产物：

- 4 个声明参数（`learning_rate=0.001`、`batch_size=32`、`seed=42`、`weight_decay=0.01`）全部 `sourced`，前三条定位到 `config.yaml:1 / :2 / :4`；
- **有源率 1.00、无源数值 0、冲突 0**；
- 复现九项**覆盖 1.00**，`missing` 为空；
- 步骤四要素**完整率 1.00**，`bad_steps` 为空；
- 限制具体率 **1.00**，`vague_limits` 为空；
- `audit.json` 与 `repro.json` 的 `violations` 均为空、`failed_gates` 为空，`pass=true`。

缺陷注入自检（`python examples/selftest.py`）要求四类破坏全部命中：

| 注入 | 预期违规 |
|---|---|
| F1 正文改值造成冲突 | `param_conflict` |
| F2 正文凭空加带单位/裸小数值 | `unsourced_number` |
| F3 删清单字段 | `repro_field_missing` |
| F4 步骤缺判断条件 | `step_incomplete` |

自检 **14 条**全绿，另覆盖：英文单位裸整数 `200 epochs / 128 channels / 3 blocks` 全部命中且章节编号不误判；限制小节比较式阈值 `2 μm` 免溯源、同节无源实测值 `25 °C` 仍被抓；套话限制"数据规模变化时可能失效"判 `limitation_specificity=0.00` + `limitation_vague`；平台入口（`case.json → result.json`，`status=success`、4 参数全溯源）、`limitations` 置空时 `limitation_specificity=None` + `limitation_missing` + `pass=false`（旧版记 `0.0` 却放过）、裸小数 `0.85` 被抓而章节编号 `3.1–3.4` 不误判、正文零参数时 `sourced_rate=None` + `no_params_declared`、基线对照（Skill `pass` vs 裸 Agent `fail`，九项差 +0.6667、步骤 +1.0、限制 +1.0）、缺 `audit.json`/`repro.json` 的基线段记 `None` 不崩溃。

**上岗入口**：`python scripts/run.py --input /input --output /app/output`，读 `case.json` 的 `draft / params / sources / manifest / steps`，串 `param_align.py → repro_check.py`，写 `result.json`；`status` 由产物判定：`success` 需 `audit.pass` 且 `repro.pass`；有产物未过门槛为 `partial`；完全没给来源文件为 `cannot_determine`（只交待核草稿）；缺方法章节或参数声明为 `rejected`。

## 7. 异常与降级

| 情况 | 处置 |
|---|---|
| 配置与日志数值不一致 | 两处都列，标 `conflict`，正文用"待确认"占位 |
| 只有代码默认值、无运行配置 | 用默认值但注明"默认值，实际运行配置未提供" |
| 数据集版本不明 | 只写名称与规模，版本标"未提供" |
| 随机种子未固定 | 在限制里写"结果不可逐位复现" |
| 参数无单位 | `unit` 留空并备注，不猜单位 |
| 材料只给一半 | `status=partial`，列"缺配置文件/缺日志/缺数据说明"，不补造数值 |

## 8. 快速开始

```bash
python scripts/param_align.py --draft methods.md --params params.json \
  --sources config.yaml train.log model.py --out out
python scripts/repro_check.py --manifest manifest.json --steps steps.json \
  --params out/params.csv --out out
python eval/metrics.py --out_dir out
python examples/selftest.py
```

依赖：Python 3.10+，仅标准库，无网络调用。

## 9. 目录结构

```
05-repro-guard/
├── SKILL.md
├── README.md
├── scripts/          # param_align.py / repro_check.py
├── references/method.md
├── eval/             # rubric.yaml / metrics.py / protocol.md
├── baseline/cases.md
├── examples/
│   ├── demo/         # config.yaml / train.log / model.py / methods.md / manifest.json / steps.json
│   ├── expected/     # params.csv / audit.json / repro.json / repro.md
│   └── selftest.py
└── environment/resources.yaml
```

## 10. 维护与扩展

- 新增参数类型：只需在 `params.json` 加别名，脚本自动纳入对齐与泛扫；
- 新增来源格式（TOML/JSON/INI）：在 `param_align.py` 的 `read_sources` 里加分支，不影响判定；
- 复现九项若按期刊要求增减，改 `repro_check.py` 的 `REPRO_ITEMS` 并同步 `eval/rubric.yaml`；
- 单位换算目前不做（避免猜），如需做，应作为独立函数并输出换算依据，不得静默改写正文值。

## 11. 声明

- 演示配置、日志、数值均为构造，**非真实实验、非平台案例**；
- 本包未在平台运行，不声称任何平台得分；
- 不替作者编造参数来源；`unsourced` 只允许删值或标"待确认"。

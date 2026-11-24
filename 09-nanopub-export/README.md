# 09 · 一句一断言 + 可回解析的结构化导出

**一句话**：把论文结论拆成"一句一断言"，每条只保留主体—关系—客体—限定，绑定逐字原文引文与段落号，导出为四层 JSON-LD + 每条断言一个命名图的 TriG，并当场回解析证明结构可读。

只做这一件事：不做整段摘要、不做综述、不做翻译、不做文献推荐、不做 RDF 推理与签名发布。

---

## 1. 为什么是这个单点

"把结论结构化"最常见的偷懒方式是**整段摘要塞进一个三元组**：主体是"该研究"，关系是"表明"，客体是"某某机制很重要"。看起来是图谱，实际每条都无法判断真假，也无法回原文核对。

v3 把要求钉在四个可机器判定的点：

1. **原子性**：一条断言只能有 1 个句子，不含量词连接（`并且/而且/以及/；/and/此外`），主体与客体不同且非空；
2. **逐字证据**：`quote` 必须是原文**连续子串**，长度 10–400 字符，且包含主体或客体的表面形式；
3. **来源完整**：必须有 `source_id` + `paragraph_id`（JATS 段落号，没有则自定稳定编号，**不编页码**）；
4. **可回解析**：导出的 TriG 必须能被重新解析，命名图数 = 断言数、引文数 = 断言数。

## 2. 交付物

| 文件 | 内容 |
|---|---|
| `result.json` | 契约字段 `case_id` + `status` + `artifacts` + `metrics`，**由 `scripts/run.py` 产出**（数字取自 `validation.json`，不手填） |
| `assertions.json` | 校验后的断言清单（含 `evidence`、`confidence/derivation`） |
| `nanopub.jsonld` | `@context` + 四层结构（assertion / provenance / pubinfo / 命名图） |
| `nanopub.trig` | 每条断言一个命名图 |
| `validation.json` | 原子率/逐字率/来源率/回解析结果 + 逐条违规码 |

## 3. 输入与判据

工作文件两份：

```json
// sources.json
{"sources":[{"source_id":"paper-A","paragraph_id":"p-003","text":"原文段落……"}]}

// assertions.json
{"case_id":"...","paper":{"title":"...","year":2021,"doi":"..."},
 "assertions":[{"id":"a1","text":"...","subject":"...","relation":"increases",
               "object":"...","qualifier":"at 10 MPa","evidence":{"source_id":"paper-A","paragraph_id":"p-003","quote":"..."},
               "confidence":"high","derivation":"direct"}]}
```

关系词封闭 10 个：`increases / decreases / supports / contradicts / uses / measured_by / located_in / composed_of / exceeds / has_value`。需要新关系时，在 `assertions.json` 顶部写 `relation_extensions`，`nanopub.py` 会把它真的并进受控词表（不是只写在文档里），**不许临时造词**。

"约/可能"不进主句：写入 `qualifier`，或 `derivation=inferred`。

## 4. 流程

**第 1 步 拆断言（模型做）**：一句一断言，切句时只在标点后带空白处切，避免把小数 `0.9` 误判成句号。

**第 2 步 绑逐字证据（模型做）**：`quote` 从原文复制粘贴，不改字、不合并两句、不用省略号。

**第 3 步 机器校验 + 导出（脚本，必跑）**

```
python scripts/nanopub.py build --assertions work/assertions.json --sources work/sources.json --out /app/output
```

违规码：

| 码 | 含义 |
|---|---|
| N01 | 非原子（多句 / 含并列连接 / 主客同体） |
| N02 | 引文不是原文连续子串 |
| N03 | 引文长度越界（<10 或 >400） |
| N04 | 证据不含主体或客体的表面形式 |
| N05 | 来源不全（缺 source_id / paragraph_id） |
| N06 | 关系词不在封闭表内 |
| N07 | 重复断言（同主-关-客-限定） |
| N08 | 回解析结果与导出不一致 |

**第 4 步 修到全绿再交付**：`status` 由 `scripts/run.py` 按实际产物判定——`success` 需 `pass=true`、断言 ≥3 条、TriG 回解析成功；有违规或不满足则 `partial`；论文文本都没有则 `cannot_determine`；缺 `assertions.json`/`sources.json` 则 `rejected`。任一硬指标 < 1.00 时写清剩余问题，不许写"通过"。

## 5. 硬门槛

| 指标 | 定义 | 门槛 |
|---|---|---|
| 原子率 | 通过 N01 的断言比例 | = 1.00 |
| 逐字率 | `quote` 为原文连续子串的比例 | = 1.00 |
| 来源率 | `source_id + paragraph_id` 齐全的比例 | = 1.00 |
| 回解析 | TriG 命名图数/断言节点数/引文数与断言数一致 | = true |

## 6. 实测证据（构造演示，非平台案例）

`examples/demo/` 是 1 篇构造文本 + 5 条断言，`examples/expected/` 是真实产物：

- **5 条断言**，`atomic_rate=1.00`、`verbatim_rate=1.00`、`provenance_rate=1.00`；
- 回解析：**5 个命名图 / 5 个断言节点 / 5 条引文**，`ok=true`；
- `violations` 为空，`pass=true`；
- `nanopub.jsonld` 带 `@context` 与四层结构；`nanopub.trig` 每条断言独立命名图。**回解析只做结构计数**（命名图 / 断言节点 / 引文数是否等于断言数），不是完整 RDF 解析——这一点如实标注，不宣称"TriG 解析器已验收"。TriG 的 `rel:subject`/`rel:object`/`rel:relation` 已输出为 IRI 节点（`…/ent/<slug>`、`https://example.org/rel/<slug>`），不再是裸字符串字面量；JSON-LD 与 TriG 的 DOI 统一走 `doi_iri()`，同一篇论文两种序列化给同一个 IRI。
- `prov:wasDerivedFrom` 统一为单一 IRI：纯 DOI 补 `https://doi.org/`，已是 URL/urn 的原样用，缺 DOI 用 `urn:case:<id>`（修掉了旧的 `urn:doi:urn:doi:...` 双前缀畸形）。

缺陷注入自检（`python examples/selftest.py`）要求四类破坏全部命中：

| 注入 | 预期违规 |
|---|---|
| D1 并列句（"A 增加并且 B 降低"） | N01 |
| D2 改写证据（同义替换引文） | N02 |
| D3 缺段落号 | N05 |
| D4 重复断言 | N07 |

5 条断言全绿。

**本轮补强（2026-11-25）**：新增 `scripts/run.py`（读 `/input/case.json` → 校验 → 导出 → `/app/output/result.json`）、N04 纳入逐字率（证据不含主体/客体表面形式会拉低 `verbatim_rate`，实测 5 条里 1 条违规 → 0.80）、零断言时三比率记 `null` 并报 `N00`、`relation_extensions` 真正生效、DOI 统一 IRI、新增 `examples/baseline.py`（裸基线：只把断言转存 JSON，不校验不导出）。自检 **11 条**：原 5 条 + 平台入口、零断言、N04、TriG IRI、基线对照、JSON-LD/TriG DOI 一致性、TriG 主语与关系为 IRI 节点。

## 7. 异常与降级

| 情况 | 处置 |
|---|---|
| 断言跨两段 | 拆成两条，各绑各自段落；不许跨段拼引文 |
| 结论只在图/表里 | 不编造引文；`status=partial`，`uncertainties="结论位于图表，正文无对应句"` |
| 扫描件无文字层 | 不猜；`cannot_determine` + 建议 OCR |
| 同一结论多篇支持 | 每篇一条断言，`derivation=direct`，不合并成"多篇一致" |
| 方向存疑（增/减不明） | `derivation=inferred` + `confidence=low`，`qualifier` 写依据 |
| 预算不足（剩余 <8 请求） | 停止新增，转校验并交 `partial` |

## 8. 快速开始

```bash
python scripts/nanopub.py build --assertions work/assertions.json --sources work/sources.json --out out
python eval/metrics.py --out_dir out
python examples/selftest.py
```

依赖：Python 3.10+，仅标准库（TriG/JSON-LD 以文本生成，不依赖 rdflib），无网络调用。

## 9. 目录结构

```
09-nanopub-export/
├── SKILL.md
├── README.md
├── scripts/nanopub.py       # 校验（N01–N08）+ 双格式导出 + 回解析
├── references/method.md
├── eval/                    # rubric.yaml / metrics.py / protocol.md
├── baseline/cases.md
├── examples/
│   ├── demo/                # sources.json / assertions.json
│   ├── expected/            # assertions.json / nanopub.jsonld / nanopub.trig / validation.json / result.json
│   └── selftest.py
└── environment/resources.yaml
```

## 10. 维护与扩展

- 新增关系词：改 `nanopub.py` 的 `RELATIONS` 表，同时在 `assertions.json` 写 `relation_extensions` 与理由；
- 新增输出格式（如 RDF/XML）：在导出函数加分支，回解析校验同步加一项；
- 接真实 Nanopub 网络：签名与发布应作为独立步骤，本包只保证"结构可读"，不声称已发布；
- 关系词表可按学科收紧/扩展，但**同一批次内必须固定**，避免同义关系混用。

## 11. 声明

- 演示文本、DOI、结论均为构造，**非真实论文、非平台案例**；
- 本包未在平台运行，不声称任何平台得分；
- 回解析通过只证明结构可读，**不证明结论为真**；不做数字签名，不声称已发布到 Nanopub 网络。

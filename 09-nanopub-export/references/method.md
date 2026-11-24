# 方法说明（09）

## 1. 原子性判据
一条断言只能有一个主体、一个关系、一个客体。判据（N01）：
- 文本按 `。！？` 与句号+空格切分后必须只有 1 句；
- 不得含 `并且/而且/以及/；/; / and /此外` 这类并列或递进连接；
- 主体与客体标签不能相同或缺失。
"约/可能/大概"这类模糊词不进主句：要么把区间写进 `qualifier`，要么把 `derivation` 标为 `inferred`。

## 2. 证据为什么必须逐字
转述会引入原文没有的限定。判据（N02）要求 `quote` 是源段落归一化空白后的**连续子串**；N03 限定 10–400 字符，防止"整段当证据"；N04 要求片段至少含主体或客体的表面形式，防止用无关句子凑证据。

## 3. 四层结构
| 层 | 内容 | 字段 |
|---|---|---|
| assertion | 主体-关系-客体-限定 | `rel:subject/relation/object/qualifier/text` |
| provenance | 论文、段落号、原文引文、推导方式 | `prov:wasDerivedFrom`、`rel:paragraphId`、`rel:quote`、`rel:derivation` |
| pubinfo | 案例 id、创建者、许可证 | `rel:caseId`、`rel:creator`、`rel:license` |
| 命名图 | 每条断言一个 `<.../np/An>` 图 | TriG `{ ... }` |

## 4. 为什么要回解析
导出"看起来像 RDF"不等于可被下游读。`build` 写完 TriG 立刻交给 `scripts/trig.py` 真解析（tokenizer + 递归下降，不是正则计数）：括号必须闭合、每条三元组以 `.` 结束、字面量必须闭合且转义合法、主语不得是字面量；语法失败抛 `TrigSyntaxError`（带字符位置）→ N08。解析通过后再数命名图、`np:Assertion` 节点、`rel:quote` 字面量，三者都等于断言数才算 `export_roundtrip=true`。

同一断言在两种序列化里必须是同一组 IRI：JSON-LD 的 `rel:subject`/`rel:object` 写成 `{"@id": ent_iri, "rel:label":…, "rel:entityType":…}`，`rel:relation` 写成 `{"@id": rel_iri}`；TriG 对应写成 `<ent_iri>` 与 `<rel_iri>`，并额外带 `rel:subjectLabel` 等字面量保留人读标签。`compare_serializations()` 逐断言比对主/客/关系三项，任何一项不同即 N09，并给出 `serialization_consistency_rate`。

## 5. 已知边界
- 不做数字签名与 Nanopub 网络发布，只做结构对齐。
- 关系词表是封闭的 10 个词；新关系需显式扩展并记录。
- 证据位置用 JATS 段落号；无页码时不伪造页码。
- 不解析公式与图表内部数值。

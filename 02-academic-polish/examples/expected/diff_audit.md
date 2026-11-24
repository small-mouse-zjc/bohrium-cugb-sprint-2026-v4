# 润色事实台账

- 模式：minimal-edit；改动 2 条，未改动句子 2 条

## 保留率

| 指标 | 值 |
|---|---|
| number_retention | 1.0 |
| citation_retention | 1.0 |
| hedge_retention | 1.0 |
| negation_retention | 1.0 |
| sentence_coverage | 1.0 |
| changes | 2 |
| length_ratio | 0.9 |

## 逐句对齐

| # | 原句 | 润色后 | 相似度 | 事实标记变化 |
|---|---|---|---|---|
| 1 | Gas hydrate (GH) maybe can form in m | Gas hydrate (GH) may form in marine  | 0.933 | ['25 samples', '[3]'] → ['25 samples', '[3]', 'hedge:may:1'] |
| 2 | The dissociation pressure of GH may  | The dissociation pressure of GH may  | 1.0 | 同一组 |
| 3 | We did not observe any dissociation  | We did not observe any dissociation  | 1.0 | 同一组 |
| 4 | It can be seen that the dissociation | The dissociation pressure is sensiti | 0.787 | 同一组 |

## 结论

- 数字/单位、引用、限定词、否定、比较级全部守恒，无未声明的事实改动。
- 提示 `sentence_rewritten`：{'type': 'sentence_rewritten', 'index': 3, 'similarity': 0.787, 'code': 'A02'}

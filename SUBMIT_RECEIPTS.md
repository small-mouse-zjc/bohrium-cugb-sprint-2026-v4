# v3 提交回执（2026-11-24）

账号 `bohr66b36d`；平台 `https://play.bohrium.com/api`；提交方式 `@paper2arm/playground-cli 0.1.57 submit`，`--model doubao --harness doubao-agent`。

| 题 | 挑战 ID | attempt | 包大小 | bundle sha256（前 12） | 状态（提交后查询） |
|---|---|---|---|---|---|
| 01 术语锁定双语对照 | product-arena-01-5a9928c1 | 104862 | 9,913,393 B | 10c4ebaa3b44 | submitted / queued |
| 04 相关工作矩阵 | product-arena-04-4b82ad21 | 104863 | 9,858,944 B | 348172f07e57 | submitted / queued |
| 05 参数溯源与复现 | product-arena-05-64faa4a2 | 104865 | 9,840,180 B | c547737d52d9 | submitted / queued |
| 07 模板适配编译闭环 | product-arena-07-865de7e4 | 104866 | 9,872,520 B | ce2fc786d492 | submitted / queued |
| 08 双栏阅读顺序 | product-arena-08-3027d350 | 104864 | 9,874,830 B | 3d129de236cb | submitted / queued |
| 09 断言与四层序列化 | product-arena-09-0e8befd4 | 104857 | 9,864,755 B | d6e3da365d80 | submitted / queued |
| 10 跨篇归一图谱 | product-arena-10-760d1a0b | 104867 | 9,885,353 B | 701a131e7f31 | submitted / queued |

说明：

1. 七个包各自打包，`outputs/` 下为该包完整内容（SKILL.md、scripts、references、eval、baseline、examples、environment、GITHUB_URL.txt）。
2. 轨迹用本次会话真实运行记录（4419 条消息）导出为 conversation-record JSONL，已截断超长内容并把 `asp_`/`github_pat_`/`sk-`/`ark-`/邮箱替换为 `[REDACTED]`；提交前 `trace validate` 通过。
3. 各挑战配额（limit 10）均未超限：01 used 4、04 used 7、05 used 4、07 used 5、08 used 6、09 used 7、10 used 4。
4. 提交流程里没有修改旧版本、没有覆盖历史 attempt；本文件只记录本次 7 条。
5. 分数尚未回写（`scoring_state=queued`），出分后另记；此处不预填任何分数。

## 第二轮（2026-11-24 22:25，文档深化 + 实编清单，GitHub v4）

代码与结论未变；本轮只改了 README（每包 3.5–5.4k 字符）、补了 01/04/05/08 的契约 `result.json`、把 07 的构建清单换成云主机实编结果（旧 `static_only` 清单保留为对照），`GITHUB_URL.txt` 指向新仓 `bohrium-cugb-sprint-2026-v4`。

| 题 | attempt | 提交后状态 | 该题配额（used/10，本轮后） | 剩余 |
|---|---|---|---|---|
| 01 | 104967 | submitted / queued | 5 | 5 |
| 04 | 104968 | submitted / queued | 8 | 2 |
| 05 | 104969 | submitted / queued | 5 | 5 |
| 07 | 104970 | submitted / queued | 6 | 4 |
| 08 | 104971 | submitted / queued | 7 | 3 |
| 09 | 104972 | submitted / queued | 8 | 2 |
| 10 | 104973 | submitted / queued | 5 | 5 |

第二轮说明：

1. 第一轮的 7 条（104857/104862–104867）仍在队列中，未被修改、未被覆盖；第二轮是**新 attempt**，不是 retry。
2. 轨迹复用同一份脱敏记录（4,431 条事件，`trace validate: valid`）。
3. 每道题本轮只交一次；余量最少的两题（04、09）仍有 2 次。
4. 这一轮的分数尚未回写，出分后另记。

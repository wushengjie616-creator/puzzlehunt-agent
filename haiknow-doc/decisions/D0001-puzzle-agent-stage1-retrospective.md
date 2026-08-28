---
id: D0001
title: Puzzle Agent 第一阶段总结
status: archived
created_at: 2026-08-28
event_date: 2026-08-28
tags: [puzzle-agent, ccbc16, benchmark, retrospective]
related:
  - plans/P0003-24h-ccbc-learning-and-evaluation.md
  - plans/_drafts/P0005-ccbc16-hourly-text-evaluation.md
linked_current:
  - ../docs/01-puzzle-agent-architecture.md
  - ../docs/03-ccbc16-24-case-solution-guide.md
related_commits:
  - cf0155d
  - 06cf18f
  - 7973af4
  - ec4ac25
  - 426cb1f
  - dd87f1e
  - cf7bc32
  - 317717a
archived_at: 2026-08-28
archived_reason: "24题文本测试集与首阶段持续评测的时间点快照"
---

# D0001 · Puzzle Agent 第一阶段总结

## 0. TL;DR

第一阶段完成了一个只通过 CLI 使用、以 DeepSeek 官方 API 的独立单轮请求为推理节点、采用 LangGraph 状态图思想的 PuzzleHunt Agent；建立了 24 道 CCBC16 题的 oracle 隔离文本测试集、独立中间答案门和最终答案门，以及按小时冻结 commit 的人类可读报告链。流程与安全终态已经跑通，但真实复杂题正确率仍为 0，第一阶段完成的是可重复研究与评测基础设施，不是“已经会解全部 24 题”。

## 1. 完成项

| 项 | 结果 | 验证 |
|---|---|---|
| CLI 与低依赖入口 | simple 模式零基础依赖；complex 通过可选 LangGraph/SQLite extra | CLI 生命周期与离线测试 |
| 多阶段状态图 | 观察、联想、子题物化、局部验证、计划、工具、证据评价、中间验证、终局验证 | 24 题离线 cycle 0 error/timeout |
| 阶段性 memory | checkpoint、events、结构化 evidence、open questions 与 unused elements 分账 | session history/branch/resume/finalize 验收 |
| CCBC16 文本测试集 | 10 道直接文本 + 14 道 source-hashed 人工转写，共 24 道 | 每题 `validate_case`；runtime/oracle 隔离 |
| 中间答案评分 | 每题 evaluator-only checkpoints，和 final oracle 分开评分 | `VERIFY_INTERMEDIATES` 与 cycle 双指标 |
| 小时报告 | 14:29 基线 + 15:00 至 20:00 六个正式锚点 | `benchmarks/cycles/hourly-reports/` |
| 报告驱动演进 | 增加子题 DAG、局部证据门、语义恢复、工具契约、协议保守总化 | 128 项测试与真实批次 before/after |
| 方法论 | 从 49 道非 Meta 抽象 TRACE-LIFT 与机制卡 | `research/ccbc16/` |

用户在 20:37 确认 24 题足够作为第一阶段测试集；21:00/22:00 scheduler 随即停止，不补造未运行报告，也不再强求 #30 的十页纸笔题或 #36 的音频进入文本集。

## 2. Agent 工作流

```text
题面/转写
  → intake / artifact inventory
  → observe & classify（事实、异常、风味触发）
  → associate theme（3–5 个本体候选、bridge、预测、反证）
  → materialize subproblems（结构、子题、依赖、候选局部结果）
  → validate subproblems（supported / contradicted / needs-test）
  → hypothesize plan（竞争假设与有界实验）
  → deterministic tools
  → evaluate evidence（覆盖、唯一性、未消费项、是否 replan）
  → verify intermediates（只接受 state 中已有且有 evidence 的载体）
  → verify answer（格式、证据、风味回扣、全线索消费、独立推导）
  → SOLVED / NEEDS_REVIEW / EXHAUSTED
```

这不是 LangGraph 预制 ReAct agent。项目只借用了 `StateGraph + conditional edges + SQLite checkpointer + interrupt/resume/branch`；每个 LLM 节点都向 DeepSeek 发起新的单轮 Chat Completions 请求，跨节点上下文来自本地裁剪后的 `PuzzleState`。正常路径 8 次模型调用；一次语义恢复或证据驱动 replan 最多 10 次。

## 3. 测试集构成

- 直接文本 10 题：3、6、7、8、10、18、21、27、46、48。
- source-hashed 人工转写 14 题：4、9、14、15、22、23、28、29、31、37、38、52、53、54。
- 未继续纳入：#30 需要十页异构逻辑盘和墨迹 mask；#36 需要实际音频听写。用户已明确无需强求。
- 23 道其余非 Meta 依赖动态交互、摄影识别、物理折叠、不可恢复旧题面等通道，不冒充“纯文本可保真”。

每个 case 分离为 runtime `input.json` 与 evaluator-only `oracle.json/rubric.json`。worker 退出后父进程才读取 oracle，避免最终答案或官方中间答案进入 prompt、checkpoint 或工具输入。

## 4. 实测数据

| 时间 | 题数 | final | intermediate | 主要证据 |
|---|---:|---:|---:|---|
| 14:29 | 10 | 0 | 0 | 首次真实 DeepSeek 基线 |
| 15:03 | 10 | 0 | 0 | 暴露空计划、工具失败、长题扁平化 |
| 16:03 | 13 | 0 | 0 | 0 provider error；局部 checkpoint 开始命中 |
| 17:04 | 20 | 0 | 0 | 新局部验证协议过严，8 题 schema error |
| 18:03 | 20 | 0 | 0 | 上一轮局部协议错误消失；3 个网络错误 |
| 19:07 | 21 | 0 | 0 | semantic refinement 实际激活；6 个协议/provider error |
| 20:08 | 23 | 0 | 0 | #3 命中 6/9；20 NEEDS_REVIEW、3 ERROR |

20:00 报告后的三类错误——非法 JSON、恢复结果引用未知子题、计划漏 signal——均被转为带 blocker 的保守 `NEEDS_REVIEW`，并通过 128/128 测试。第 24 题 #23 在阶段结束前完成转写、case validation 和离线 cycle，但没有伪造一轮真实 DeepSeek 结果。

## 5. 关键决策

1. **先保真、后推理**：缺失图片/音频/交互时中断；URL placeholder 不是 artifact。
2. **联想是候选，不是事实**：独立 `ASSOCIATE_THEME` 产生 bridge、holdout prediction 和 falsifier。
3. **复杂题先拆子题**：列表、网格、阶段题和题内 meta 进入显式 DAG。
4. **中间答案必须独立验证**：最终答案正确不能掩盖错误过程；中间命中也不能自动升级 final。
5. **工具只做有界确定性操作**：参数、坐标系、失败状态、fingerprint 和 provenance 都进入账本。
6. **错误输出保守总化**：容错的目标是安全到达 `NEEDS_REVIEW`，不是从残缺 JSON 猜答案。
7. **报告不伪造因果**：答案错误时节点 usefulness 保持 `UNASSESSABLE`，但报告实际激活、写入和问题。

## 6. 未解决问题

- 真实复杂题 final accuracy 为 0；当前主要瓶颈是从风味/结构联想到正确 ontology、系统性解出局部线索、以及把中间载体继续提取为 final。
- DeepSeek 偶发 TLS/read timeout、IncompleteRead 与截断；checkpoint 可恢复，但在线稳定性仍需下一阶段单独验收。
- 通用 CSP/语料检索能力不足，许多逻辑盘、固定作品语料与开放文化知识仍依赖模型或人工。
- 24 题官方标准解法已经形成复盘文档，但不能把 evaluator oracle 直接喂给运行时 agent。
- 逐题复盘还承担数据审计：已修正 #9 evaluator 字符“发→岌”和 #53 上游颜色 `BLUE→PURPLE`，并从空目录重建 24 题 suite；这类修正必须保持 runtime/oracle 边界。

## 7. 可推广经验

- PuzzleHunt 的难点主要不是“再加一种密码”，而是载体切换、异常作为信号、答案仍是载体和多层依赖。
- 风味文本最有价值的角色是缩小 ontology 和解释提取操作；必须配合题面 holdout 检验，不能只靠语义相似。
- 长题要衡量局部 coverage，而不是让模型在整页上写一段漂亮总结。
- 多解题应验证差异和不变量；“找到一个解”不是完成。
- 每次框架改动都应由真实报告中的可复现失败触发，并在新冻结 commit 上复测。

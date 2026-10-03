---
id: P0011
title: Agent 密码资料索引与工具调用
status: completed
created_at: 2026-10-03
paired_task: T0010
acceptance_contract: v1
plan_completed_at: 2026-10-03
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
---

# P0011 · Agent 密码资料索引与工具调用

<!-- 一旦执行此 plan 即冻结；偏差只写到对应 task，不回改本 plan。 -->

## 目标与边界

- 题目标题、题面、提示或备注命中明确密码关键词时，自动注入紧凑的相关资料提示。
- 给复杂 Agent 注册 `cipher_reference_lookup`，按明确查询返回同一资料库中的规则、注意事项与对照表。
- 简单求解器与复杂 Agent 共用 `cipher_reference.py`，不复制网页数据，不把候选当作已证答案。
- 无关键词时不注入冗长表格；工具查询有长度和结果数量边界，不做无界枚举。

## 验收标准

| ID | 必需 | 可观察结果 |
|---|---|---|
| A01 | 是 | “凯撒/ROT/移位、培根、猪圈、栅栏、ASCII、盲文、旗语、A1Z26”等关键词能得到对应紧凑提示 |
| A02 | 是 | 简单 Agent prompt 包含命中的提示，普通文本得到空提示列表 |
| A03 | 是 | 复杂 Agent 初始状态包含命中提示，并可调用 `cipher_reference_lookup(query)` 取得相关对照表 |
| A04 | 是 | 空查询、超长查询和无关查询失败关闭；全部既有测试无回归 |

## 验证

- 按 RED→GREEN→REFACTOR 增加资料索引、简单 prompt、复杂状态及工具注册测试。
- 运行聚焦测试、完整 unittest、JavaScript 语法检查和 `git diff --check`。

## 成稿自审记录

- 用户已明确要求缺失时直接补齐，故采用 approved execution 并直接进入 `in_progress`。
- 当前 dirty 工作树均为同一密码工具功能的上一轮未提交改动；保留原改动，在当前 feature 分支增量实现。
- `haiknow task preflight` 因 dirty worktree 建议停止；该状态已确认不是无关改动，且本轮不切分支、不覆盖文件。
- 资料提示与完整对照表分层，控制 prompt 体积；确定性结果仍需题面独立证据验证。
- 结论：范围有界、授权充分，可以实施。

---
id: T0010
title: Agent 密码资料索引与工具调用
status: completed
created_at: 2026-10-03
paired_plan: P0011
acceptance_contract: v1
plan_completed_at: 2026-10-03
---

# T0010 · Agent 密码资料索引与工具调用

## 实际步骤

- 已确认网页密码资料库尚未接入 Agent；简单链路只有机械候选，复杂链路只有部分解码函数。
- 已按 TDD 补关键词索引、简单 prompt、复杂状态及资料查询工具。
- 关键词 hint 只包含名称、规则、注意事项和 lookup query；完整表格只在工具调用时返回。
- 盲文与 A1Z26 加入 Agent 专用资料记录，复用既有 36 格盲文数据并提供 A–Z 数字表。

## 与计划的偏差

- `haiknow task preflight` 因同一功能分支存在上一轮未提交改动而 stop；已确认这些是 P0009/P0010 的相关改动，未切分支或覆盖无关文件。

## 测试 / 验证

- RED：聚焦测试出现 1 failure + 3 errors，分别证明缺 prompt 区块、索引函数、复杂状态字段和工具注册。
- GREEN：聚焦 `tests.test_cipher_reference tests.test_solver tests.test_complex_domain tests.test_tool_registry` 共 32 项通过。
- 全量：`unittest discover` 共 182 项通过；三个前端脚本 `node --check` 通过；`git diff --check` 通过。
- Mutation 判断：删除关键词索引会使 simple/complex 两条测试失败；移除工具注册会让真实 registry 调用报 Unknown tool，均已由 RED 实际观察。

## 验收逐项处置

| ID | 结果 | 证据 |
|---|---|---|
| A01 | pass | 凯撒关键词与盲文/A1Z26 已知向量测试；8 类 pattern 共用同一索引函数 |
| A02 | pass | simple provider 实际收到 `CIPHER_REFERENCES_JSON`，且不含未命中的猪圈资料 |
| A03 | pass | complex initial state 含盲文 hint；Registry 实际返回 26 项猪圈表 |
| A04 | pass | 空、无关、超长 lookup 均抛错；182 项全量回归通过 |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 关键 commit

- 尚未提交；用户本轮未授权 commit、merge 或 push。

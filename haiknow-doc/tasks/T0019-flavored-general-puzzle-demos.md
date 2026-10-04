---
id: T0019
title: 普通谜题演示风味与推理层次升级
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_plan: P0020
acceptance_contract: v1
---

# T0019 · 普通谜题演示风味与推理层次升级

## 实际步骤

- 2026-10-04：对照 P0019 三份题面与当前 demo replay contract，确认简单度来自题面直接宣布算法，而不是工具层不足。
- 2026-10-04：选择“三层但有扶手”路线：保留现有工具，增加竞争假设、指令型中间结果、错误方向排除与风味化载体。
- 2026-10-04：先扩展 demo contract，旧 manifest 因缺少 `layers` 正确 RED；随后改写三份题面、oracle、工具轨迹与 walkthrough。
- 2026-10-04：重写图片生成器并生成三张 1200×960 题图；人工检查大小写灯态、灯标数量、近回文、星号网格和箭头均清晰。

## 与计划的偏差

| § | 偏差 | 原因 | 影响 |
|---|---|---|---|
| 基线 | preflight 返回 `stop-and-ask`，仍在当前工作树实施 | 用户明确要求继续优化同一批尚未提交的示例 | 不切分支、不提交、不覆盖其他改动；最终明确工作树状态 |

## 关键 commit

- 本轮未获得 commit 授权。

## 测试 / 验证

- RED：`tests.test_general_puzzle_demos...test_three_original_demos_replay_with_registered_tools` 因旧 case 没有三层机制元数据失败，证明新合同不是立即通过。
- GREEN：普通题 demo 2/2；文档与 demo 聚焦 5/5；全量 `unittest discover` 229/229。
- Tool replay：三题依次验证 `TURNBACKTHREE → HARBOR`、唯一排班 `→ ODQWHUQ → LANTERN`、裂距 `→ FOLLOW → SECRET`。
- Mutation：把镜廊最后一步从向西改成向东后，工具轨迹实际输出 `SECREB`，聚焦测试按预期失败；恢复后 2/2 fresh GREEN。
- Visual：三张 1200×960 PNG 人工查看无截断；大小写、灯标、文字、星号与箭头可辨认。
- Hygiene：旧题名、旧答案和旧直白措辞在 active demo 路由中无残留；`git diff --check` 通过；`haiknow sensitive check .` 0 命中。

## 验收逐项处置

| ID | 结果 | 证据引用 | 适用身份 | 承接或授权 |
|---|---|---|---|---|
| A01 | pass | 新测试禁止六类旧版直白提示；三份 puzzle.txt 通过 | current worktree | T0019 |
| A02 | pass | manifest `layers=3`；首步 output 均非最终答案 | current worktree | T0019 |
| A03 | pass | 三份 oracle 含 required_inferences、rejected_hypotheses、signals 完整消费 | current worktree | T0019 |
| A04 | pass | 三份 walkthrough 均含竞争假设与最小可证伪测试等七节 | current worktree | T0019 |
| A05 | pass | ToolRegistry fresh replay 逐步与 literal expected 和 oracle 一致 | current worktree | T0019 |
| A06 | pass | 三张 1200×960 PNG 人工视觉检查 | current worktree | T0019 |
| A07 | pass | general demo README、examples README、manifest、topic index 同步 | current worktree | T0019 |
| A08 | pass | RED/GREEN、229/229、mutation killed、diff/sensitive gates | current worktree | T0019 |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 后续 todo

- 无。本轮未获得 commit、push 或 merge 授权，改动保留在现有工作树。

---
id: T0018
title: 数织提交链路修复与三道普通谜题演示
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_plan: P0019
acceptance_contract: v1
---

# T0018 · 数织提交链路修复与三道普通谜题演示

> 配对 plan：P0019

## 实际步骤

- 2026-10-04：沿前端 `preferred_kind=nonogram`、`/api/intakes`、后台 normalizer 与启动配置逐层排查。
- 2026-10-04：确认前后端题型路由存在；启动配置只读取 `.env.local`，而当前用户配置位于 `.env`。
- 2026-10-04：读取 TRACE-LIFT、CCBC16 机制卡与当前 ToolRegistry 能力边界，确定三题只使用现有确定性工具。
- 2026-10-04：按 TDD 加入 `.env` / `.env.local` / 进程环境优先级合同；Web 在仅有项目 `.env` 时恢复 DeepSeek configured 状态，且状态输出不含 key。
- 2026-10-04：真实提交 10×10 数织图后发现第二层问题：模型曾返回行线索正确、列线索错位，但旧 validator 仍接受。新增行列填充格总数守恒门并强化转写 prompt 后，真实重试得到 10 行、10 列、confidence=0.98，行列线索与 fixture 完全一致并进入 `READY_FOR_CONFIRMATION`。
- 2026-10-04：新增三道原创中等题及图片生成器；每题保存 puzzle、oracle、当前 ToolRegistry 轨迹与 TRACE-LIFT 风格 walkthrough，并接入 README 和主题索引。

## 与计划的偏差

| § | 偏差 | 原因 | 影响 |
|---|---|---|---|
| 基线 | preflight 返回 `stop-and-ask`，但仍在当前工作树继续 | 用户本轮已明确要求开始，且 dirty 内容是上一轮本项目示例/文档改动 | 不切分支、不提交、不覆盖；最终状态明确列出未提交范围 |

## 关键 commit

- 本轮尚未获得提交指令；改动保留在工作树。

## 测试 / 验证

- RED：仅 `.env` 的 Web bootstrap 测试起初返回 configured=false；行列总格数不一致的数织起初未抛错；普通题 demo contract 起初因 manifest 不存在报错。
- GREEN：相关 config/intake/nonogram/Web/纸笔/普通题/文档测试 39/39；全量 `unittest discover` 229/229。
- External：仓库 `nonogram-10x10-image/puzzle.png` 经真实 DeepSeek `/api/intakes` 返回 `READY_FOR_CONFIRMATION`、`kind=nonogram`、10×10、confidence 0.98；规范化线索与 fixture 一致。
- Mutation：临时把数织总格数守恒条件 `!=` 反转为 `==`，新增回归测试按预期失败；恢复实现后全量再次通过。
- Visual：人工查看三张 1100×820 PNG，大小写差异、卡片索引、排序规则、近回文行与答案长度均清晰且未截断。
- Gates：`git diff --check` 通过；`haiknow sensitive check .` 0 命中；docs schema 通过。`haiknow docs drift .` 无 STALE，但四份文档因仓库未设置 `last_verified_commit` 被 skipped，未据此声称全部同步。

## 验收逐项处置

| ID | 结果 | 证据引用 | 适用身份 | 承接或授权 |
|---|---|---|---|---|
| A01 | pass | 临时目录仅写 `.env` 的 bootstrap 回归 + 真实项目启动配置 | current worktree | T0018 |
| A02 | pass | shell > `.env.local` > `.env` 测试；状态对象无 key | current worktree | T0018 |
| A03 | pass | 真实 DeepSeek intake：READY_FOR_CONFIRMATION / nonogram / 10×10 / 0.98 / fixture 等值 | external current run | T0018 |
| A04 | pass | `examples/general-puzzle-demos/` 三个不同 mechanism case，各含五类资产 | current worktree | T0018 |
| A05 | pass | `tests.test_general_puzzle_demos` 逐步调用 ToolRegistry 并与 oracle 对齐 | current worktree | T0018 |
| A06 | pass | 三份 walkthrough 均含观察、联想、调用、中间结果、验证分节 | current worktree | T0018 |
| A07 | pass | 根 README、examples README、demo README 与 topic index 路由；证据边界明确 | current worktree | T0018 |
| A08 | pass | 39/39 聚焦、229/229 全量、mutation killed、三图视觉检查、diff/sensitive/schema gates | current worktree | T0018 |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 后续 todo

- 无。本轮未获 Git 提交指令，全部改动保留在工作树并与前序未提交示例/文档改动共存。

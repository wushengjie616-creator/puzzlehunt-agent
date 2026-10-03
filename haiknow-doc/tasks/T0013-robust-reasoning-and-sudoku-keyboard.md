---
id: T0013
title: 普通谜题鲁棒推理链与数独键盘导航
status: completed
created_at: 2026-10-03
paired_plan: P0014
acceptance_contract: v1
plan_completed_at: 2026-10-04
---

# T0013 · 普通谜题鲁棒推理链与数独键盘导航

## 实际步骤

- 2026-10-03：用户批准 P0014，并要求在当前 Codex session 存活期间无人值守执行到完成。
- 2026-10-03：授权范围确认为本地实现、测试与 commit；不包含真实付费 DeepSeek、push、merge 或公网部署。
- 2026-10-03：Session Loop preflight 除 state selftest 外均通过；已确认当前 HAiKnow runtime 缺少其声明的
  `scripts/tests/test-session-loop-state.sh`，state selftest 以 exit 23 失败。依无人值守安全门停止，尚未派发
  writer，也未修改业务代码。
- 2026-10-03 当时待执行：按 RED→GREEN→REFACTOR 完成 A01–A08；A09 在没有单独付费授权时保持
  conditional/unknown。
- 2026-10-04：用户提交研究资料并再次明确“全部提交！开工！”。本会话在干净 preflight 后顺序执行，不再
  把缺少 session-loop 自检脚本等同为业务实现本身不可进行。
- 2026-10-04：完成数独方向键 clamp 导航；新增独立纯函数模块和 Node 行为 probe，Tab/非方向键返回 null。
- 2026-10-04：完成通用 `expand_symbol_groups`、共享 SSOT 的 Bacon modern26/classic24 变体、输入指纹及
  ToolRegistry 注册；生产代码不含例题 token，例题只作为回归 fixture。
- 2026-10-04：完成 answer constraints、representation hypotheses/assessment、工具 provenance 和机器终局门；
  显式长度不符、表示未通过或未决变体输出冲突均返回 `NEEDS_REVIEW`。
- 2026-10-04：Web 从持久 state 投影五段可审计过程，不追加模型请求。

## 与计划的偏差

- 控制面阻断：HAiKnow v0.33.0 runtime 安装包缺少 Session Loop state focused selftest。修复全局 runtime
  属于本项目计划之外的新权限，不能由主会话静默绕过或自行修改。
- 执行恢复偏差：用户的新一轮明确开工授权后，采用当前会话顺序实施；未声称已恢复 session-loop writer。

## 关键 commit

- 前序基线：`ec22f1c`。
- 本任务实施 commit：包含在本次 P0014 完成提交中。

## 测试 / 验证

- `session-loop-preflight.sh --surface codex --mode session-alive --permissions-confirmed`：FAIL，仅
  `state_selftest=FAIL`，其余 marker/worktree/skill/subagent/lock/runtime IO 均 PASS。
- `session-loop-state.sh --selftest`：exit 23，报告 focused selftest 文件不存在。
- 数独导航 RED：`test_sudoku_keyboard_navigation_clamps_at_edges_without_changing_values` 因脚本不存在失败；
  GREEN 后聚焦测试与 Web API 11 项通过。
- 表示工具 RED：ToolRegistry 报 `Unknown tool: expand_symbol_groups`；GREEN 后 tool/reference 26 项通过。
- 状态/机器门 RED：缺字段、KeyError、错误长度仍被 SOLVED；GREEN 后 domain/graph/session 39 项通过。
- 最终 fresh regression：`python -m unittest discover -s tests -p 'test_*.py' -q` → 201 tests OK；全部 Web JS
  通过 `node --check`；`git diff --check` 通过。

## 验收逐项处置

| ID | 结果 | 证据 | 适用范围 / 承接 |
|---|---|---|---|
| A01 | pass | 纯函数 Node probe + Web route test；边界 clamp、Tab 不拦截 | Web Sudoku |
| A02 | pass | domain/graph tests 覆盖新字段、引用和旧默认 | Complex state |
| A03 | pass | 通用展开逐组输出、宽度/字符集/未知 token/上限测试 | ToolRegistry |
| A04 | pass | 24/26 共享资料 SSOT、显式工具测试 | Cipher variants |
| A05 | pass | 长度、表示 evidence、变体冲突机器门回归 | Runtime gate |
| A06 | pass | `agent-trace.js` 五段投影及 Web 接线测试 | Web general |
| A07 | pass | 正例、宽度反例、无关键词/非 Bacon、歧义和关键词假阳性 | Robustness suite |
| A08 | pass | fresh 201 tests、JS syntax、diff check | Regression |
| A09 | unknown | 真实付费 DeepSeek 尚未授权 | Overall model；conditional，不阻塞 source scope |

## 范围结论

- task_scope: completed
- overall_goal: source implementation complete；真实模型自主发现能力 unknown

## 后续 todo

- 若真实模型发现能力需要证明，另行请求付费调用授权。

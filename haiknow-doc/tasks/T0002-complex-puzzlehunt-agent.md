---
id: T0002
title: 可复用 PuzzleHunt 多阶段解题 Agent 实施
status: completed
created_at: 2026-08-28
plan_completed_at: 2026-08-28
paired_plan: P0002
related_commits: []
---

# T0002 · 可复用 PuzzleHunt 多阶段解题 Agent 实施

配对计划：[P0002](../plans/P0002-complex-puzzlehunt-agent.md)。

## 与计划的偏差

- `session run --max-calls` 在实现中收敛为 `session init --max-calls`：预算成为 session 不可变初始契约，避免运行中静默放宽；benchmark run 仍显式接受 `--max-calls`。
- 兼容 spike 证明 LangGraph 传递安装 `langchain-core`/Pydantic 2；因此 complex extra 必须推荐项目 `.venv`，共享 Conda 已恢复原 Pydantic 1.10.19。
- 第一闭环实现统一 ToolRegistry，而未为每类谜题建立独立 LangGraph subgraph；当前节点可按 plan 调度 cipher/extraction/grid/meta 工具，知识检索和更专门 subgraph 留待真实 benchmark 证据。

## 实际步骤

- [x] 用户批准架构草案。
- [x] 将草案提升为 P0002，进入执行并冻结正文。
- [x] 验证 LangGraph 1.2.11 + SQLite checkpointer 3.1.1 + 直接 provider 的最小兼容组合。
- [x] 以 TDD 实现领域 state、预算和 transition。
- [x] 以 TDD 实现 graph skeleton、interrupt/resume 与 checkpoint branch。
- [x] 实现逐节点 LLM contract、确定性 ToolRegistry 与 CLI。
- [x] 建立 CCBC16 机制蒸馏和原创 derived benchmark 工厂。
- [x] 同步 README、架构与设计学习日志。

## 关键 commit

本项目当前不是 Git 仓库，无 commit 可记录。

## 测试 / 验证

- 兼容 spike：最小 StateGraph 输入 `value=1`，SQLite checkpoint 后输出 `value=2`，可读取 3 个历史 snapshot。
- 依赖事实：LangGraph 1.2.11 会安装 `langchain-core`/Pydantic 2；共享 Conda 环境存在 Pydantic 1 约束，最终 complex 体验必须使用项目 `.venv` 隔离。
- 基线测试修正：`test_live_mode_without_key_has_actionable_error` 原先会读取工作区 `.env.local`；现改为临时 cwd，聚焦 CLI suite 3/3 通过且不读取/输出用户 key。
- TDD RED：初始 state 缺契约/预算校验；graph 零调用；session 无持久化；CLI 无 session/benchmark；artifact 无 interrupt；工具 registry 空实现；derived suite 为空；确定性工具结果未写入 extraction ledger；各项均先观察目标行为失败再写最小实现。
- complex GREEN：项目 `.venv` 运行 `python -m unittest discover -s tests -v`，36/36 通过。
- base GREEN：共享 Python 保持空 runtime 依赖，运行同一命令 36 项均成功，其中 11 项 complex-only 测试按能力 gate 跳过；Pydantic 保持 1.10.19。
- derived benchmark：8 个 dev + 2 个 blind case 通过 input/oracle 隔离与答案字面泄漏检查；offline benchmark 输出不含 oracle。
- 文档审计：所有 Markdown 本地链接存在；repo-wide 占位符扫描无 `TODO/FIXME/NotImplemented/stub` 命中；CLI help 与 README 命令面一致。
- HAiKnow 原生 Windows 当前不支持 `docs diagnose` / `docs drift`，两条命令均明确返回 unsupported；已按工作流使用 schema 检查加手工 frontmatter、链接、索引和代码/文档契约核对作为 fallback。
- 未运行真实 DeepSeek benchmark：该操作会产生多次计费请求，按计划保持显式 opt-in。

## 敏感边界审计

| 边界 | 正向路径证据 | 负向 / 泄漏证据 |
|---|---|---|
| `.env.local` → DeepSeek CLI | 配置加载测试证明只消费三个受支持键且 shell 优先；本地 key 已配置且文件被忽略 | CLI 错误与模拟 API 错误测试均断言不输出 key |
| provider → session checkpoint | `SessionManager.run` 后可由新 manager 恢复 state/history | 注入 sentinel key 后扫描 session 全部持久化字节，sentinel 不存在 |
| benchmark input → provider → evaluator | runtime 只由 `input.json` 构造 puzzle；oracle 仅在评分阶段独立读取 | validator 曾实际拦截标题中的答案字面泄漏；CLI 输出测试断言无 oracle/expected answer |

## 后续 todo

- 无本计划内遗留项。用户可另行显式运行 `benchmark run --provider deepseek` 收集真实模型能力证据；默认不计费。

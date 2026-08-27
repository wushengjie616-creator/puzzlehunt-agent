# Puzzle Agent 当前架构

## 1. 双模式边界

系统保留两个相互兼容的入口：

| 模式 | 目标 | 模型调用 | 依赖 |
|---|---|---|---|
| simple | 文本题与常见密码的快速单次求解 | 有效输入恰好一次 | Python 标准库 |
| complex | 长运行 PuzzleHunt、多阶段工具反馈、artifact 与 meta | 多个独立单轮节点，受预算限制 | 可选 LangGraph + SQLite checkpointer |

`PuzzleInput`、DeepSeek provider 和确定性工具不依赖 LangGraph。simple mode 不会因为 complex mode 增加基础依赖。

## 2. Simple 数据流

```text
PuzzleInput
  → CipherWorkbench
  → build_messages
  → OfflineProvider / DeepSeekProvider（一次）
  → SolveResult
```

simple mode 仍遵守：输入无效零调用；有效输入一次调用；API/JSON/schema 错误不自动重试。

## 3. Complex StateGraph

```text
INTAKE
  → ARTIFACT_INVENTORY
      ├─ missing → HUMAN_INTERRUPT → ARTIFACT_INVENTORY
      └─ ready
  → OBSERVE_CLASSIFY              # LLM call 1
  → HYPOTHESIZE_PLAN              # LLM call 2
  → TOOL_DISPATCH                 # zero LLM calls
  → EVALUATE_EVIDENCE             # LLM call 3
  → VERIFY_ANSWER                 # LLM call 4
  → SOLVED | NEEDS_REVIEW | EXHAUSTED
```

四个 LLM node 都调用同一个 `DeepSeekProvider.complete()`，每次是 stateless single-turn Chat Completions 请求。本地 state 被裁剪成当前节点所需 JSON 后注入下一次请求，不依赖 DeepSeek 服务端会话。

### 强制阶段纪律

- 观察轮只能写事实、异常和有触发词的风味联想，不提交答案。
- 计划轮至少保留两个 competing hypotheses，并选择可判别实验。
- 工具轮只运行白名单确定性工具，结果带 provenance 写入 evidence。
- 评价轮必须消费工具或人工产生的新 evidence。
- 验证轮检查格式、证据、风味/标题回扣；不足时返回 null/`NEEDS_REVIEW`。
- 预算耗尽返回 `EXHAUSTED`，不继续调用或编造结果。

## 4. PuzzleState

框架中立 state 是 JSON 兼容映射，主要分区为：

- immutable `puzzle`、`artifacts`、`required_artifacts`
- `observations` 与 `flavor_associations`
- `hypotheses`、`plan`、`attempts`、`evidence`
- `intermediate_answers`、`extractions`、`answer_candidates`
- `open_questions`、`missing_artifacts`、`blockers`
- `budget`、`stage`、`status`、`last_node`、`next_node`
- `final_answer`

系统不保存私有思维链；只保存可协作的结论、证据、实验、失败记录和简洁推理摘要。

## 5. 持久化与恢复

每个 session 使用独立目录：

```text
.puzzle-agent/sessions/<id>/
  puzzle.json
  checkpoint.sqlite
  events.jsonl
  artifacts/
  final.json
```

- LangGraph checkpoint 是可恢复运行状态的 SSOT。
- SQLite 每个节点边界形成历史 snapshot；CLI 可以读取历史并从指定 checkpoint 建新分支。
- `events.jsonl` 是面向人的审计日志，不与 checkpoint 竞争写入语义。
- `interrupt()` 保存缺失 artifact 状态；`Command(resume=...)` 将用户转写并入 state 后继续。
- state 限制为 JSON 兼容类型，并设置 strict msgpack；不启用 pickle fallback。
- `final.json` 只在 `SOLVED` 后生成。

## 6. 工具层

`CipherWorkbench` 负责高召回密码候选；`ToolRegistry` 负责模型可计划调用的确定性工具：

| 工具 | 契约 |
|---|---|
| `cipher_workbench` | 有限候选、字符预算、已知 key 才运行 Vigenère |
| `extract_nth` | 1-based 逐行索引，越界失败 |
| `anagram_delta` | multiset subset 校验，保留源顺序 |
| `read_grid_path` | 矩形网格、坐标边界、四邻接校验 |
| `dependency_order` | meta DAG 拓扑排序、未知依赖和循环检测 |

每次调用用 tool+arguments fingerprint 去重。未知工具或参数错误形成 failed attempt，不进入成功 evidence。

## 7. 模块责任

| 模块 | 责任 |
|---|---|
| `domain.py` | simple 输入、候选与输出 |
| `complex_domain.py` | complex 初始 state 与预算 |
| `complex_graph.py` | StateGraph、节点 prompt contract、条件边和工具调度 |
| `complex_session.py` | SQLite session、interrupt/resume、history、branch、finalize、event/artifact |
| `complex_offline.py` | 无网络的 staged demonstration provider |
| `tool_registry.py` | 框架中立确定性 puzzle 工具 |
| `benchmark.py` | runtime input loader、case validator、隔离 evaluator |
| `automation.py` | allowlist staging、secret gate、稳定快照验证、Git commit/push 与 watcher heartbeat |
| `providers/deepseek.py` | DeepSeek 官方 Chat Completions 适配器 |
| `cli.py` | simple、session、benchmark 与 automation CLI |

### Git 自动发布边界

watcher 每轮先对 allowlisted 工作树内容做 fingerprint，运行完整测试后再次计算；测试失败或验证期间内容变化均不提交。随后只暂存白名单路径，对 staged blob 做 secret scan，并在 evaluation lock 存在时延期。`.env.local` 和 `.puzzle-agent/` 必须保持 ignored；未知根文件由 owner 明确分类后才可发布。

## 8. 依赖策略

`pyproject.toml` 的 base `dependencies=[]`。complex 只存在于 optional extra：

- `langgraph>=1.2.11,<2`
- `langgraph-checkpoint-sqlite>=3.1.1,<4`

LangGraph 实际会传递安装 `langchain-core` 与 Pydantic 2，因此推荐项目 `.venv`。项目没有使用 LangChain agent abstraction、tool decorator、model adapter 或 LangSmith 服务。

## 9. Benchmark 隔离

CCBC16 是离线机制学习来源，不是 runtime 题库：

```text
official puzzle/solution（仅开发者研究）
  → abstract mechanism note
  → original derived input
  ├─ input.json       → runtime 可见
  ├─ artifacts/       → runtime 可见
  ├─ oracle.json      → evaluator only
  ├─ rubric.json      → evaluator only
  └─ provenance.json  → validator/evaluator only
```

validator 递归拒绝 input 中的 `answer/solution/oracle` 字段，并检查答案字面泄漏、官方来源和原创声明。benchmark 输出只报告正确与否，不输出期望答案。

## 10. 当前边界

- DeepSeek API text-only；图片、音频、版式与交互必须先转写为 artifact。
- 当前确定性 grid/CSP 能力是基础组件，不等于完整填字/数独/图像识别引擎。
- knowledge research subgraph 尚未接外部搜索 provider；没有可靠事实时保持 unknown。
- offline provider 只验证系统流，不代表真实复杂解题能力。
- 真实 DeepSeek benchmark 明确 opt-in，默认测试绝不计费。

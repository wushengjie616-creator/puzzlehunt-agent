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
  → OBSERVE_CLASSIFY              # LLM call 1：事实与 surface tension
  → ASSOCIATE_THEME               # LLM call 2：ontology beam、bridge、预测与反证
  → MATERIALIZE_SUBPROBLEMS       # LLM call 3：显式子题、分组、依赖与候选载体
  → VALIDATE_SUBPROBLEMS          # LLM call 4：局部答案的语义/转录证据门
      ├─ semantic coverage < 50%、未恢复且剩余预算 ≥ 6
      │    → PREPARE_SEMANTIC_REFINEMENT   # zero LLM calls
      │    → MATERIALIZE_SUBPROBLEMS → VALIDATE_SUBPROBLEMS（至多一次）
      └─ otherwise
  → HYPOTHESIZE_PLAN              # LLM call 5：机制承诺与有界实验
  → TOOL_DISPATCH                 # zero LLM calls
  → EVALUATE_EVIDENCE             # LLM call 6
  → VERIFY_INTERMEDIATES          # LLM call 7：中间载体证据门
  → VERIFY_ANSWER                 # LLM call 8
  → SOLVED | NEEDS_REVIEW | EXHAUSTED
```

八类 LLM node 都调用同一个 `DeepSeekProvider.complete()`，每次是 stateless single-turn Chat Completions 请求。本地 state 被裁剪成当前节点所需 JSON 后注入下一次请求，不依赖 DeepSeek 服务端会话。正常路径八次调用；一次 evidence-driven replan 或一次 pre-plan semantic refinement 使用十次，二者不会在同一运行中叠加。

### 强制阶段纪律

- 观察轮只能写事实、异常和有触发词的风味联想，不提交答案。
- 子问题物化轮先把列表、网格、阶段题和 meta 拆成可单独检查的工作单元；大题保留总数、分组和依赖，并选择代表性单元，不把 100+ 条线索压成一段摘要。
- 子问题验证轮把每个非空局部答案精确分入 supported、contradicted 或 needs-test；只有值不漂移、引用真实 signal 且给出 prediction/falsifier 的 supported 结果才能进入 evidence，无支持结果的子题必须显式 unresolved。
- 首轮局部语义覆盖不足一半时，框架可在计划前做一次恢复轮：已验证结果视为不可变锚点，未解单元重新物化；完全没有锚点时只生成 1–3 个题面可落地的高杠杆候选。恢复后禁止再进入工具重规划，保证总预算仍有界。
- 计划轮至少保留两个 competing hypotheses，并选择可判别实验。
- 每个工具计划必须引用可见 signal，给出具体 prediction 与 falsifier；空计划保持为空，不再暗中回退到通用密码 shotgun。
- 工具轮只运行白名单确定性工具，结果带 provenance 写入 evidence。
- 评价轮必须消费工具或人工产生的新 evidence。
- 中间验证轮只接受已存在且引用真实 evidence ID 的 carrier/instruction/ordering/parameter；原始中间猜测不能直接通过。
- 验证轮检查格式、证据、风味/标题回扣；不足时返回 null/`NEEDS_REVIEW`。
- 验证响应中的未知局部 result ID 被忽略且不产生 evidence；终局漏填的 required check 由机器补为 `false`。两者都会留下问题标记并安全停在 `NEEDS_REVIEW`，不会因保守总化而提升答案。
- 预算耗尽返回 `EXHAUSTED`，不继续调用或编造结果。
- DeepSeek 的显式网络传输失败可从同一 checkpoint 重试同一节点一次；JSON、schema 和业务协议错误不重试，避免把非幂等状态或错误输出静默吞掉。

## 4. PuzzleState

框架中立 state 是 JSON 兼容映射，主要分区为：

- immutable `puzzle`、`artifacts`、`required_artifacts`
- `observations`、`flavor_associations`、`structure_model`、`subproblems`、`subproblem_results`、`validated_subproblem_results` 与 `subproblem_validation`
- `hypotheses`、`plan`、`attempts`、`evidence`
- `intermediate_answers`、`validated_intermediate_answers`、`intermediate_validation`、`extractions`、`answer_candidates`
- `open_questions`、`missing_artifacts`、`blockers`
- `budget`、`semantic_refinement_used`、`stage`、`status`、`last_node`、`next_node`
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

分支建立时使用 `graph.update_state(..., as_node=last_node)` 在新 thread 中重建所选 snapshot 的执行游标，并核对新 snapshot 的 `next` 与原 checkpoint 完全一致；仅复制 state 而不复制游标会错误地从 `START` 重跑。

## 6. 工具层

`CipherWorkbench` 负责高召回密码候选；`ToolRegistry` 负责模型可计划调用的确定性工具：

| 工具 | 契约 |
|---|---|
| `cipher_workbench` | 有限候选、字符预算、已知 key 才运行 Vigenère |
| `extract_nth` | 1-based 逐行索引，越界失败 |
| `anagram_delta` | multiset subset 校验，保留源顺序 |
| `read_grid_path` | 矩形网格、坐标边界、四邻接校验 |
| `dependency_order` | meta DAG 拓扑排序、未知依赖和循环检测 |
| `caesar_shift` / `atbash_transform` / `base_decode` / `morse_decode` | 显式编码约定的经典转换；无效编码失败 |
| `vigenere_decode` / `rail_fence_decode` | key 或栏数必须已知，不在工具内猜测 |
| `a1z26_decode` / `interleave_sequences` | 参数化基础恢复与提取，不从题面猜参数 |
| `grid_trace` / `grid_transform` | 明确坐标、方向和变换，越界或非矩形失败 |
| `constrained_order` | 最多 9 项的先后/紧邻/首尾约束，区分 SAT/UNSAT/AMBIGUOUS |
| `decode_bit_patterns` / `repair_mojibake` | 位序显式；编码链必须 allowlist + strict round trip |
| `bounded_mojibake_scan` | 最多两层、固定编码对、严格 round trip；返回无评分候选和完整 codec path |
| `minesweeper_propagate` | 有界矩形雷区，只应用确定性八邻域传播；停滞时不猜测或回溯 |
| `common_symbol_intersection` | 共有符号及各字符串位置，可要求唯一 |
| `phone_keypad_decode` / `braille_decode` / `playfair_codec` | 固定约定的常见密码，非法或歧义输入不猜 |
| `decode_token_morse` / `solution_position_analysis` | 显式点划 token；比较多解的逐位不变量与差异，不只返回第一个解 |
| `palindrome_mismatch` / `unicode_inspect` | 回文镜像错位载体；保留易混 Unicode 字符的码位、名称和类别 |

每次调用用 tool+arguments fingerprint 去重，replan 中相同调用记录为 `duplicate_skipped` 而不再次执行。未知工具或参数错误形成 failed attempt，不进入成功 evidence。

规划 prompt 的工具签名由 `inspect.signature()` 对 ToolRegistry 当前 callable 生成，例如 `a1z26_decode(values)`、`grid_trace(grid, start, directions)`。ToolSpec 在同一注册点补充紧凑前置条件，例如 0-based 坐标、`N|E|S|W`、等长字符串和 constraint object shape。只列工具名已被 cycle 2 证伪；只有签名又在 cycle 3 暴露类型/前置条件错误，因此两者都属于执行契约。

阶段 memory 不是对话历史，而是结构化状态：`observations` 与 `flavor_associations` 保存题面事实和可检验联想，`attempts/evidence/extractions` 保存机械实验账本，`intermediate_answers` 保存候选载体，`validated_intermediate_answers` 只保存通过独立证据门的中间结果，`open_questions` 与 `unused_elements` 保存尚未闭合的推理债务。没有验证过的中间结果、或后两项非空时，机器终局门都不能接受 `SOLVED`。

周期报告不读取模型私有思维链。每个节点 trace 额外记录可观察效果：观察/联想数量、假设与计划数量、工具成功/失败和 extraction 增量、评价的 verify/replan 决策、阶段 memory 债务，以及终局是否接受答案。错误题的因果 usefulness 仍标 `UNASSESSABLE`，但报告会显示实际行为及 `FAILED_TOOL_CALLS`、`EMPTY_PLAN`、`PROVIDER_ERROR` 等问题，不再只给空泛激活率。

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
| `cycle_runner.py` | 有界并发 worker、进程树 timeout、step trace、oracle 后置评分和节点报告 |
| `cycle_scheduler.py` | T+3h…T+24h 可恢复调度、冻结/发布门与 perfect-score hard gate |
| `hard_runner.py` | 49 道非-meta官方题的一次性临时转换、限并发执行、脱敏报告与缓存清理 |
| `providers/deepseek.py` | DeepSeek 官方 Chat Completions 适配器 |
| `cli.py` | simple、session、benchmark 与 automation CLI |

### Git 自动发布边界

watcher 每轮先对 allowlisted 工作树内容做 fingerprint，运行完整测试后再次计算；测试失败或验证期间内容变化均不提交。随后只暂存白名单路径，对 staged blob 做 secret scan，并在 evaluation lock 存在时延期。`.env.local` 和 `.puzzle-agent/` 必须保持 ignored；未知根文件由 owner 明确分类后才可发布。

### 周期评测与节点作用

父进程只把 `input.json` 交给 worker；worker 逐节点调用 `SessionManager.step()`，记录公开 state 的字段变化、evidence ID 和 wall time。五个 worker 并发且各自受 monotonic deadline 约束。父进程等待 worker 退出后才读取 oracle，写 `correct/rubric_score`；因此 oracle 不进入 prompt、checkpoint 或 worker trace。

节点报告只依据可观察数据。正确证据链中的写入节点可标 `HELPFUL/ESSENTIAL`；错误答案时保持 `UNASSESSABLE`，避免从失败运行反推虚假的节点因果作用。每轮还生成 `node-summary.json` 和 analysis 中的全节点聚合表，列出跨题激活数、总次数、耗时、写入字段、evidence 数、作用标签计数与未激活/无可观察效果问题。

证据评估默认进入中间验证，再进入终局验证；若它显式给出 `decision=replan` 且剩余预算至少能容纳“新规划 + 新评估 + 中间验证 + 最终验证”，则回到 `hypothesize_plan`。第二轮能读取上一轮 attempts/evidence，工具和 assessment ID 跨轮次保持唯一。默认 `max_calls=10`；正常路径使用八次，单次 replan 路径使用十次，不形成无限 ReAct loop。

`ASSOCIATE_THEME` 是独立发现阶段：输入观察、surface tensions、题面与既有 memory，输出 3–5 个 ontology candidates、bridge、association role、holdout prediction 和 falsifier。它不能看到 ToolRegistry；只有 `HYPOTHESIZE_PLAN` 才接收工具签名与契约，防止工具名反向泄露机制。

`MATERIALIZE_SUBPROBLEMS` 位于 ontology discovery 与工具规划之间。它把题面结构写成 `structure_model`，把可独立求解单元写成 `subproblems`，并把尚未成为证据的语义候选写进 `subproblem_results`。这些 provisional result 不会绕过 evidence gate；它们的作用是让后续计划面向具体 clue unit，而不是对整页内容盲试转换。

`VALIDATE_SUBPROBLEMS` 是独立的局部答案证据门。16:00 批次在 89 个局部单元里产生了 33 个非空结果，但零个被正式提升为 evidence；其中 #3 已接近解出 8/9 个 clue answer，晚期验证只保留 2 个。新节点因此要求三分覆盖、值不可变、signal provenance 与可证伪依据，并只把 supported 结果写入 `validated_subproblem_result` evidence。

模型输出契约与运行时状态契约并不等价。17:00 批次中，模型漏掉某个 verdict、把同一候选放进多个 verdict，或给出漂移后的 accepted value 时，旧实现会抛异常并截断整条图。现在运行时对“已知候选的不完整/矛盾判断”做保守总化：遗漏、冲突和漂移值统一降级为 `needs_test`，空结果 verdict 被忽略，`unresolved_subproblem_ids` 由 accepted 结果重新计算；只有引用完全未知 result ID 的响应仍被硬拒绝。这个容错只保证流程继续，不会把不可靠结果提升为 evidence。

`VERIFY_INTERMEDIATES` 同样执行状态一致性门：模型只能逐字复制 `intermediate_answers` 中已存在的 value，且 evidence IDs 必须是源中间项已有引用的非空子集。评分器的模糊包含匹配只用于至少两个归一化字符的值，避免单字符别名在无关长文本中产生假阳性。

每个 LLM 节点都有显式字符预算，并把单个字符串限制为 240 字符。预算按节点产物规模分配；例如 `ASSOCIATE_THEME` 为 3500 字符，而需要枚举题面单元的 `MATERIALIZE_SUBPROBLEMS` 为 9000 字符。DeepSeek 请求允许最多 16384 output tokens，以免 4096 的旧上限截断结构化阶段结果；这是生成上限而非固定消耗。若 DeepSeek 返回 `finish_reason=length`，provider 会报告截断错误，不会尝试猜补残缺 JSON 或把部分输出写进证据。

中间载体门有一个机器可证的窄例外：若结构明确为 `atomic`、恰有一个子题、无 unresolved 局部单元、存在与 answer candidate 同值的 `semantic_derivation`、且同一值被成功确定性工具独立复现，则 `distinct_from_final=false` 可以形成 `direct_answer_ready`。这不是跳过 `VERIFY_INTERMEDIATES`；节点仍检查值来源、evidence 子集和可复现性。列表、网格、staged、meta 与 hybrid 结构不能使用这个例外。

终局还有一个机器门：若当前计划要求确定性工具，但所有相关 attempt 都失败，则即使模型返回全真 checks，也只能进入 `NEEDS_REVIEW`。这防止 cycle 2 中“工具全失败却把猜测标为 evidence-backed”的错误。

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

若原创五题在某个正式周期达到 5/5，scheduler 调用一次 `hard_runner`。官方 JSON 只进入 `.puzzle-agent/hard-cache/`，转换器剥离 `answer/solution` 后才生成 worker input；含图片或互动脚本的题会声明 `required_artifacts`，URL placeholder 不算 artifact。父进程评分结束仅持久化题号、状态、耗时、调用数和错误分类，随后删除临时题面、oracle、checkpoint 与模型答案。`once-result.json` 在网络请求前即写入，因此失败也算一次 attempt，不会静默重试。

## 10. 当前边界

- DeepSeek API text-only；图片、音频、版式与交互必须先转写为 artifact。
- 当前确定性 grid/CSP 能力是基础组件，不等于完整填字/数独/图像识别引擎。
- 49 道 CCBC16 非 Meta 已完成表面分类：10 道直接文本、12 道 source-hashed 人工转写、4 道待转写、23 道无法仅用文本忠实表达；当前可运行官方文本套件为 22 道。转写 final feeders 时还必须带入人类在解锁该题时已经拥有的上游 Meta 答案、网格或操作符，不能只抄当前图片。
- knowledge research subgraph 尚未接外部搜索 provider；没有可靠事实时保持 unknown。
- offline provider 只验证系统流，不代表真实复杂解题能力。
- 真实 DeepSeek benchmark 明确 opt-in，默认测试绝不计费。

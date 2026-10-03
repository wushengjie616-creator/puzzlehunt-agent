# Puzzle Agent 当前架构

## 1. 三入口边界

系统保留两个相互兼容的入口：

| 模式 | 目标 | 模型调用 | 依赖 |
|---|---|---|---|
| simple | 文本题与常见密码的快速单次求解 | 有效输入恰好一次 | Python 标准库 |
| complex | 长运行 PuzzleHunt、多阶段工具反馈、artifact 与 meta | 多个独立单轮节点，受预算限制 | 可选 LangGraph + SQLite checkpointer |
| local web | 文字/图片统一规范化、确认、纸笔组件或 complex session | 至少一次 DeepSeek NORMALIZE_INPUT；后续按组件 | 可选 `[web]`（FastAPI/Uvicorn/Pillow + complex） |

`PuzzleInput`、DeepSeek provider 和确定性工具不依赖 LangGraph。simple mode 不会因为 complex mode 增加基础依赖。

Web 默认仅监听 `127.0.0.1`。站点把题目入口、`/paper-puzzles` 纸笔栏目和 `/cipher-tools` 密码工具拆成
三个可直接访问的页面。写请求同时受随机 capability token、Host、Origin、Content-Type 门保护，不提供
账号系统，也不把 API Key、原图或 base64 放入浏览器响应和事件。原图只在内存中经过解码、像素限制与
重编码，规范化线程结束后释放。

`/api/bootstrap` 只返回 DeepSeek 是否已配置、视觉/Agent 模型名和非敏感提示，不返回 Key。未配置时首页
在提交前禁用规范化并提示创建 `.env.local`；“已配置”仅表示 Key 存在，不代表网络、余额或凭据已通过
付费探测。当前默认视觉模型为 `deepseek-flash`，使用官方 OpenAI-compatible Chat Completions 的
`image_url` data URL 输入。

## 2. Web 规范化与纸笔组件

```text
text / image / mixed
  → upload safety gate
  → DeepSeek NORMALIZE_INPUT (deepseek-flash content parts + optional preferred_kind)
  → schema + editable puzzle structure validation
  → editable user confirmation
  → strict puzzle validation
  → signed source/envelope/canonical receipt
  → Sudoku / Nonogram / RulePuzzle gateway / existing complex SessionManager
```

首页支持点击选择和拖拽图片，但两条路径共用同一套 MIME、magic、大小、像素与重编码安全门。题型可选
auto/general/sudoku/nonogram/rule_puzzle；纸笔子页通过 allowlist query 预选，服务端再次校验。显式题型进入 normalizer
prompt，输出 kind 不一致即失败关闭，不能静默落到通用 Agent。

确认阶段按题型渲染编辑器，而不向玩家暴露 canonical JSON：Sudoku 使用可编辑 N×N 网格并依据
`box_rows/box_cols`（标准 9×9 默认 3×3）绘制粗分宫线，Nonogram 使用行列线索表，rule_puzzle 使用规则、
实体和线索编辑器，general 使用文本框。
Sudoku 编辑器实时检测行、列、宫内的重复数字并标红冲突格。编辑器只负责提示和收集输入，最终 canonical
仍由服务端严格 validator 校验并绑定确认回执。方向键使用纯函数计算相邻坐标并在边界 clamp，不环绕、
不改值；Tab、数字和删除不被拦截。

普通 9×9 数独的视觉 prompt 明确忽略截图 UI，只抄录盘内印刷数字，不求解，并要求整数 1..9 / `null`
矩阵。模型若只在 JSON 表示层产生无歧义噪声（数字字符串，或以 `0`、`.`、空字符串表示空格，或给出
字符串 symbols），normalizer 在验证前收敛为标准 1..9 矩阵并追加 warning；无法证明属于标准数独的字符和
错误尺寸在识别阶段拒绝。重复 clue 或候选矛盾不由程序猜测修补，而是携带 warning 进入可视化确认；未被
玩家修正时，确认端的严格 Sudoku validator 拒绝签发回执。

普通数独组件维护 N×N grid 与逐格 candidates，按固定顺序循环裸单、行隐单、列隐单和宫隐单。每次赋值
包含 technique、target、value、premises、中文观察说明及前后 state fingerprint；replay verifier 从 givens
重新生成同一确定性步骤。`solve_mode=next_step` 最多赋一个数并返回 `STEP_LIMIT`，不触发停滞建议；完整模式
固定点未解完才是 `STALLED`，自由模型建议只能标记为 `UNVERIFIED_ADVISORY`，不能修改盘面。

扫雷采用与数独不同的产品边界：它是本地互动游戏，不经过 DeepSeek normalization，也不自动求解。服务端
保存权威雷位，首次 reveal 后才布雷；浏览器只取得 covered/flagged/revealed 状态，终局才显示雷。引擎支持
零区 flood、flag、chord、胜负和计时；进程内 `MinesweeperStore` 最多保留 64 局，game ID 可在刷新后恢复，
但服务重启即失效。逻辑提示只从公开数字做确定性八邻域传播，忽略玩家旗子的真实性，不读取隐藏雷位，且
只返回建议、不改变棋盘。对应写 API 继续复用本地 capability、Host、Origin 与 JSON 安全门。

数织继续使用统一的强制 normalization journey。canonical 由 `row_clues`、`column_clues` 与可选的三态
`grid` 组成；引擎为每条行/列生成局部合法模式，按已知格过滤并取模式交集，只把所有兼容模式共同拥有的
黑格/空格写入盘面。扫描顺序固定为行后列，每次有变化后从行重新开始，整轮无变化即 `STALLED`，没有
整盘 DFS、回溯或猜格路径。每个 line step 保存线索、兼容模式数、共同结论、实际变更和前后 fingerprint；
replay 从 canonical 重新生成同一步。停滞后的模型输出只保留 `UNVERIFIED_ADVISORY` 分析与技巧名，任何
cell assignment 都会被裁掉。

未知规则型纸笔题采用两段式可信边界。`NORMALIZE_INPUT` 只转写为 `RulePuzzleSource`，不设计解法；用户确认后，
`METHOD_SYNTHESIS` 才从同一 source 生成受限 `DeductionProgram`。程序只能引用白名单约束
`all_different / less_than / sum_equals / visibility` 和已注册传播策略，所有字段、引用、来源 coverage 与资源
预算均严格校验。任何未知字段（包括代码文本）都不会获得执行语义。

共享 rule-based engine 不按 Futoshiki、Kakuro 或 Skyscrapers 分支，而按约束类型做固定点传播。和值与可见数
只在一条显式约束内部枚举支持 tuple/permutation，最多 100,000 个，不跨约束回溯。每步保存 constraint、
rule/clue provenance、domain before/after、中文观察和 fingerprint；`replay_trace` 从 source 重算。全部实体单值且
所有约束复核通过才是 `SOLVED`，单步模式为 `STEP_LIMIT`，固定点未解为 `STALLED`。方法合成 provider 缺失时
Web 明确返回 503，不静默降级为通用 Agent。

`examples/paper-puzzle-demos/` 是运营演示与回归夹具的共同入口。五个原创 case 都包含 PNG、规则、source、
program、expected result 与 walkthrough；生成脚本只负责可重建 PNG。离线测试证明资产可解码、程序可执行和
trace 可重放，不把 scripted fixture 误报成真实 DeepSeek 图片识别证据。

## 3. Simple 数据流

```text
PuzzleInput
  → cipher keyword reference index + CipherWorkbench
  → build_messages
  → OfflineProvider / DeepSeekProvider（一次）
  → SolveResult
```

simple mode 仍遵守：输入无效零调用；有效输入一次调用；API/JSON/schema 错误不自动重试。关键词索引只把
匹配资料的名称、规则和注意事项放进 prompt，不注入完整表格，也不把命中本身当成密码成立的证据。除密码
索引外，运行时还可按题面信号注入中文语音、汉字结构、规范语料、模板归纳和状态交互的无答案方法卡；方法卡
只提供必要输入、歧义和验证方式。

## 4. Complex StateGraph

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

Web 的通用 Agent 运行支持玩家协作终止。页面先调用受 capability/Host/Origin/JSON 门保护的 stop API，再用
`AbortController` 立即结束浏览器等待；`SessionManager` 把停止请求原子写入 session 的 `stop.json`，并由
provider wrapper 在当前调用前后检查。若请求发生在一次非流式 DeepSeek 调用中，不能安全强杀该线程或撤回
远端请求，但返回后会立刻停止，不进入下一节点，最终状态为 `CANCELLED`。SQLite 保留最后一个完整节点，
事件流分别记录 `session_stop_requested` 与 `session_cancelled`。

### 强制阶段纪律

- 观察轮只能写事实、异常和有触发词的风味联想，不提交答案。
- 子问题物化轮先把列表、网格、阶段题和 meta 拆成可单独检查的工作单元；大题保留总数、分组和依赖，并选择代表性单元，不把 100+ 条线索压成一段摘要。
- 子问题验证轮把每个非空局部答案精确分入 supported、contradicted 或 needs-test；只有值不漂移、引用真实 signal 且给出 prediction/falsifier 的 supported 结果才能进入 evidence，无支持结果的子题必须显式 unresolved。
- 首轮局部语义覆盖不足一半时，框架可在计划前做一次恢复轮：已验证结果视为不可变锚点，未解单元重新物化；完全没有锚点时只生成 1–3 个题面可落地的高杠杆候选。恢复后禁止再进入工具重规划，保证总预算仍有界。
- 计划轮至少保留两个 competing hypotheses，并选择可判别实验。
- 观察轮保存题面明确给出的答案长度等 `answer_constraints`；计划轮最多保存四个带映射依据、不变量、预测和
  证伪条件的 `representation_hypotheses`。表示只能在通用展开工具证明全组约束后升级为 evidence。
- 每个工具计划必须引用可见 signal，给出具体 prediction 与 falsifier；空计划保持为空，不再暗中回退到通用密码 shotgun。
- 工具轮只运行白名单确定性工具，结果带 provenance 写入 evidence。
- 评价轮必须消费工具或人工产生的新 evidence。
- 中间验证轮只接受已存在且引用真实 evidence ID 的 carrier/instruction/ordering/parameter；原始中间猜测不能直接通过。
- 验证轮检查格式、证据、风味/标题回扣；不足时返回 null/`NEEDS_REVIEW`。
- 显式答案长度由运行时复核；尚无通过机器不变量的表示，或两个未否决的显式码表变体产生不同输出时，
  即使模型给出全真 checks 也只能 `NEEDS_REVIEW`。
- 验证响应中的未知局部 result ID 被忽略且不产生 evidence；终局漏填的 required check 由机器补为 `false`。两者都会留下问题标记并安全停在 `NEEDS_REVIEW`，不会因保守总化而提升答案。
- 预算耗尽返回 `EXHAUSTED`，不继续调用或编造结果。
- DeepSeek 的显式网络传输失败可从同一 checkpoint 重试同一节点一次。非法 JSON/非对象输出不重试、不猜补，记录长度与摘要指纹后安全终止为 `NEEDS_REVIEW`；未知子题引用和无 signal/缺契约的计划项被保守丢弃并写入 blocker。其他尚未总化的 schema 错误仍显式失败，避免把错误输出静默吞掉。

## 5. PuzzleState

框架中立 state 是 JSON 兼容映射，主要分区为：

- immutable `puzzle`、`artifacts`、`required_artifacts`，以及从题面关键词确定性生成的 `cipher_reference_hints` / `reasoning_reference_hints`
- `input_assessment` 保存输入完整性、媒介、缺失 artifact、来源模式与转写风险
- `observations`、`answer_constraints`、`flavor_associations`、`structure_model`、`subproblems`、`subproblem_results`、`validated_subproblem_results` 与 `subproblem_validation`
- `clue_roles` 区分 theme/parameter/ordering/decoder/extractor/instruction；`research_ledger` 明确查询用途且 lookup 永不单独证明答案
- `hypotheses`、`representation_hypotheses`、`representation_assessment`、`plan`、`attempts`、`evidence`
- `intermediate_answers`、`validated_intermediate_answers`、`intermediate_validation`、`extractions`、`answer_candidates`
- `source_conflicts`、`verification_scope`、`open_questions`、`missing_artifacts`、`blockers`、`blocker_details`
- `budget`、`semantic_refinement_used`、`stage`、`status`、`last_node`、`next_node`
- `final_answer`

系统不保存私有思维链；只保存可协作的结论、证据、实验、失败记录和简洁推理摘要。

## 6. 持久化与恢复

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

## 7. 工具层

`CipherWorkbench` 负责高召回密码候选，并包含现代 26 字母 Bacon 与十进制 ASCII 的确定性识别；
`cipher_reference.py` 是 Web 古典密码资料与转换的单一服务端入口，提供培根、猪圈、凯撒、栅栏、ASCII
资料搜索以及 Caesar 全移位、Bacon、A1Z26、ASCII、盲文点位和 2/3/10 进制有界转换。资料页面使用
10/5 列响应式紧凑格；猪圈同时提供 GPT 生成的黑白结构图和确定性位置/点位数据，盲文以六点图覆盖
A–Z/0–9，旗语以接收者视角的双臂八方向数据绘制 A–Z。生成图不参与解码逻辑，猪圈也不会从不稳定
Unicode 图形猜字母。`ToolRegistry` 负责模型可计划调用的确定性工具：

同一模块也负责 Agent 路由：题面明确出现凯撒/ROT、培根、猪圈、栅栏、ASCII、盲文、旗语或 A1Z26
关键词时，simple prompt 与 complex state 自动获得不含大表的紧凑 hint；复杂 Agent 需要映射时再调用
`cipher_reference_lookup(query)` 取得至多四项完整资料。无关文本得到空 hint，空/超长/无匹配查询失败关闭。

| 工具 | 契约 |
|---|---|
| `cipher_workbench` | 有限候选、字符预算、已知 key 才运行 Vigenère |
| `cipher_reference_lookup` | 明确密码关键词查询；返回同一资料库中的规则、注意事项和有界对照表 |
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
| `expand_symbol_groups` | 显式 token 映射、允许字符集和固定宽度验证；输出逐 token 展开与输入指纹，不枚举映射 |
| `decode_bacon_groups` | 显式 `modern26` / `classic24` 变体；24 字母版保留 I/J、U/V 歧义，不自动选优 |
| `audit_signal_coverage` | 对显式 signal/claim 关系返回已消费、未消费、多重归属与未知引用 |
| `compare_explicit_variants` | 并列比较调用者给出的版本及约束结果，不按语言可读性自动选优 |
| `validate_template_holdout` | 将训练记录与留出记录分账，验证显式周期/字段规则是否外推 |
| `extract_by_pronunciation_positions` | 只按调用者给出的规范读音和位置机械提取；缺来源或越界失败 |
| `state_snapshot_diff` | 比较互动题前后状态，返回新增、移除、变化与不变字段 |
| `reasoning_reference_lookup` | 按显式信号读取无答案方法卡；查询记录进 research ledger 且 `proves_answer=false` |

每次调用用 tool+arguments fingerprint 去重，replan 中相同调用记录为 `duplicate_skipped` 而不再次执行。未知工具或参数错误形成 failed attempt，不进入成功 evidence。

规划 prompt 的工具签名由 `inspect.signature()` 对 ToolRegistry 当前 callable 生成，例如 `a1z26_decode(values)`、`grid_trace(grid, start, directions)`。ToolSpec 在同一注册点补充紧凑前置条件，例如 0-based 坐标、`N|E|S|W`、等长字符串和 constraint object shape。只列工具名已被 cycle 2 证伪；只有签名又在 cycle 3 暴露类型/前置条件错误，因此两者都属于执行契约。

阶段 memory 不是对话历史，而是结构化状态：`observations` 与 `flavor_associations` 保存题面事实和可检验联想，`attempts/evidence/extractions` 保存机械实验账本，`intermediate_answers` 保存候选载体，`validated_intermediate_answers` 只保存通过独立证据门的中间结果，`open_questions` 与 `unused_elements` 保存尚未闭合的推理债务。没有验证过的中间结果、或后两项非空时，机器终局门都不能接受 `SOLVED`。

Web 不请求模型另写“思维过程”，而是将上述 state 投影为五段可审计 trace：看到、联想、资料路由、表示/
工具验证以及接受或停下原因。其中同时展示输入充分性、线索角色、查询用途、留出验证、版本冲突与 typed
blocker；旧 session 缺少新字段时按空集合显示。

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
| `cipher_reference.py` | 古典密码参考库、搜索和 Web 有界转换 |
| `reasoning_reference.py` | 中文文字、规范语料、模板与状态题的无答案信号路由卡 |
| `paper_puzzle/components/rule_based/` | 受限规则程序合同、方法合成适配器、确定性传播与 replay |
| `scripts/generate_paper_demo_images.py` | 生成原创纸笔演示题 PNG；JSON 与讲解仍是版本化 source |
| `.agents/skills/puzzle-reasoning-sop/` | 跨 Agent surface 的证据优先 SOP；只引用 canonical runtime |
| `web/app.py` | 本地安全门、DeepSeek 配置状态、题目/纸笔/密码页面与 API |
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

模型输出契约与运行时状态契约并不等价。17:00 批次中，模型漏掉某个 verdict、把同一候选放进多个 verdict，或给出漂移后的 accepted value 时，旧实现会抛异常并截断整条图。现在运行时对“已知候选的不完整/矛盾判断”做保守总化：遗漏、冲突和漂移值统一降级为 `needs_test`，空结果 verdict 被忽略，`unresolved_subproblem_ids` 由 accepted 结果重新计算；引用完全未知 result ID 的判断也只记录并忽略。20:00 批次进一步证明恢复轮可能产生引用不存在子题的 candidate result，计划轮也可能漏掉 signal；两者现在分别丢弃并留下不可通过终局的 blocker。这个容错只保证流程继续，不会把不可靠结果提升为 evidence。

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

- complex graph 当前仍以文本/artifact 为主；本地 Web 的 NORMALIZE_INPUT 已支持单张 PNG/JPEG/WebP 视觉输入。
- 当前确定性 grid/CSP 与 rule-based 白名单是基础组件，不等于任意纸笔题、完整填字或通用图像理解引擎。
- 49 道 CCBC16 非 Meta 已完成表面分类：第一阶段冻结 10 道直接文本、14 道 source-hashed 人工转写，共 24 道可运行官方文本题；23 道无法仅用文本忠实表达。十页栅格 PDF #30 与三段音频 #36 理论上可在额外人工转写后加入，但用户已明确不作为第一阶段准入要求，当前不再列为未完成项。转写 final feeders 时仍必须带入人类在解锁该题时已经拥有的上游 Meta 答案、网格或操作符，不能只抄当前图片。
- knowledge research subgraph 尚未接外部搜索 provider；没有可靠事实时保持 unknown。
- offline provider 只验证系统流，不代表真实复杂解题能力。
- 真实 DeepSeek benchmark 明确 opt-in，默认测试绝不计费。

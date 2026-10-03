---
id: P0015
title: CCBC 研究精髓全面产品化
status: completed
created_at: 2026-10-04
paired_task: T0014
acceptance_contract: v1
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - ../docs/02-agent-design-journey.md
  - ../../research/ccbc16/methodology.md
  - ../../research/human-association-reasoning.md
  - P0014-robust-reasoning-and-sudoku-keyboard.md
evidence:
  - "haiknow task preflight --root $PWD --intent new-task → use-current；HEAD d59da7e，origin/main 0 behind / 8 ahead，worktree clean"
  - "research/CCBC12_CCBC16_文字题研究总报告.html → 151 个研究单元：96 收录、31 条件收录、24 边界/排除、74 具完整文字数据或等价模型"
  - "research/CCBC16_官方内部关卡逐关简报.html → 423 个固定内部关卡，覆盖大量中文语音、字形、映射、排序和提取操作"
  - "research/CCBC16_复习资料130题核对表.html → 5 类重复生成模板各 26 例，并保留来源版本冲突"
  - "src/puzzle_agent/complex_domain.py 已有 observations/hypotheses/evidence/unused_elements，但没有输入充分性、线索角色、搜索、来源冲突和核验范围账本"
  - "src/puzzle_agent/tool_registry.py 已有密码、网格、排序等有界工具；缺表示展开、模板 holdout、语音索引与通用覆盖审计"
deps:
  blocked_by:
    - P0014
---

# P0015 · CCBC 研究精髓全面产品化

> 用户要求完整吸收五份 CCBC12/CCBC16 研究资料的可迁移方法，并逐步实现。用户于 2026-10-04 明确说“全部提交！开工！”，授权跳过额外 plan review，在本地完成实现、测试和 commit；不包含 push、公网部署或付费模型调用。
>
> <!-- 一旦执行此 plan 即冻结；偏差只写到 T0014 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景与问题

项目已经有 TRACE-LIFT、HA-BRIDGE、复杂 Agent 状态图、密码参考库和一批确定性工具，但研究材料显示仍有五类能力没有完整进入产品运行契约：

1. 输入是否足以求解以及转写是否泄漏识别结果，没有形成统一机器账本。
2. 标题、风味、异常、搜索词和中间结果的“角色”没有显式表示，模型容易把提示当证据、把指令当答案。
3. 表示映射、固定宽度、码表变体和全局不变量缺少通用可重放工具；由 P0014 先补齐。
4. 重复生成题的“归纳规则 → 留出验证 → 外推”没有一等状态和工具支持。
5. 官方解析重构、实际复算、来源冲突和盲解证据没有严格分级，容易制造虚假的“Agent 会自主解题”结论。

研究 HTML 是方法证据和测试设计来源，不直接作为线上 Agent 的答案记忆。生产 prompt、技能和工具中不得嵌入具体题目答案。

## 2. 目标与非目标

### 2.1 目标

- 建立一个可执行、可审计、与题型无关的普通谜题 SOP。
- 让运行时持久化输入充分性、线索角色、搜索记录、来源/版本冲突、验证范围和具体 blocker。
- 增加可迁移的确定性工具：表示展开、覆盖审计、模板 holdout、语音位置提取及版本比较。
- 建立中文文字游戏的保守处理契约：模型提出读音/拆字候选，脚本只验证显式数据，不伪装成权威字典。
- 支持状态题和多层题的依赖、状态差与中间产物分类。
- 在 Web 中向玩家展示短而可复验的“看到 → 联想 → 搜索/查表 → 最小实验 → 全局验证 → 结论/阻塞”。
- 建立无答案泄漏的课程和回归集，分别评价发现、机制执行、提取和终局验证。
- 将通用方法做成项目本地 Skill，供其他 Agent surface 调用，并让 DeepSeek 运行时复用同一语义。

### 2.2 非目标

- 不把 151/423/130 条官方答案放入在线 prompt、向量库或关键词到答案映射。
- 不一次性实现所有纸笔谜题 solver、任意中文拆字器或无限词典搜索。
- 不声称 scripted/offline 测试证明真实 DeepSeek 已获得自主发现能力。
- 不自动联网搜索；搜索账本先支持内置资料查询和显式外部结果输入。
- 不修改已冻结的 P0014 正文；实施新发现只进入各自 task。

## 3. 总体方案

选择“共享运行时契约 + 小型确定性工具 + 项目 Skill + 盲测”的组合，而不是巨型 prompt。

```text
题面/图片
  → 输入充分性与保真检查
  → tension/线索角色账本
  → 2–4 个竞争桥接假设
  → 内置资料检索记录
  → 最小可证伪实验
  → 全量展开/约束求解
  → 中间产物分类
  → 排序与提取
  → 覆盖、版本、来源和终局验证
```

模型负责提出少量语义候选；脚本只执行显式、有限、可重放的操作。任何 lookup、模型判断或语言可读性都不能单独把候选升级为答案。

## 4. 分阶段实施

### 阶段 0 · 完成 P0014 基础

- 数独确认表格方向键导航。
- `answer_constraints` 和 `representation_hypotheses`。
- 通用 token 展开、Bacon 24/26 变体、机器终局门。
- 普通谜题可视化证据轨迹和六类泛化回归。

### 阶段 1 · SOP 与运行时状态

扩展 PuzzleState：

- `input_assessment`：媒介、完整性、缺失 artifact、是否为摘要/等价模型、转写风险。
- `clue_roles`：theme/parameter/ordering/decoder/extractor/instruction。
- `research_ledger`：查询、命中资料、来源、用途和“仅提示/可作证据”级别。
- `source_conflicts`：来源、版本、差异和未决裁决。
- `verification_scope`：blind-solved/recomputed/checked-against-source/reconstructed/unknown。
- `blocker_kind`：missing_input/missing_knowledge/missing_rule/calculation_error/ambiguity/version_conflict/budget_exhausted。
- `intermediate_type`：answer/instruction/parameter/ordering_key/transformed_artifact。

旧 session 缺字段时保守补默认值，不迁移或重写历史 checkpoint。

### 阶段 2 · 通用确定性工具

在 ToolRegistry 增加：

1. `audit_signal_coverage(signals, claims)`：返回已消费、未消费、多重归属和未知引用。
2. `compare_explicit_variants(variants)`：对调用者提供的候选逐项比较约束结果，不按可读性替 Agent 选优。
3. `validate_template_holdout(records, hypothesis, holdout_ids)`：验证显式周期/分类/字段规则，训练样本与留出样本分账。
4. `extract_by_pronunciation_positions(items)`：对调用者明确给出的规范读音和位置做机械提取；不猜多音字。
5. `state_snapshot_diff(before, after)`：返回新增、移除、变化和不变字段，支持互动题。
6. P0014 的 `expand_symbol_groups` 和 Bacon 变体作为同一工具层基础。

所有工具有大小上限、明确失败状态、输入/输出 provenance，并提供正例、边界、歧义和恶意超限测试。

### 阶段 3 · 中文文字游戏与资料路由

- 新增中文语言机制参考：拼音/声调、声韵母、谐音、部件/偏旁、字形、成语/规范语料。
- 资料只说明观察信号、必要输入、常见歧义和验证方法，不内置研究题答案。
- 多音字、异读字、字形拆分必须保留候选与来源；没有权威输入时返回 `NEEDS_REVIEW`。
- 扩展关键词路由，但关键词仍只负责找到资料，不直接调用固定答案流程。

### 阶段 4 · Agent 编排与证据门

- `artifact_inventory` 生成输入充分性结论。
- `observe_classify` 登记 tension、显式约束和候选角色。
- `associate_theme` 为候选 ontology 指定角色和 holdout 预测。
- `hypothesize_plan` 将搜索、表示、模板和状态实验关联到具体 hypothesis。
- `evaluate_evidence` 保留失败路线、来源冲突和中间产物类型。
- `verify_answer` 增加输入充分性、覆盖率、版本歧义、核验范围和来源独立性机器门。
- blocker 精确到类别；缺输入时停止，不用模型猜图或动态状态。

### 阶段 5 · Skill 与 Web

- 新建项目 Skill `puzzle-reasoning-sop`，引用项目 canonical 工具，不复制算法。
- Skill 教会 Agent 使用 SOP、失败语义和停止条件；不包含具体答案。
- Web 过程视图增加输入充分性、线索角色、搜索/资料、最小实验、版本冲突、未消费项和核验等级。
- 旧 session 和 simple solver 结果仍可显示，不因新字段缺失崩溃。

### 阶段 6 · 课程、盲测与文档

- 从研究机制抽象原创 fixture，不复制答案和独特题面表达。
- 按机制家族划分 train/dev/test，避免同一生成器实例随机泄漏。
- 加入关键词假阳性、缺 artifact、版本冲突、多解不变量、中间指令、未消费元素和 title/flavor ablation。
- rubric 分开计 discovery、mechanism、extraction、verification；仅猜中答案标记 `lucky-answer`。
- 更新架构、设计学习日志、README 和 task 实证。

## 5. Contract impact map

| 维度 | 影响 |
|---|---|
| canonical SSOT | `complex_domain.py` 持久状态；`complex_graph.py` 阶段契约；`tool_registry.py` 工具语义；新的 reasoning playbook 保存 SOP 数据 |
| active consumers | complex CLI/session/Web、offline provider、cycle runner、benchmark evaluator、项目 Skill |
| templates/generators | scripted/offline provider 和 benchmark fixture schema 需要同步；历史输出不回写 |
| mechanical checks | domain/graph/tool/session/Web/benchmark tests、Skill 脚本测试、JS syntax、全量 unittest、diff check |
| historical snapshots | 已完成 P/T/D、旧 benchmark 结果、研究 HTML 与旧 checkpoint 只读保留 |
| search terms | `artifact_inventory|observations|association_candidates|hypotheses|attempts|evidence|intermediate_answers|unused_elements|blockers|verification_checks|cipher_reference_hints` |

## 6. 风险与恢复

- **答案泄漏**：研究 HTML 只进入 provenance 和人工分析；测试 fixture 必须通过现有 leak validator或新增等价检查。
- **prompt 膨胀**：SOP 使用紧凑字段与按需资料检索，不把完整机制库每轮注入。
- **伪字典权威**：中文工具只处理显式读音/部件，开放语言判断由模型提出并标来源。
- **过度门禁**：原子题不因没有复杂中间层而失败；机器门只检查适用字段。
- **兼容性**：新字段使用保守默认值；旧 checkpoint 可恢复，旧 Web 结果可渲染。
- **过拟合**：生产代码不出现研究题答案或特定 token 映射；正例必须配近似反例和跨载体例。
- **范围失控**：每阶段独立 RED/GREEN/commit；发现新题型只记 backlog，不顺手新增完整 solver。
- **真实模型证据**：没有另行授权的付费盲测时，model discovery 结论保持 unknown。

## 7. 验证方式

- 每项行为执行 RED → Verify RED → GREEN → Verify GREEN → REFACTOR。
- 聚焦运行 domain、tool registry、complex graph、session、benchmark、Web 和 Skill 测试。
- 每阶段运行相关回归；最终运行全量 unittest、前端语法检查和 `git diff --check`。
- 对终局门做 mutation probe：移除未消费项/版本冲突/输入不足任一检查时，至少一个测试应失败。
- 浏览器可用时执行数独键盘和普通谜题 trace smoke；否则标记未做，不以源码 grep 冒充交互证据。

## 8. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | P0014 基础 | P0014 A01–A08 全部通过或在 T0013 中有明确失败证据；P0015 不复制其实现 |
| A02 | yes | Runtime state | 新状态可持久化输入充分性、线索角色、搜索、来源冲突、核验范围、blocker 类别和中间产物类型；旧 checkpoint 可读 |
| A03 | yes | Tools | 覆盖审计、显式变体比较、模板 holdout、显式读音位置提取和状态 diff 均可调用、有限、可重放 |
| A04 | yes | Chinese routing | 中文语音/字形/成语机制可被检索，歧义或缺来源时不伪装成确定答案 |
| A05 | yes | Agent graph | 各阶段消费并更新新账本；输入不足、未消费显著线索或未决版本冲突时不能高置信 `SOLVED` |
| A06 | yes | Skill | 项目存在可发现的 `puzzle-reasoning-sop` Skill，调用 canonical 实现并明确禁止答案记忆和无界搜索 |
| A07 | yes | Web | 玩家可查看完整的短证据链、失败候选、未决冲突和具体停止原因，旧结果兼容 |
| A08 | yes | Evaluation | 至少覆盖七类鲁棒性样例，按阶段评分并能识别 lucky answer 与答案泄漏 |
| A09 | yes | Documentation | 架构、学习日志、README 与实现一致；研究报告的证据等级和使用边界写清 |
| A10 | yes | Regression | 聚焦测试、全量测试、JS syntax 和 diff check 全绿；任何未执行的真实浏览器/模型检查明确列出 |

## 9. 成稿自审记录

- 日期/审核者：2026-10-04，Codex 主执行者自审。
- 实际上下文：宿主规则不允许在用户未明确要求时启动 subagent，因此采用从落盘文件完整重读的降级自审；没有把同上下文审核称为独立审核。
- 被审版本：本文件除本节自身外的完整正文。
- 意图与范围：覆盖“完全吸纳研究精髓”，并明确方法产品化而非答案记忆；P0014 与 P0015 边界和依赖清楚。
- 事实与假设：研究规模来自已提交 HTML；运行时字段和工具缺口来自当前源码；中文开放知识不假定存在完整本地字典。
- 方案与步骤：SOP、状态、工具、中文路由、图编排、Skill、Web、评测和文档形成闭环；每阶段可独立验证和提交。
- 影响范围：canonical state、图、工具、consumer、provider、benchmark、Skill、Web 和历史边界均纳入 impact map。
- 风险与恢复：答案泄漏、prompt 膨胀、伪权威、过度门禁、兼容、过拟合和付费证据边界均有 fail-closed 处理。
- 验证与验收：A01–A10 都是调用者可观察结果；真实模型和浏览器证据不由 mock/source-shape 冒充。
- 授权与冻结：用户明确授权全部提交并开工，采用 skip-review；授权不包含 push、公网部署或付费调用。
- 完整 findings：未发现阻止安全实施的未决产品选择。唯一环境风险是此前 session-loop runtime 自检文件缺失；它影响无人值守编排，不改变逐阶段本地实现，可在恢复前由当前会话顺序执行并在 task 记录偏差。
- 结论：自审通过，可以建立 T0014 并开始实施；执行后 plan 冻结。

---
id: P0016
title: 从题目规则归纳可执行纸笔推理方法
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_task: T0015
acceptance_contract: v1
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - ../docs/02-agent-design-journey.md
  - P0015-ccbc-reasoning-operationalization.md
evidence:
  - "用户要求题目与规则共同输入时，Agent 先自研解法，再以类似数独的脚本工作流求解，并建立可交给运营同事的 Git 演示题目录；2026-10-04 明确允许继续当前分支并全部提交"
  - "PaperPuzzleGateway 当前只分发 sudoku/nonogram，kakuro 仍为 disabled roadmap；normalizer kind 只允许 sudoku/nonogram/general"
  - "Sudoku 与 Nonogram 已证明固定点传播、逐步解释、fingerprint 与 replay verifier 是项目可复用模式"
  - "git fetch origin 后手工验证 origin/main 是 aa28d5a 的祖先且 origin/main...HEAD=0/14；自动 preflight 仍误报 fresh-remote-unknown，用户随后明确授权继续当前 feat/cipher-tools-and-pages 分支"
---

# P0016 · 从题目规则归纳可执行纸笔推理方法

> 用户已授权在当前分支直接实施并提交，采用 skip-review。付费 DeepSeek 调用、push、merge 和公网部署不在授权内。
>
> <!-- 一旦执行此 plan 即冻结；偏差只写到 T0015 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景、目标与边界

当前纸笔组件按题型硬编码：先知道是 Sudoku 或 Nonogram，再调用对应 solver。新需求是处理“规则和题面一起给出”的未知或未注册纸笔题：Agent 应先把自然语言规则与可见线索归纳为一套方法，再由脚本重复执行机械推理，保留人类可读步骤。

本阶段目标：

1. 新增 `rule_puzzle` 入口，输入规则、实体/格子和可见线索。
2. 新增独立 METHOD_SYNTHESIS 调用，让 Agent 从输入归纳受限的 `DeductionProgram`。
3. 程序只能组合白名单约束和传播器，不允许生成或执行 Python/JavaScript、shell、表达式求值或插件代码。
4. 脚本固定点运行，每一步记录采用的规则、观察、删除的候选、形成的赋值及前后 fingerprint；支持完整求解和只提示一步。
5. 增加 replay verifier、终局约束核验、规则/线索覆盖门和资源预算；停滞时明确返回而不搜索整盘解。
6. 建立 Git 演示目录，包含原创题面图片、规则文本、期望规范化、推理程序、结果和讲解。

非目标：

- 不让模型生成任意可执行代码。
- 不声称一组有限原语能覆盖所有纸笔谜题；不支持的规则返回 typed blocker。
- 不做整盘 DFS、回溯、SAT/SMT 求解或从答案倒推程序。
- 不用 scripted provider 冒充真实图片识别或模型自主归纳证据。
- 不复制网络题面或答案；所有演示题原创生成。

## 2. 方案与数据流

采用“结构化转写 → 方法归纳 → 机器验证 → 确定性传播”的分层方案：

```text
文字/图片 + 自然语言规则
  → DeepSeek NORMALIZE_INPUT
  → RulePuzzleSource（规则、符号、实体、可见线索、显示坐标）
  → 用户可视化确认
  → DeepSeek METHOD_SYNTHESIS
  → DeductionProgram（白名单约束、来源绑定、传播顺序）
  → schema / provenance / coverage / budget validator
  → deterministic fixed-point engine
  → replay + final constraint verifier
  → SOLVED | STEP_LIMIT | STALLED | NEEDS_REVIEW
```

选择受限程序而非任意代码的理由：Agent 可以针对新规则组合方法，但执行语义仍由项目代码拥有；同一输入和程序可重放，错误程序不会取得本地代码执行能力。

### 2.1 RulePuzzleSource

- `rules`: 带稳定 ID 的原始规则句。
- `symbols`: 有界整数符号集。
- `entities`: 稳定 ID、显示标签、可选行列坐标和已知值。
- `clues`: 稳定 ID、原始可见文本/符号、涉及 entity IDs。
- `display`: 可选 grid 尺寸，只用于确认与展示。
- 限制实体、规则、线索和文本总量；所有引用必须存在。

Normalizer 只做保真转写，不决定求解策略。用户确认页显示规则文本、格子/实体和线索表；不会只显示一坨 JSON。

### 2.2 DeductionProgram

首版白名单约束：

- `all_different`
- `less_than`
- `sum_equals`
- `visibility`

每条约束必须含 `source_rule_ids`，线索派生约束还必须含 `source_clue_ids`。程序另含 `method_summary`、`strategy_order` 和 coverage ledger。策略只可选择注册传播器：已知值传播、all-different 排除/唯一位置、不等式支持剪枝、和约束局部支持剪枝、可见楼层局部排列交集。

局部 tuple/permutation 只用于一个显式约束的候选支持检查，设置严格上限；它不是整盘解枚举，也不允许跨约束回溯。

### 2.3 执行与可信边界

- METHOD_SYNTHESIS lookup 本身不是解题证据；只有通过 validator 的程序可执行。
- 程序必须覆盖全部 operational rules/clues；未覆盖、未知 constraint/strategy、悬空引用或超预算均 `NEEDS_REVIEW`。
- 每个传播步骤只缩小 domain，不直接接受模型给出的答案。
- 候选域为空立即 contradiction；单值域形成可审计赋值。
- `SOLVED` 要求所有变量单值、全部约束复核通过、coverage 完整且 replay 一致。
- 固定点仍有多值域返回 `STALLED`；只提示一步在第一个 domain 变化后返回 `STEP_LIMIT`。

## 3. 实施拆分、影响面与演示资产

### 阶段 1 · 合同与 TDD 骨架

- 新建 `paper_puzzle/components/rule_based/`，定义 source/program/state/error schema。
- 先写 validator、未知原语、悬空引用、规则覆盖、预算与无任意代码字段的 RED tests。
- 新建 METHOD_SYNTHESIS provider adapter；用 scripted provider 测 prompt 输入隔离和非法 JSON fail-closed。

### 阶段 2 · 通用传播引擎

- 实现四类约束传播器、固定顺序调度、步骤解释、fingerprint、next-step/full、replay 和终局验证。
- constraint-local 候选最多 100,000；变量/符号/约束均有上限。
- 验收至少覆盖 Futoshiki、Kakuro、Skyscrapers 三种未实现经典题型；三者使用同一 engine，不新增三个 solver。

### 阶段 3 · Intake、Gateway 与 Web

- Normalizer 新增 `rule_puzzle` kind 与严格 source validation。
- Web 增加“按规则推理”选择项、规则/网格/线索可视化确认、方法摘要与步骤展示。
- Gateway 分发 rule-based engine；方法归纳使用 agent provider，缺 provider 明确 503/typed blocker。
- rule puzzle 同时支持 `full` 与 `next_step`。

### 阶段 4 · 演示题目录

新建 `examples/paper-puzzle-demos/`，目录规范：

```text
README.md
manifest.json
<case-id>/
  puzzle.png
  rules.txt
  source.json
  program.json
  expected-result.json
  walkthrough.md
```

首批至少五题：Sudoku 图片、Nonogram 图片、Futoshiki、Kakuro、Skyscrapers。图片由仓库脚本从原创 fixture 确定性生成，提交最终 PNG；规则题同时保存 source/program/result，使运营同事既能上传图片演示，也能离线复现脚本能力。manifest 标注每题展示的能力和是否需要 DeepSeek。

### 阶段 5 · 文档与收尾

- 更新 README、架构、设计学习日志、纸笔子页文案和主题索引。
- 记录真实图片/模型验证未执行项，不把 fixture 或 fake provider 当作在线识别成功。
- 全量回归、JS syntax、图片完整性、demo replay、diff check 和 HAiKnow contract。

### Contract impact map

| 维度 | 影响 |
|---|---|
| canonical SSOT | rule-based contracts/engine 拥有程序语义；normalizer 只拥有转写 envelope；gateway 只分发 |
| active consumers | intake normalizer、Web API/session、gateway、静态前端、paper catalog、README/docs |
| templates/generators | demo image generator 与 manifest schema；生成 PNG 是 derived asset，fixture JSON 是 source |
| mechanical checks | rule contracts/engine/synthesis/gateway/intake/Web/demo tests、full unittest、JS check、PNG decode、replay、diff check |
| historical snapshots | 已完成 Sudoku/Nonogram P/T、旧 session、旧 demo 文件保持只读兼容 |
| search terms | `sudoku|nonogram|general|preferred_kind|solve_mode|PaperPuzzleGateway|renderCanonicalEditor|renderResult|paper-puzzles` |

## 4. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | Source/program contracts | 规则题 source 与 program 均有严格有界 schema；未知字段语义、任意代码、悬空引用和覆盖缺口失败关闭 |
| A02 | yes | Method synthesis | 独立 METHOD_SYNTHESIS 调用从确认 source 产出程序；非法 JSON/原语/来源绑定不执行，且不把模型答案写入状态 |
| A03 | yes | Engine | 一个共享引擎支持 all-different、less-than、sum、visibility 的确定性传播，无整盘搜索/回溯 |
| A04 | yes | Trace/replay | 每步包含规则与线索来源、domain 变化、中文观察和前后 fingerprint；next-step/full 可重放并通过终局约束复核 |
| A05 | yes | Generalization | Futoshiki、Kakuro、Skyscrapers 三类原创 fixture 通过同一 program engine 求解或给出诚实 STALLED，无题型专用 solver |
| A06 | yes | Intake/Web | `rule_puzzle` 可经文字/图片 normalization、可视化确认、方法归纳和结果展示；缺 provider 或不支持规则明确失败 |
| A07 | yes | Demo assets | `examples/paper-puzzle-demos/` 至少五题，每题含所需图片/规则/source/program/result/walkthrough；manifest 能说明演示能力与运行方式 |
| A08 | yes | Evidence integrity | demo 图片可解码，program 可离线重放，expected result 独立 fixture；未运行真实 DeepSeek 时不声称图片识别已验证 |
| A09 | yes | Documentation | README、架构、学习日志、纸笔页面和 HAiKnow task 与实现一致，说明安全边界和支持原语 |
| A10 | yes | Regression | 聚焦 RED/GREEN、mutation probe、全量 unittest、所有 JS syntax、demo validator、HAiKnow contract 与 diff check 全绿 |

## 5. 风险、恢复与授权

- **规则误译**：约束必须绑定原规则/线索且在 Web 展示；coverage 缺口停止。脚本 soundness 不等于自然语言翻译正确，用户仍可在确认阶段纠正 source。
- **伪泛化**：三种新题型必须共享同一引擎；生产代码不得出现 fixture ID、答案或按题型分支。
- **隐式暴力搜索**：只允许 constraint-local 支持枚举并限制规模；不做跨约束猜测或回溯。
- **图片 OCR 夸大**：离线测试只证明 envelope/asset 路径；真实视觉能力需另行授权付费 smoke。
- **前端复杂度**：首版确认器只承诺规则、数字网格、实体与线索表，不尝试复刻任意图形编辑器。
- **恢复**：新 kind 与新组件为加法；失败时旧 sudoku/nonogram/general 路径不变，可单独禁用 rule_puzzle catalog entry。
- **授权**：用户允许当前分支实施和 commit；不包含 push、merge、发布、外部消息或付费调用。

## 6. 成稿自审记录

- 日期/审核者：2026-10-04，Codex 主执行者。
- 实际上下文：宿主未授权 subagent，按允许的降级路径从落盘文件完整重读；不声称独立 reviewer。
- 被审版本：除本节自身外的完整 P0016 正文。
- 意图与范围：覆盖“规则与题面一起输入 → 自研方法 → 脚本推理 → 运营演示资产”，没有扩大到任意纸笔万能求解或任意代码生成。
- 事实与假设：现有 gateway/normalizer/Web kind 枚举、Sudoku/Nonogram solver 模式均来自当前源码；真实 DeepSeek 对新图片的表现明确为 unknown。
- 方案与步骤：source、program、validator、engine、gateway/Web、demo、文档形成闭环；三种新题型共用同一约束引擎。
- 影响范围：canonical、consumers、生成器、测试、历史兼容和 repo-wide 搜索词均已列出。
- 风险与恢复：误译、伪泛化、隐式搜索、OCR 证据和前端范围均有 fail-closed 或可回退路径。
- 验证与验收：A01–A10 均为调用者可见结果；真实模型与浏览器证据不由 fake/provider shape 冒充。
- 授权与冻结：用户明确允许继续当前分支并全部提交，足以覆盖本地实施与 commit；不覆盖 push/merge/付费调用。执行开始后 plan 冻结。
- 完整 findings：受限 DSL 是安全与可审计性的必要选择；若允许任意生成代码会改变权限模型，因此明确列为非目标。没有剩余必须由用户决定的 blocker。
- 结论：成稿自审通过，可以建立 T0015 并开始实施。

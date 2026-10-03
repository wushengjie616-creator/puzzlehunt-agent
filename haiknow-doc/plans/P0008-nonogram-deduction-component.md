---
id: P0008
title: 数织确定性推理组件与本地 Web 做题过程
status: in_progress
created_at: 2026-10-03
paired_task: T0007
acceptance_contract: v1
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - P0006
evidence:
  - "2026-10-03 扫雷基线已提交为 db773c304112ba22b0dce0dedac6f00f34345858；git status clean"
  - "fresh git fetch 后 HEAD=db773c3、origin/main=3dbc389、git rev-list origin/main...HEAD 为 0 2；preflight 仍报 fresh-remote-unknown，按原始 Git 证据记录为工具识别限制"
  - "当前 normalizer 仅允许 sudoku/general，PaperPuzzleGateway 中 nonogram disabled，Web result 仅渲染 Sudoku"
  - "项目已有 unittest/FastAPI TestClient 测试入口；扫雷完成后全量为 158 tests GREEN"
---

# P0008 · 数织确定性推理组件与本地 Web 做题过程

<!-- 一旦执行此 plan 即冻结；偏差只写到 T0007 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景与意图

用户已经确认数织规则和设计方向，并授权本轮实现、提交和本地 merge。数织组件应把人类会重复进行的
“生成某行/列当前仍合法的区段放置，取共同黑格/空格，再传播到交叉方向”固化为小函数和确定性循环；当
这些基础约束到达固定点仍未完成时，明确返回 `STALLED`，让 Agent 提供不修改盘面的高层建议，不把整盘
搜索、回溯或猜测包装成人类推理。

## 2. 目标与非目标

### 目标

- DeepSeek `NORMALIZE_INPUT` 新增 `nonogram` 分类，canonical 使用 `row_clues`、`column_clues` 与可选
  `grid`；用户确认后才进入组件。
- 支持矩形数织；每格状态为 unknown / filled / empty，空题默认全 unknown。
- 将规格校验、线索校验、合法行模式生成、已知状态过滤、模式交集、行/列应用、完成验证和 trace replay
  分成可直接调用的小函数。
- 主循环按稳定顺序扫描行再扫描列；已完成的 line 自动跳过。每个有变化的 line 形成一条带依据、候选模式
  数量、变更格、前后 fingerprint 的可回放步骤。
- 前端启用独立数织卡片；结果显示黑格、空格、未定格、状态及逐步推理说明。
- 基础传播停滞时只返回 `UNVERIFIED_ADVISORY` 高层建议，不允许模型返回的填格直接改变结果。

### 非目标

- 不做整盘 DFS、回溯、唯一解枚举、概率猜测或“试一个格子看看”。
- 不实现浏览器内交互作答、关卡编辑器、图库、排行榜或云存档。
- 不支持彩色数织；本轮只做黑白数织。
- 不绕过 DeepSeek normalization，不做未经授权的真实付费模型调用。

## 3. 方案与契约

### 3.1 Canonical input

```json
{
  "row_clues": [[1], [3], [5], [3], [1]],
  "column_clues": [[1], [3], [5], [3], [1]]
}
```

`grid` 可省略；提供时必须与线索尺寸一致，cell 只接受 `null`（unknown）、`1`（filled）、`0`（empty）。
行列各 1..50 条、总格数不超过 2500；每条 clue 为正整数序列，最短占用长度不得超过 line 长度。空线索
使用 `[]`。解析与求解阶段都 fail closed，不默默修正矛盾题面。

### 3.2 确定性 line engine

核心函数责任：

```text
validate_spec → build_state
generate_line_patterns(length, clues)
filter_compatible_patterns(patterns, known_line)
intersect_patterns(compatible)
analyze_line(kind, index)
apply_line_deductions
is_solved / fingerprint
solve_nonogram / replay_trace
```

`generate_line_patterns` 只枚举**单行线索的合法放置**，这是求交集所需的局部约束表达，不跨行组合，也不
递归搜索答案。为防止恶意输入造成组合爆炸，每条 line 最多保留 100000 个模式，超过即返回清晰错误。
对当前 known line 过滤后若为 0 个模式，立即报 contradiction；所有兼容模式同一位置均为 filled/empty 时，
该格才升级为确定状态。

循环每次取第一个能产生新格的 row/column，应用后从 row 重新扫描。完成 line 与无新增 line 跳过；一整轮
无新增即 fixed point。全部确定且行列 run lengths 均匹配线索才为 `SOLVED`，否则为 `STALLED`。

### 3.3 Trace 与 Agent 边界

每步记录 `technique=line_intersection`、`unit=row|column:index`、clues、兼容模式数、共同格、实际变更格及
before/after fingerprint。replay 从原 canonical 重建，每步重新计算当前确定性下一步；任何目标、依据或
fingerprint 篡改均拒绝。

Gateway 按 kind 分派 Sudoku/Nonogram replay 和 stall advisory。Nonogram advisory 只获得公开 canonical、
当前 grid 与已验证技巧列表；返回内容裁剪为分析和建议技巧，统一标 `UNVERIFIED_ADVISORY`，不得携带或
应用 cell assignments。

### 3.4 Web journey

通用上传/文字入口不变：输入 → DeepSeek normalization → 用户编辑确认 canonical → 签名回执 → session。
`nonogram` session 同步运行确定性组件。前端根据 `session.kind` 分派 Sudoku/Nonogram renderer；数织卡片
只是说明和滚动到统一输入，不增加可绕过 normalization 的直连求解 API。

## 4. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | source | DeepSeek normalizer 严格验证 `kind=nonogram`，且文字/图片必须经过 normalization 和用户确认 |
| A02 | yes | source | 矩形、空线索、预填 grid 可用，非法尺寸、cell、clue、最短长度或资源上限 fail closed |
| A03 | yes | source | 模式生成、兼容过滤、交集、line 分析、应用、完成检查和 replay 均有独立函数边界 |
| A04 | yes | source | 行列循环只落所有兼容模式的共同结论，跳过完成 line 并在固定点停止 |
| A05 | yes | source | 无整盘搜索、回溯或概率猜测；基础规则不足返回 `STALLED` 并保留 unknown |
| A06 | yes | source | 手算 fixture 得到预期 grid，矛盾明确报错，完成盘复核全部行列 clues |
| A07 | yes | source | 每步包含 unit、clue、兼容模式数、共同结论、变更格和前后 fingerprint，顺序稳定 |
| A08 | yes | source | canonical trace 可重放相同终态，关键字段或 fingerprint 篡改被拒绝 |
| A09 | yes | source | STALLED 后 Agent 只返回 `UNVERIFIED_ADVISORY` 分析/技巧，不能携带或应用填格 |
| A10 | yes | source | catalog、Gateway、Web session 和前端 renderer 完成数织 journey |
| A11 | yes | source | 页面区分黑格、空格、未定格，并逐步显示依据与 SOLVED/STALLED |
| A12 | yes | source | 回执和既有本地安全门保持，不能直连绕过 normalization 求解 |
| A13 | yes | source | 聚焦、全量、JS、diff、文档 gate fresh GREEN，既有 journey 不退化 |
| A14 | yes | source | README/current architecture 同步 canonical、确定性传播、STALLED/Agent 和无搜索边界 |
| A15 | yes | integration | feature 独立提交并本地 merge 到 main，merge 后全量通过且不 push |

## 5. Contract impact map

| 维度 | 影响 |
|---|---|
| canonical SSOT | `components/nonogram/solver.py` 定义规格、状态、步骤与 replay；normalizer 定义外部 envelope |
| active consumers | `PaperPuzzleGateway`、Web session dispatch、前端 renderer、README/current architecture |
| templates/generators | 无代码生成器；DeepSeek system prompt 是 canonical 生成入口，必须同步 |
| mechanical checks | engine/replay、normalizer、gateway、Web journey、静态页面与全量回归 |
| historical snapshots | P0006/T0005 的 disabled 记录与 P0007/T0006 不回写；living README/docs 更新 |
| search terms | `nonogram|数织|picross|路线图|disabled|kind.*sudoku|session.kind` 全仓分类检查 |

## 6. 实施拆分

1. RED：以手算小盘测试规格校验、合法 line 模式、交集、传播、矛盾、停滞和 trace 防篡改。
2. GREEN：实现独立 nonogram contracts/solver，保持无搜索路径；聚焦测试转绿后重构小函数。
3. RED/GREEN：扩展 normalizer、gateway 与 Web session contract，证明所有数织输入仍需有效 normalization
   receipt，模型 advisory 不能改格。
4. 前端启用卡片和数织结果 renderer，显示格子状态与逐步依据；同步 README/current architecture。
5. 运行聚焦、全量、diff/文档 gate、本地服务与真实 Chrome smoke；完成 task 逐项验收后提交。
6. 按用户授权在本地将 feature 分支 `--no-ff` 合并到 `main`，在合并后再次运行全量测试；不 push。

## 7. 风险与恢复

- **局部模式爆炸**：尺寸、总格数和每行模式数三重上限；超限显式报错，不占满进程。
- **把局部枚举误当整盘穷举**：生产代码不包含跨 line 分支、猜格或回溯入口；STALLED 测试证明固定点停止。
- **DeepSeek 格式误识别**：normalizer 严格校验，用户确认页允许修正 canonical，错误线索不能签发有效确认。
- **trace 看似解释但不可验证**：replay 重新生成下一步和 fingerprint；篡改 technique/target/premise 必须 RED。
- **前端与 Sudoku 绑死**：按 kind 分派 renderer，不重写现有 Sudoku journey；旧测试继续回归。
- **恢复**：nonogram 是隔离模块；可将 catalog 卡片降级并撤回 kind dispatch，不迁移持久数据。

## 8. 验证策略

- 独立 oracle：手算 line 模式与小盘答案，不用 solver helper 生成 expected。
- mutation probes：漏最小间隔、把“所有模式一致”改成“任一模式”、允许 0 clue、继续猜一个 unknown、replay
  忽略 premise，分别应触发测试失败。
- TestClient 走真实 intake/confirm/session 路径；fake normalizer 只代替外部 DeepSeek，不绕过收据门。
- 浏览器 smoke 用 fake fixture 或已签 session 的本地页面验证卡片、结果盘和步骤文本；不进行付费调用。
- commit 前和 merge 后均运行项目全量 unittest；JavaScript 语法、diff、HAiKnow lifecycle/changed-contract 同步检查。

## 9. 授权与冻结边界

用户授权本轮实现、全部提交并 merge。授权覆盖本地代码、测试、文档、commit、切换本地主分支和本地
`--no-ff` merge；不覆盖 push、PR、公网部署、付费 DeepSeek 调用或删除用户数据。本文成稿自审通过并进入
执行后冻结，偏差和验收证据只写 T0007。

## 10. 成稿自审记录

- 日期：2026-10-03。
- 审核者与上下文：主 agent 从文件完整重读两轮；宿主规则不允许未获用户要求的 subagent，因此没有冒充独立审核。
- 被审版本：第二轮排除本节的正文 SHA-256 `fb5c6bb3af88c091cdd66a9340eb15df90eeb7ca0eb882e8ca03a6b5b499f7c8`。
- 意图与范围：只交付黑白数织确定性组件、统一 DeepSeek 入口、过程显示和本地集成；交互作答、彩色、搜索和付费调用边界明确。
- 事实与假设：实现缺口、测试入口、当前 Git tuple 均有 fresh 文件/命令证据；preflight 的 remote freshness 识别失败已与直接 Git 证据区分记录。
- 方案与步骤：canonical、line engine、固定点、trace/replay、Agent 裁剪、Web journey 责任闭合，下一执行者无需猜关键格式。
- 影响范围：normalizer、canonical SSOT、gateway、session、frontend、tests、living docs 与历史边界均列入 impact map。
- 风险与恢复：局部组合上限、矛盾、模型误识别、trace 伪解释、旧 journey 回归和模块撤回均有控制与负例。
- 验证与验收：A01–A15 均可观察；engine 使用手算 oracle，Web 使用真实 receipt journey，浏览器证据不冒充模型实调用。
- Findings：第一轮发现 canonical 示例声明 5 行线索却只给 1 行 grid，属于会误导实现的 blocker；已删除该无效可选 grid。第二轮完整重读未发现新 blocker。
- 最终结论：通过，可按用户 skip-review、本地 commit/merge 授权冻结执行；不构成 push、公网部署或付费调用授权。

---
id: T0007
title: 数织确定性推理组件与本地 Web 做题过程
status: in_progress
created_at: 2026-10-03
paired_plan: P0008
acceptance_contract: v1
related_commits: []
---

# T0007 · 数织确定性推理组件与本地 Web 做题过程

## 范围结论

按已冻结 P0008 实现黑白数织确定性 line propagation、trace/replay、强制 normalization、Agent advisory、
本地 Web 过程显示和本地 merge。本任务不含整盘搜索、交互作答、彩色数织、push 或付费模型调用。

- task_scope: pending
- overall_goal: pending

## 实际步骤

- 2026-10-03：扫雷以 `db773c3` 独立提交；fresh fetch 后直接 Git tuple 为 origin/main behind=0、ahead=2、worktree clean。
- 2026-10-03：P0008 走用户已授权 skip-review，完成两轮全文自审并修复 canonical 示例 blocker 后冻结执行。
- 2026-10-03：建立 importable placeholder 后运行 7 项 engine RED；初跑为 1 failure + 6 errors，调整占位返回与防篡改 fixture 后得到 10 个目标行为 assertion failures（歧义盘停滞因占位恰好通过），确认缺口后实现 line pattern、兼容过滤、交集、固定点、矛盾、fingerprint 与 replay，7/7 GREEN。
- 2026-10-03：normalizer/gateway/Web 第二轮 RED 为 3 failures + 2 unsupported errors；扩展 `kind=nonogram`、Gateway dispatch/advisory、session 和 renderer 后，与 engine 合计 17/17 GREEN。
- 2026-10-03：同步 README/current architecture；全量 169/169 GREEN。额外用独立 bit-product oracle 穷举核对 line length 1..8 的所有 clue pattern 集合，PASS。
- 2026-10-03：临时 fake normalizer 服务 + 真实 Chrome 完成 intake、canonical 确认、5×5 方框求解和 10 步过程显示，全程无付费调用；视觉检查发现 `<ol>` 与手写序号重复，修正 Sudoku/Nonogram 同类渲染后复验为单一编号。

## 与计划的偏差

无范围或架构偏差。浏览器 smoke 使用 `/private/tmp` 的临时 fake normalizer 服务代替真实 DeepSeek，严格保持“无付费调用”边界；验收后已停止服务并移除临时模块。

## 关键 commit

扫雷前置提交：`db773c304112ba22b0dce0dedac6f00f34345858`。数织 feature commit 与本地 merge 待本节后续追加；用户已授权 commit/merge，未授权 push。

## 测试 / 验证

- Engine RED：`.venv/bin/python -m unittest tests.test_nonogram_solver -v` → 10 个目标行为 assertion failures；GREEN → 7/7。
- Integration GREEN：engine + normalizer + gateway + nonogram Web → 17/17。
- 全量：`.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q` → 169/169 GREEN。
- 独立 oracle：长度 1..8 的全部二进制 line 按 run clue 分组，与生成模式集合逐一相等。
- 静态：`node --check src/puzzle_agent/web/static/app.js` 与 `git diff --check` GREEN。
- 浏览器：真实 Chrome 显示 SOLVED、25 格状态、10 条 line/clue/pattern-count/changes 过程；重复编号修复后复验通过。

## 验收逐项处置

| ID | 结果 | 证据引用 | 适用身份 | 承接或授权 |
|---|---|---|---|---|
| A01 | pass | tests.test_intake_normalizer + tests.test_nonogram_web_api | source-tree@P0008 | — |
| A02 | pass | tests.test_nonogram_solver invalid/prefilled/resource cases | source-tree@P0008 | — |
| A03 | pass | nonogram public imports + 7 engine tests | source-tree@P0008 | — |
| A04 | pass | frame propagation + ambiguous fixed-point tests | source-tree@P0008 | — |
| A05 | pass | 2x2 STALLED test + no-search source scan | source-tree@P0008 | — |
| A06 | pass | 5x5 frame oracle + contradiction tests | source-tree@P0008 | — |
| A07 | pass | step contract assertions + Chrome 10-step trace | source-tree@P0008 | — |
| A08 | pass | replay equality + three tamper mutations | source-tree@P0008 | — |
| A09 | pass | nonogram advisory assignment-cropping test | source-tree@P0008 | — |
| A10 | pass | gateway/Web TestClient journey | source-tree@P0008 | — |
| A11 | pass | Chrome 5x5 board and single-numbered trace | browser-smoke@8018 | — |
| A12 | pass | forged receipt rejection + existing middleware regression | source-tree@P0008 | — |
| A13 | pass | 17 focused + 169 full + JS/diff/lifecycle | source-tree@P0008 | — |
| A14 | pass | README + docs/01-puzzle-agent-architecture.md | source-tree@P0008 | — |
| A15 | unknown | feature commit ready; integration not run | local-main@pending | local `--no-ff` merge then full regression |

## 后续 todo

- 可另立任务实现集合包含、区段边界等高级可验证技巧；本轮不预埋整盘搜索。

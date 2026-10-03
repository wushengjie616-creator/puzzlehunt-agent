---
id: T0015
title: 从题目规则归纳可执行纸笔推理方法
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_plan: P0016
acceptance_contract: v1
---

# T0015 · 从题目规则归纳可执行纸笔推理方法

## 实际步骤

- 2026-10-04：完成当前分支与源码基线勘察；自动 preflight 因 remote state unknown 返回 stop-and-ask，随后 `git fetch origin` 并手工确认 `origin/main` 是 HEAD 祖先、分支 0 behind / 14 ahead，用户明确允许继续当前分支。
- 2026-10-04：完成 P0016 skip-review 计划与主执行者成稿自审，选择受限 DeductionProgram，不执行模型生成的任意代码。
- 2026-10-04：按 TDD 建立 strict `RulePuzzleSource` / `DeductionProgram`、独立 METHOD_SYNTHESIS 适配器和共享 fixed-point engine；先后观察到缺 package、缺 replay、缺 intake/gateway/Web route 的 RED，再实现至 GREEN。
- 2026-10-04：将 `rule_puzzle` 接入 normalizer、gateway、session API 和可视化确认页；支持 full/next-step，缺方法合成 provider 明确返回 503。
- 2026-10-04：用同一引擎离线求解原创 Futoshiki、Kakuro、Skyscrapers fixture，并建立含五题、五张 PNG 和完整讲解的 `examples/paper-puzzle-demos/`。
- 2026-10-04：同步 README、架构、设计学习日志、纸笔子页与主题索引，完成全量回归、mutation probe、图片再生成和文档 contract 检查。

## 与计划的偏差

- P0016 设想 validator 对“不支持规则”返回 `NEEDS_REVIEW`；首版实际在方法合成/程序校验边界以 `RulePuzzleError` 失败关闭，Web 映射为 HTTP 422。没有把错误程序包装成可执行结果，安全语义保持一致。
- 浏览器自动化 surface 在本环境返回 `Browser is not available: iab`，未形成真实浏览器截图证据；前端以 TestClient 静态 surface assertion、JavaScript syntax 与 API journey 验证承接。真实 DeepSeek 视觉/方法合成 smoke 未获付费调用授权，保持未执行且未声称成功。

## 关键 commit

- `abddd49`：建立 P0016/T0015。
- `14c1b4e`：rule-derived engine、normalizer/gateway/Web 接入与聚焦测试。
- `d4280fc`：五题原创演示库、确定性图片生成器与离线重放测试。
- `1d60bbb`：README、架构、设计日志与主题索引同步。

## 测试 / 验证

- RED：`tests.test_rule_based_puzzle` 最初因 package 不存在失败；增加 engine test 后因 `replay_trace` 不存在失败；接入 tests 分别因 preferred kind、gateway provider 参数和页面入口缺失失败。
- GREEN：`.venv/bin/python -m unittest tests.test_rule_based_puzzle tests.test_intake_normalizer tests.test_paper_puzzle_gateway tests.test_web_api -q`，31/31。
- Demo：`.venv/bin/python -m unittest tests.test_paper_demo_examples -q`，5 个 case 的 PNG 解码、结果复算及 rule-based trace replay 通过。
- Full：`.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q`，221/221。
- JavaScript：对 `src/puzzle_agent/web/static/*.js` 全部执行 `node --check`，通过。
- Mutation：mock `_less_than_support` 为 no-op 后，gateway 端到端测试由预期 `SOLVED` 变成 `STALLED` 并失败，`mutation_killed=True`。
- Generator：连续两次生成五张 PNG 的 SHA-256 逐项一致；`git diff --check` 通过。
- Browser：本地服务可在 127.0.0.1:8021 启动/正常关闭；IAB surface 不可用，未做真实浏览器自动化。
- Paid model：未运行真实 DeepSeek 图片或方法合成调用；fixture/fake provider 仅证明合同和后半段执行。

## 验收逐项处置

| ID | 结果 | 证据引用 | 适用身份 | 承接或授权 |
|---|---|---|---|---|
| A01 | pass | strict contracts tests 拒绝未知字段/代码、悬空引用、coverage 缺口与超界输入 | rule source/program contracts | T0015 completed |
| A02 | pass | METHOD_SYNTHESIS prompt 隔离与非法 JSON fail-closed 测试 | synthesis adapter + fake provider identity | T0015 completed；真实模型另需付费 smoke |
| A03 | pass | all-different/less-than/sum/visibility 共享传播器及 local candidate budget 测试 | rule-based engine | T0015 completed |
| A04 | pass | next-step、fingerprint、provenance、replay 与终局 constraint 验证测试 | engine trace | T0015 completed |
| A05 | pass | Futoshiki/Kakuro/Skyscrapers 同一 engine test 与 demo replay | 原创离线 fixtures | T0015 completed |
| A06 | pass | normalize→confirm→synthesize→solve API journey、503 反例、页面入口/编辑器断言 | TestClient + static Web surface | T0015 completed；真实浏览器 smoke 未执行但非必需目标 |
| A07 | pass | manifest validator 检查五题全部六类文件和 PNG | `examples/paper-puzzle-demos/` | T0015 completed |
| A08 | pass | demo 离线复算/replay、PNG decode、生成哈希一致；README 明示真实 DeepSeek 未测 | original demo fixtures | T0015 completed |
| A09 | pass | README、架构、学习日志、纸笔页面、索引与本 task 同步 | current docs | T0015 completed |
| A10 | pass | 221/221、全部 JS syntax、demo validator、mutation killed、diff check 与 HAiKnow gates | repository at closeout commit | T0015 completed |

## 范围结论

- task_scope: complete
- overall_goal: complete
- P0016 的本地 source、离线演示、文档和提交已完成；真实付费 DeepSeek smoke 与不可用的浏览器 surface 均未计作完成证据。

## 后续 todo

- 可选后续：经用户单独授权后，用五张 `puzzle.png` 做一次真实 DeepSeek 视觉与 METHOD_SYNTHESIS smoke；其结果不得回写为本次离线测试证据。
- 可选后续：按真实题型失败证据扩展新白名单原语，不允许用任意代码执行绕过合同。

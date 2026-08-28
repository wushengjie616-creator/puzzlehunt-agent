---
id: T0004
title: CCBC16 文本题八小时循环评测
status: in_progress
created_at: 2026-08-28
paired_plan: P0005
related_commits: []
---

# T0004 · CCBC16 文本题八小时循环评测

配对计划：[P0005](../plans/_drafts/P0005-ccbc16-hourly-text-evaluation.md)。

## 当前基线

- 49 道非 Meta manifest 已存在。
- 旧 hard converter 忽略实际 `html` 字段，仅凭顶层 `image`/`script` 判断 artifact；文档中的“28 道文本题”不足以证明真实可运行题面。
- 旧 oracle 只有最终答案；graph 没有独立 intermediate verification node。
- 旧 scheduler 是三小时 v2 原创题周期，已请求停止，避免与新小时目标混跑。

## 执行记录

- 2026-08-28 14:04 +08：旧 v2 scheduler 正常停止，0 个 v2 正式周期被误跑。
- 2026-08-28 14:05 +08：重新获取 49 个官方 payload；确认共同包含 `html`、`analysis`、`solution` 等字段，旧转换器的 surface/oracle 契约需要修正。
- 2026-08-28 14:09 +08：converter RED 证明 HTML-only 题面丢失、内联图片未 gate；修复后 hard converter 相关测试 4/4 GREEN。
- 2026-08-28 14:12 +08：生成器 RED/GREEN；真实 strict text gate 为 10/49，IDs 3/6/7/10/27/28/30/36/37/38。39 题保留逐题 excluded reason。
- 2026-08-28 14:16 +08：自动 emphasis 提取仅覆盖 1/10，未冒充完整 oracle；加入 ignored human-reviewed override 后 10/10 具备 checkpoint，共 35 个。
- 2026-08-28 14:17 +08：新增 `VERIFY_INTERMEDIATES` 与 evidence-reference machine gate；normal=6 calls、one replan=8 calls。最终与中间 evaluator 分离。
- 2026-08-28 14:18 +08：小时报告 formatter 与 scheduler 接线完成；报告含时间戳、逐题耗时、双评分、节点问题、失败分析和下一轮优化假设。
- 2026-08-28 14:27–14:29 +08：冻结 commit `cf0155d`，通过 CLI 对 10 道 strict-text 题完成一次真实 DeepSeek 端到端基线。10/10 生成 state 与 node analysis，0 timeout；最终答案 0/10、中间验证 0/10、推理通过 0/10；`ccbc16-010` 因首节点非法 JSON 为 ERROR，其余 9 题到达最终验证后为 NEEDS_REVIEW。公开报告：`benchmarks/cycles/hourly-reports/manual-20260828-142757.md`。
- 2026-08-28 15:00–15:03 +08：首个正式小时周期冻结 commit `06cf18f`，10/10 worker 正常完成，0 timeout、0 provider error，但 final/intermediate/reasoning 均为 0/10。节点报告集中出现 `EMPTY_PLAN`、`FAILED_TOOL_CALLS` 与 8 次 replan；#46/#48 把 127/192 条线索扁平处理，#6 缺少扫雷传播，#27 反复尝试错误乱码链。公开报告：`benchmarks/cycles/hourly-reports/cycle-20260828T070000Z.md`。
- 2026-08-28 15:04–15:12 +08：完成一次 CLI 生命周期验收。真实 DeepSeek 首节点成功写入 checkpoint，后续分别暴露 TLS handshake timeout 与 `finish_reason=length`；同一 checkpoint 使用 offline provider 恢复并依次经过工具、证据、中间验证、终局验证和 finalize，证明编排可恢复但真实 provider 稳定性仍未闭环。
- 2026-08-28 15:13–15:22 +08：依据 15:00 报告新增 `MATERIALIZE_SUBPROBLEMS`、`structure_model/subproblems/subproblem_results` memory，正常路径 7 calls、单次 replan 9 calls；移除空计划的隐式 `cipher_workbench` fallback；计划加入 signal/prediction/falsifier contract；重复 fingerprint 不再执行。新增 `bounded_mojibake_scan` 与 `minesweeper_propagate`。全量 101 tests GREEN。
- 2026-08-28 15:13–15:22 +08：完成 49 题文本表面分类收敛：direct text 10、可保真静态/音频转写队列 16、仅文本不可保真 23、pending 0。该分类不冒充实际转写完成；当前可运行套件仍只有 direct 10，后续必须逐题完成 source-hashed human review 才能扩到 26。
- 2026-08-28 15:22–15:30 +08：完成 #52–#54 静态题逐格人工复核，并发现 final feeder 的完整输入还包含 unlock-time state：#52 的印刷 Meta 答案、#53 的火药 Meta 答案及已解 8x4 颜色网格、#54 的造纸 Meta 答案及 `〔〕=同音` 操作符。三题均保存当前 artifact 与上游来源 SHA-256、`unrepresented_channels=[]`，且各配置 3 个 reviewed intermediate checkpoints。v10 suite 为 13/13 valid；审计现为 direct 10 + reviewed 3 + queue 13 + not-faithful 23。
- 2026-08-28 15:40–15:51 +08：真实单题流程首先在 `ASSOCIATE_THEME` 以 4096 output-token 上限截断；TDD 增加非空 `finish_reason=length` 诊断和分阶段字符预算，102 tests GREEN。软预算复跑仍被截断，随后依据 DeepSeek JSON Output 契约把生成上限有界提高到 16384。commit `b14cde8` 的同题复跑 9/9 调用成功，完整经过 materialize、一次 replan、两轮 tool/evaluate、中间门禁和最终门禁，最终诚实停在 `NEEDS_REVIEW`；命中 2/9 官方中间 checkpoint，没有伪造最终答案。诊断报告：`.puzzle-agent/diagnostic/live-one-run/live-one-16k-budget/report.md`。
- 2026-08-28 16:00–16:04 +08：正式小时周期冻结 commit `7973af4`，13/13 worker 完成，0 timeout、0 provider error，全部到达安全终态 `NEEDS_REVIEW`。最终/整题中间/推理通过均为 0/13；局部 checkpoint 命中 #3=2/9、#27=3/6、#54=1/3。公开报告：`benchmarks/cycles/hourly-reports/cycle-20260828T080000Z.md`。
- 2026-08-28 16:05–16:18 +08：节点审计发现 89 个 `subproblem_results` 中有 33 个非空，但 0 个被提升为 evidence；#3 实际已有约 8/9 个 clue answer。新增 `VALIDATE_SUBPROBLEMS` 三分证据门、值不可变与 provenance/falsifier contract；默认预算升为 normal=8、one-replan=10。同步修复韩文 `안녕` 被归一化为空的 Unicode evaluator 缺陷，并将 reviewed transcription 从 3 扩到 10，审计目标变为 direct 10 + reviewed 10 + queue 6 + not-faithful 23。
- 2026-08-28 16:23 +08：小时报告节点作用 RED/GREEN：旧 formatter 不展示 `node_summary`，新增逐节点激活、次数、耗时、可观察效果、作用判断和问题表；相关 cycle suite 13/13 GREEN。下一次真实周期将作为新验证节点和新报告合同的首次运行证据。

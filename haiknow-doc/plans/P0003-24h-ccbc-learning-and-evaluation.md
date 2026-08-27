---
id: P0003
title: 24 小时 CCBC16 学习、框架演进与周期评测
status: in_progress
created_at: 2026-08-28
paired_task: T0003
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - ../docs/02-agent-design-journey.md
evidence:
  - "2026-08-28T03:00:29+08:00 启动；用户明确要求连续工作 24 小时并每 3 小时运行一次 5 题评测"
  - "haiknow task preflight --intent new-task => use-current / non-git-project"
  - "项目无 .git，GitHub CLI 已认证 wushengjie616-creator，目标 puzzlehunt-agent 尚不存在"
  - "现有 complex suite 36/36 通过，但 ToolRegistry 仅有四个结构工具，CCBC16 抽象机制表尚未形成可执行方法库"
---

# P0003 · 24 小时 CCBC16 学习、框架演进与周期评测

<!-- 一旦执行此 plan 即冻结；偏差只写到 T0003 的“与计划的偏差”章节，不回改本 plan -->

## 背景与目标

在 P0002 的可恢复多阶段 Agent 基础上，建立一个可审计的 24 小时学习—实现—评测闭环：以 CCBC16 公开题目和题解为方法研究来源，抽象项目独有的 PuzzleHunt 方法论，把确定性且边界清楚的步骤实现为工具，把需要判断的步骤改进为 Agent 节点契约；用 5 道原创题每 3 小时冻结版本评测一次。

窗口：`2026-08-28 03:00 +08:00` 至 `2026-08-29 03:00 +08:00`。计划评测锚点为 0h、3h、6h、9h、12h、15h、18h、21h、24h；实际开始/结束时间与偏差写入运行记录。

## 非目标与边界

- 不把 CCBC16 原题、完整题解或答案批量复制进仓库或 DeepSeek prompt；只保存来源 URL、机制摘要、少量必要事实和原创派生数据。
- 不把评分 oracle 交给 provider；评测输入、oracle、rubric 物理分离。
- 不在评测批次运行期间修改代码、题面或 oracle；每批记录 Git commit 作为冻结版本。
- 真实 DeepSeek 调用由用户本次指令明确授权，但仍受每题 1 小时 wall-clock timeout、每 session 调用预算和 24 小时窗口约束。
- 若缺少远端或认证则继续本地 Git 与评测，并显式记录 upload blocked；当前证据允许采用私有 GitHub 仓库作为安全默认。
- “提前全对”只由一整个冻结批次 5/5 且 evaluator 全部通过触发。触发后的硬测试集只运行一次；受版权边界约束，使用官方 URL + 本地文本抽取/结构摘要，不提交或回显批量原文。

## 方案

采用四个相互解耦的工作流，由同一个 T0003 承载：

1. **WS-GIT**：初始化 Git，创建私有 GitHub repo；自动发布器只处理 allowlisted 项目文件，先检查 ignore 与 secret，再 commit/push；无变化不造空 commit。
2. **WS-LEARN**：subagent 并行研究 CCBC16 非 meta 题；主代理做来源核验、去重和术语统一，形成“信号 → 假设 → 操作 → 中间验证 → 提取 → 反证”的方法卡。
3. **WS-EVOLVE**：方法卡按三类落地：确定性纯函数进入 ToolRegistry；需要策略判断的进入节点 prompt/state contract；尚无可靠 oracle 的保留为研究假设。
4. **WS-EVAL**：5 道原创 Markdown/text 谜题；runner 每 3 小时启动一批，逐题创建独立 session，硬超时 3600 秒，保存阶段时间、最终答案、评分、错误与每个节点的输入贡献/输出贡献/冗余/失败。

## 状态与目录契约

```text
research/ccbc16/
  methodology.md          # 当前方法论 SSOT
  source-ledger.json       # URL、题号、访问时间、机制标签，不存完整原文

benchmarks/cycles/
  cases/<case-id>/         # input.md/input.json + oracle.json + rubric.json + provenance.json
  runs/<cycle-id>/         # manifest、逐题结果、timing、node traces、analysis.md
  hard/                    # 仅在 5/5 gate 后生成；once marker 防重复运行

.puzzle-agent/automation/  # gitignored runtime state、locks、scheduler log、PID
```

每批 `manifest.json` 至少记录：`cycle_id`、计划/实际时间、`git_commit`、provider/model、题目列表、每题 start/end/duration、timeout、answer、score、错误；`node-analysis.json` 记录每节点是否执行、消费了哪些 state、产生哪些可验证增量、是否影响后续决策、失败与改进候选。

## 实施顺序

1. 建 P0003/T0003，初始化 Git，确认 ignore/secret gate，创建私有远端并完成基线 push。
2. 以 TDD 增加周期 case schema、runner、1 小时子进程 timeout、once-only hard gate 和节点分析器。
3. 建立 5 道原创组合机制谜题及独立 oracle/rubric，先验证 leak isolation。
4. 汇总 subagent 研究，建立 source ledger 与方法卡；只把可独立验证的机械步骤实现为工具。
5. 在每个 3 小时锚点冻结 Git commit 并运行一批；运行中持有 evaluation lock，发布器与框架写入等待。
6. 每批结束生成 timing/result/error/node-effect 报告；依据失败证据在下个锚点前进行 TDD 改进并同步架构/学习文档。
7. 若任一冻结批次 5/5，通过 gate 构建非 meta 硬测试 manifest 并仅运行一次，生成错误分析与耗时报告；不因硬测试失败重复运行。
8. 24 小时结束停止 scheduler，做 base/complex 测试、secret scan、Git/remote 状态和报告完整性审计。

## 跨文件影响图

| 维度 | 内容 |
|---|---|
| canonical SSOT | 方法论=`research/ccbc16/methodology.md`；运行状态=`.puzzle-agent/automation`；评测事实=`benchmarks/cycles/runs`；Agent state=LangGraph checkpoint |
| active consumers | CLI、scheduler、cycle runner、ToolRegistry、complex graph、benchmark evaluator、README/架构/学习日志 |
| templates/generators | case scaffold、cycle manifest、node report；生成器受 schema 测试保护 |
| mechanical checks | base/complex unittest、leak sentinel、timeout probe、once marker、secret gate、clean-clone CLI smoke |
| historical snapshots | P0001/P0002/T0001/T0002 与既有 derived benchmark 不回写，只作基线证据 |
| search terms | `ToolRegistry|STAGE_PROMPTS|benchmark|oracle|timeout|cycle|scheduler|git push|DEEPSEEK_API_KEY|ccbc16` |

## 风险与恢复

- **成本失控**：每题 session 调用预算固定，runner 记录请求数；超时强制终止子进程，不自动重试整批。
- **评测污染**：题面冻结、oracle 分离、prompt capture 和答案字面 leak 检查；同一批次代码 commit 固定。
- **自动提交秘密**：`.env.local`/runtime 目录必须 ignored；staged diff secret scanner 失败即拒绝 commit/push。
- **后台进程失活**：PID/heartbeat/next-run 持久化；重复启动使用 lock 拒绝；主代理每次恢复先核 heartbeat。
- **并发写冲突**：subagent 不写共享文件；主代理单写；evaluation lock 期间不变更框架。
- **方法过拟合**：每条方法必须写触发信号、反证与适用边界；只有独立 known vector 才能进入确定性工具。
- **版权/来源风险**：不提交 CCBC16 批量题面或完整题解；硬测试使用链接、抽取器与结构化摘要，报告只保留错误类型。

## 验证与验收

- [ ] Git 仓库、私有 origin、基线 commit 和安全自动发布器可用；`.env.local` 从未进入任何 commit。
- [ ] 24 小时 scheduler 可恢复、可停止、3 小时 cadence 可审计，单题 timeout 为 3600 秒。
- [ ] 至少 5 道原创纯文本/Markdown 谜题通过 schema、oracle isolation 和 leak 检查。
- [ ] 每个实际批次都有冻结 commit、耗时、结果、错误和逐节点作用报告。
- [ ] CCBC16 方法论具有来源 ledger，并明确事实/推断、信号、操作、验证、反证和 Agent 落点。
- [ ] 新增确定性工具均经过 RED→GREEN、独立 known vector、无效输入与 mutation probe。
- [ ] Agent 框架改进均能由某次实际失败或节点报告支撑，不凭“可能有用”堆功能。
- [ ] 若 5/5 gate 触发，硬测试 once marker 保证只运行一次并输出错误/耗时报告；未触发则报告 gate 未满足。
- [ ] 截止后 background process 已停止，base/complex suites fresh GREEN，remote 与本地 HEAD 一致或明确报告阻塞。

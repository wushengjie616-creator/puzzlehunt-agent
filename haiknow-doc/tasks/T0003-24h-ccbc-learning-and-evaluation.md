---
id: T0003
title: 24 小时 CCBC16 学习、框架演进与周期评测
status: in_progress
created_at: 2026-08-28
paired_plan: P0003
related_commits: []
---

# T0003 · 24 小时 CCBC16 学习、框架演进与周期评测

配对计划：[P0003](../plans/P0003-24h-ccbc-learning-and-evaluation.md)。

## 与计划的偏差

- 计划文本同时列出 0h 与“每过 3 小时”；实现按用户字面语义采用 T+3h…T+24h 共 8 批，不把搭建期间的 offline smoke 冒充正式周期批次。
- 节点作用报告在错误答案时使用 `UNASSESSABLE`，不强行给 `HARMFUL/NEUTRAL` 因果标签；只有正确证据链才评估 `HELPFUL/ESSENTIAL`。

## 实际步骤

- [x] 核实 HAiKnow、时间窗口、Git/GitHub 与现有测试基线。
- [x] 启动三个只读 CCBC16 研究 subagent，主代理保留唯一写入权。
- [x] 初始化 Git、创建私有远端并建立安全自动发布器。
- [x] 实现周期评测 runner、timeout、节点分析与 scheduler。
- [x] 制作并验证 5 道原创测试题。
- [x] 汇总首轮 CCBC16 方法论并按证据扩充工具/框架。
- [x] 审计全部 55 个题目 ID，排除 6 道赛事 Meta，形成 49 题抽象机制账本。
- [x] 实现 49 题一次性 hard runner：临时文本化、oracle 隔离、限并发、脱敏报告与失败不重试。
- [ ] 完成周期运行、报告和 24 小时收尾审计。

## 关键 commit

- `53702e4`：项目 Git 基线、P0003/T0003 与私有 GitHub origin。
- `dd32efe`：guarded publisher、watcher CLI 与 secret/evaluation/stability gates。
- `be6c8c9`：TRACE-LIFT、五道原创题、周期 runner/scheduler 和首批工具/节点契约。

## 测试 / 验证

- 启动前 complex suite：36/36 GREEN（P0002 收尾证据）。
- 自动发布器 RED：缺少 `puzzle_agent.automation`；watch cycle / CLI status / heartbeat 入口缺失，均观察到对应 import 或 CLI failure。
- 自动发布器 GREEN：6 个 module 行为测试 + 1 个 CLI status 测试通过；覆盖临时 bare remote push、secret abort、evaluation defer、validation failure、验证期变化和 lock/state 生命周期。
- 周期 runner RED/GREEN：缺 fixture、runner、worker、timeout、节点分析、schedule 与 CLI status 均分别观察失败；随后 5 题 isolation、进程树 timeout、step trace、并发 offline batch、8 锚点 schedule 全部转绿。
- TRACE-LIFT 首轮汇总 22 个官方来源条目；只保存 URL 与抽象机制标签。五题输入与 oracle/rubric/provenance 分离并通过 leak validator。
- 工具/节点 RED/GREEN：新增 Caesar、A1Z26、interleave、grid trace、constraint order known vectors 与无效/歧义测试；verify 缺 coverage/consumption/independent checks 会被拒绝。
- 当前 complex fresh GREEN：53/53；base fresh GREEN：53 项成功、14 项按 complex capability gate 跳过；原创 v1 suite 5/5 通过 schema/oracle leak validation。
- 研究校正：subagent 把经典 Playfair `BMODZB...` 向量错误归给 `MONARCHY` key；实际独立向量使用 `PLAYFAIR EXAMPLE`。测试先失败并暴露错误，未修改算法迎合错误 oracle。
- 第二梯队工具 GREEN：bit pattern、strict mojibake、common-symbol、grid transform、multitap、Braille、Playfair 共 7 组 known vector 与失败边界通过；graph tool catalog 改为从 registry 动态生成，防新增工具与 prompt 漂移。
- 第二梯队完整回归：complex 55/55 GREEN；base 41 passed + 14 capability skips。watcher 自动发布 commit `a96424a`。
- 全量只读审计：#12/#25/#33/#44/#50 为区域 Meta，#55 为最终 Meta；其余 49 题进入 `source-ledger.json` 与 `nonmeta-manifest.json`。特别固定 `type` 不是 Meta 分类器、题内 meta-style 不等于赛事 Meta。
- hard runner RED/GREEN：先观察缺少模块；随后 3/3 契约测试通过，覆盖 49 ID 集合、题面/oracle 分离、报告脱敏、缓存清理及重复运行拒绝。官方 #1 JSON 做真实无答案输出探针，转换成功。
- scheduler 热重启审计发现 stop sentinel 会跨进程残留；新实例取得 exclusive lock 后现在会清除上一进程的 stop request，避免恢复后立即自停。原 `start_at` 与批次状态保持不变。
- 49 题官方 JSON 全量转换探针：49/49 成功、0 schema failure；21 题因图片/互动依赖进入 `required_artifacts` gate，28 题可直接文本推理。hard runner 不把 URL placeholder 当作已提供 artifact。
- 官方文档复核确认 Chat Completions 当前模型 ID 为 `deepseek-v4-pro`/`deepseek-v4-flash`，现配置的 `deepseek-v4-pro` 有效。周期 worker 的单次 HTTP timeout 调为 600 秒；四阶段最坏 2400 秒仍受父进程 3600 秒硬期限约束。
- 使用 `.env.local` 认证调用官方只读 `/models` 健康检查：认证成功、目标 `deepseek-v4-pro` 在账号可用模型集合中；未输出 key，也未发起计费 completion。
- 证据驱动 replan RED/GREEN：先证明 evaluate 后只能 verify；加入 `decision=verify|replan`、三调用预算保留与 conditional edge 后，最长阶段序列为 observe→plan→evaluate→replan→evaluate→verify（6 calls）。并修复跨轮 tool/assessment evidence ID 重复，focused 5/5 GREEN。
- 节点总报告 RED/GREEN：先证明每题虽有报告但缺少 cycle aggregate；随后新增覆盖全部 8 节点的 `node-summary.json` 与 analysis Markdown 表，含跨题激活、耗时、作用标签和 issue，offline cycle 行为测试转绿。
- 第三梯队工具 RED/GREEN：新增 custom-token Morse、多解逐位 invariant/delta、回文错位和 Unicode codepoint inspection；2 组 known-vector/失败边界测试转绿，分别对应 CCBC16 的视觉点划、多解即信号、回文剩余字和异码位括号机制。
- 将三路全量审计合并为 `mechanism-cards.md`：覆盖 49 道非 Meta 的可观察信号、可复验中间产物和 Tool/Agent/Human 落点，不含答案或批量题面。
- 正式 cycle 1（06:00:29）：冻结 `e440c33`，0/5，五题均 `WORKER_ERROR`，52.453–80.890 秒，无 timeout/错答，hard gate 未触发。session events 证明 intake/artifact 5/5 完成，observe 5 次尝试/1 次完成，hypothesis 1 次尝试/0 完成，其余节点未到达。
- Cycle 1 根因：同一复杂 OBSERVE prompt 在原生 thinking 模式下返回空 `message.content`；小 JSON control 正常，关闭 thinking 后同 prompt 返回合法 JSON（必需字段齐全、10 observations）。因此不是 key/model/network/schema 支持失败。
- Cycle 1 后 RED/GREEN：DeepSeek config 支持显式 thinking/effort、空 content 给出 finish reason；周期 worker 关闭原生 thinking 但保留六阶段有限推理。worker 异常现会持久化失败节点、trace、successful/attempted calls；parent 保存脱敏错误摘要。详见该批 `failure-analysis.md`。
- 正式 cycle 2（09:00:29）：冻结 `4c14005`，2 correct / 1 wrong / 1 NEEDS_REVIEW / 1 ERROR / 0 timeout，16.625–40.156 秒。四题到达 verify；case 04 实际走了一次 replan。hard gate 未触发。
- Cycle 2 失败证据：四个规划案例共 14 次工具调用、0 成功，均因 prompt 只给工具名而模型发明参数别名；case 03 的不确定候选被正确拦下，case 04 却在工具全失败后错误通过 verify。详见该批 `failure-analysis.md`。
- Cycle 2 后 RED/GREEN：registry 从 live callable 自动生成精确签名；cycle summary 新增 `unsolved`；终局机器门拒绝“计划了工具但全部失败”的 solved 状态。focused graph/cycle tests 已先红后绿。
- DeepSeek scheduler 在 cycle 1 故障修复后恢复：runtime PID `50876`；已完成的 06:00 批次保留且不会重跑，下一锚点 09:00:29，最终锚点仍为 2026-08-29 03:00:29（Asia/Hong_Kong）；Git watcher runtime PID `62816`。

## 后续 todo

- 当前执行 P0003 全部范围。

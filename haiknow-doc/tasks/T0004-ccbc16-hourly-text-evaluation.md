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
- 2026-08-28 16:25–16:29 +08：澄清 #37/#38 的公开初始碎片与 `point_cost=3000` 付费提示缩略图完全不相交；suite 只要求转录玩家初始可见 surface，不把提示/题解图泄漏给模型，同时保留初始 HTML 图片必须被 override 覆盖的反向门。v15 最终包含 20/49 题，20/20 `validate_case` 通过；全量 108 tests GREEN。安全发布 commit `d28de0d` 后，旧 v11/9-call scheduler 优雅停止，新 scheduler 继承 15:00/16:00 completed IDs，并以 v15、20 cases、10 calls 等待 17:00。
- 2026-08-28 16:29 +08：v15 的 20 题 offline smoke 在约 15 秒内完成，0 error/timeout；12 个图节点均按预期激活（`human_interrupt` 因素材齐全为 0），每题使用正常路径 8 次 staged call。该结果只证明机械编排与新公开报告闭环，不作为复杂题正确率证据。
- 2026-08-28 17:00–17:04 +08：正式小时周期冻结 commit `ec4ac25`。20 题中 10 题受本轮调用上限执行，0/10 得到 final/intermediate/reasoning pass；其中 8 题被新 `VALIDATE_SUBPROBLEMS` 的严格响应协议截断，另有 1 题 plan JSON 截断、1 题 DeepSeek TLS EOF。公开报告：`benchmarks/cycles/hourly-reports/cycle-20260828T090000Z.md`。该批次证明节点协议完整性是当前优先 blocker，不能把 provider/schema error 解释为解题失败。
- 2026-08-28 17:04–17:14 +08：按 RED→GREEN 修复流程总化边界：已知候选的漏判、冲突和漂移 accepted value 保守降级为 `needs_test`，空结果 verdict 忽略，unresolved coverage 由机器重算，未知 result ID 仍硬拒绝；同时阻止 `VERIFY_INTERMEDIATES` 发明 state 中不存在的值，并消除单字符别名的 evaluator 子串假阳性。聚焦 8/8、相关 26/26、全量 113/113 tests GREEN。
- 2026-08-28 17:14 +08：使用公开 CLI 在隔离 session 根完成 `init → run --offline → status → history → finalize` 生命周期验收。样例 `uryyb` 经 8 个 staged calls、1 次确定性工具执行、11 条 evidence 和 13 个 checkpoint 得到 `SOLVED/hello`，重新加载状态与 final 持久化均成功。该证据证明编排闭环，不代表复杂 CCBC 解题正确率。
- 2026-08-28 17:16–17:26 +08：同一样例改用真实 DeepSeek CLI。首次 run 在 `MATERIALIZE_SUBPROBLEMS` read timeout，但前两节点 checkpoint 保留；再次 `run` 从 calls=2 恢复，完整到 calls=8，并正确产生 semantic `hello`、Caesar 工具 `hello` 和六项终局全真检查。旧门禁因原子题没有 distinct intermediate 而返回 `NEEDS_REVIEW`，证明这是流程拓扑缺口而非解题失败。
- 2026-08-28 17:27–17:38 +08：TDD 加入 atomic direct-answer 窄门，同时现场发现旧 `branch` 仅复制 state、未复制执行游标，会从 `START` 重跑并耗尽预算。新增 branch cursor RED/GREEN，以 `graph.update_state(as_node=last_node)` 重建并核对 `next`。从真实 evidence-evaluation checkpoint 再分支后，状态保持 calls=6/next=verify_intermediates，只调用最后两个 DeepSeek 节点，得到 `SOLVED/hello`；`finalize` 写入 final.json，事件包含 session_branched/session_run/session_finalized。全量 115/115 tests GREEN。
- 2026-08-28 17:15–17:32 +08：三个只读子代理完成流程证据和剩余 transcription queue 复核。queue 精确为 #9/#23/#28/#30/#31/#36；六题理论上都可条件式文本化，但当前只有 #31 接近 reviewed-ready，其余仍缺完整图结构、逐页遮挡转录或实际音频听写。保持 20 题 suite 不变，不用缺失通道凑数；#31 待独立审定“精确墨迹像素轮廓不是 clue channel”后才可纳入。
- 2026-08-28 17:36–17:38 +08：主 agent 重新下载并逐项目视核对 #31 官方 3000×1680 pre-solve raster，源 hash 与候选一致。八个面板的几何、颜色、数字、字母、离散形状方向、答题卡编号框、语义遮挡和可见边界地标均已表达；墨迹逐像素轮廓只承担装饰/遮挡，不是独立 clue channel。将 #31 纳入 reviewed，并把八个子题答案仅写入 evaluator checkpoint。v16 为 direct 10 + reviewed 11 + queue 5 + not-faithful 23；21/21 validate_case 和 21 题 offline cycle 均 0 error/timeout。
- 2026-08-28 18:00–18:04 +08：正式小时周期冻结 commit `426cb1f`，20 题中 17 题安全到达局部、中间与终局验证门，上一轮 8 个局部 schema/protocol error 全部消失；3 题因 IncompleteRead/TLS EOF 分别停在 observe、plan、evaluate。最终/中间/推理仍为 0/20。公开报告：`benchmarks/cycles/hourly-reports/cycle-20260828T100000Z.md`。
- 2026-08-28 18:05–18:12 +08：节点审计确认 17 个安全运行中 14 个触发工具重规划、14 个都未形成 answer candidate；11 题全部局部结果为空，工具层重试无法补回语义载体。调度器已从旧 v15/20-case 进程优雅切换到 v16/21-case，等待 19:00–22:00 四个小时周期。
- 2026-08-28 18:13–18:25 +08：按 RED→GREEN 增加两项有界恢复：显式传输错误从同一 checkpoint 重试同一节点一次，普通 runtime/schema 错误不重试；首轮 accepted/subproblem 覆盖低于 50% 且剩余预算至少 6 时，执行一次 pre-plan `MATERIALIZE→VALIDATE` semantic refinement，保留已验证锚点，零锚点只补 1–3 个题面支撑候选，并禁止之后再用 tool replan。节点报告同步纳入零调用恢复节点。
- 2026-08-28 18:18–18:20 +08：独立代码审查构造出“第二轮 validator 漏报首轮 accepted anchor”反例：旧实现会撤销 accepted state 却残留 semantic evidence；同一子题多个 accepted result 还会虚增覆盖。两个回归测试先稳定 RED，随后机器合并 prior anchors、全量重建 semantic evidence，并改按唯一 subproblem ID 计算覆盖；全量 122/122 tests GREEN。
- 2026-08-28 19:00–19:08 +08：正式小时周期冻结 commit `dd87f1e`，21 题中 15 题安全结束、6 题 ERROR、0 timeout；最终/中间/推理均 0/21。semantic refinement 实际触发 16 题，#10 的 validated local results 由 0→5，#46 保持 7、#53 保持 3，其余完成题多数 0→0；#46 的 verify transport retry 成功恢复。#18/#22 因未知 result ID、#29 因漏填终局 checks 中止，另 3 题为非法/截断 JSON。公开报告：`benchmarks/cycles/hourly-reports/cycle-20260828T110000Z.md`。
- 2026-08-28 19:09–19:14 +08：依据 19:00 报告把未知局部 result ID 改为“记录并忽略、不提升 evidence”，把缺失终局 checks 机器补为 false 并保留 blocker；两个原“必须抛错”测试先 RED 后 GREEN。发现常驻 scheduler 的父进程 node catalog 早于冻结 commit，而 Windows worker 会加载新源码，导致 19:00 公共节点表漏列已实际激活的 `prepare_semantic_refinement`；20:00 前必须在干净提交后重启 scheduler，使执行与报告代码同一版本。
- 2026-08-28 19:15–19:22 +08：#9 修正版通过独立 source-only 准入复核：官方 raster hash、UTF-8 注记/预填、28 节点、43 confirmed edges、46 visible paths、两处 shared-terminal ambiguity 及三 glyph 的逐字节 RLE/hash 全部一致，`unrepresented_channels=[]`。主 agent 仅在 evaluator 侧读取官方解后填字图，加入“完整行序填字”和“三角红框提取”两个 checkpoint；v17 为 direct 10 + reviewed 12 + queue 4 + not-faithful 23，22/22 validate_case 通过。
- 2026-08-28 19:23–19:30 +08：#28 的候选/validation hashes 分别为 `b7d6047…`/`84379ea…`，原 38 项 source-only 重建全绿。因第二 subagent 额度耗尽，主 agent 独立复取官方 data/page/PDF 并匹配 hashes，再从候选重算 54×70 RLE、十类 fill counts、1357+1215=2572 edges、91 visible glyphs、一个 U+3000 和 M14/M15 删边；全部一致且 `unrepresented_channels=[]`。四个题解 checkpoint 仅写 evaluator；v18 为 direct 10 + reviewed 13 + queue 3 + not-faithful 23，23/23 validate_case 通过。
- 2026-08-28 19:27–19:28 +08：v18/23-case offline cycle 在 12 秒内完成，0 error/timeout；13 个声明节点均出现在 aggregate，`prepare_semantic_refinement` 23/23 激活，证明新增大网格、oracle 隔离、worker 和新版节点报告机械闭环。20:00–22:00 scheduler 已从 commit `5802a02` 重新加载并等待 23-case 正式批次。
- 2026-08-28 19:29 +08：为使 20:00 报告能直接证明安全总化发生，validate trace 现在只把 `AUTO_*` 机器归一化问题写成 `VALIDATION_NORMALIZATION:*` observable effects，并在节点问题列聚合为 `VALIDATION_NORMALIZATION`；模型自由文本不会进入该通道。聚焦测试先 RED 后 GREEN。
- 2026-08-28 19:39–19:45 +08：冻结框架后先完成 v18/23 题离线端到端流程，13 个声明节点全部按条件执行、0 error/timeout；随后用 source-only 颜色分割和人工 overlay 复核完成 #23。官方 1536×2800 raster 的主城市保留 24 yellow + 9 green + 10 black 可见连通区及 contour rings，logo 单独排除，示例/八方向表达式另行转写，不从题解反推隐藏高度。v19 为 direct 10 + reviewed 14 + queue 2 + not-faithful 23，24/24 validate_case 与 24 题 offline cycle 通过。
- 2026-08-28 19:45–19:47 +08：#30 官方 PDF 取证确认 10 页、每页单一 1275×1650 栅格、无可提取文字层；前九页为异构逻辑题，第十页大面积墨迹遮挡。已无损抽取十页供 source-only 转写，确认准入必须同时保留规则、网格/字符和墨迹遮挡 mask，不能把普通 OCR 当作完成。
- 2026-08-28 20:00–20:08 +08：正式小时周期冻结 commit `cf7bc32`，23 题中 20 题安全到达 `NEEDS_REVIEW`、3 题 ERROR、0 timeout；最终/整题中间/推理均 0/23。#3 命中 6/9 evaluator checkpoints；#18 为 OBSERVE 非法 JSON，#53 为恢复轮结果引用未知 subproblem，#22 为计划项缺 signal。公开报告：`benchmarks/cycles/hourly-reports/cycle-20260828T120000Z.md`。
- 2026-08-28 20:09–20:14 +08：把上述三类真实失败逐一固化为 RED，再实现保守总化：非法 JSON/非对象输出记录长度与 hash 后安全终止；未知 subproblem result 和无 signal/缺契约计划项被丢弃并写 blocker；任何 blocker 都禁止终局 `SOLVED`。trace 新增 `PROTOCOL_NORMALIZATION:*`，节点报告聚合对应问题。聚焦测试、worker 集成与全量 128/128 均 GREEN。

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

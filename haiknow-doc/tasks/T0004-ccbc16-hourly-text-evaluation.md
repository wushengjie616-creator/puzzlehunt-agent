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

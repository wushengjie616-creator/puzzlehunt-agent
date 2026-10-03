---
id: T0009
title: 紧凑密码图表、猪圈示意图、盲文与旗语
status: completed
created_at: 2026-10-03
paired_plan: P0010
acceptance_contract: v1
plan_completed_at: 2026-10-03
---

# T0009 · 紧凑密码图表、猪圈示意图、盲文与旗语

## 实际步骤

- 已使用内置 GPT 图像生成器生成纯黑白猪圈密码示意图并复制进项目。
- 先写盲文/旗语完整性、visual routing 与图片 API 测试，观察缺常量、26≠36 和缺路由的正确 RED。
- 增加紧凑 10/5 列网格、猪圈 GPT 图、盲文六点图和旗语双臂方向图；移除凯撒/栅栏对照表。
- 在 8017 浏览器逐段检查猪圈、盲文和旗语实际布局。

## 与计划的偏差

- 宿主没有 Playwright，窄屏 5 列以明确 CSS media rule 验证；桌面 10 列、图片和图形已做真实浏览器截图验收。

## 关键 commit

- 尚未提交；与上一轮 P0009 改动一起保留在 `feat/cipher-tools-and-pages`。

## 测试 / 验证

- RED：聚焦测试因缺 `SEMAPHORE_TABLE`、盲文只有 26 项而失败。
- GREEN：聚焦 12 项通过；最终全量 `unittest discover` 178 项通过。
- JavaScript：三个静态脚本 `node --check` 通过；`git diff --check` 通过。
- 图片：2172×724 RGB PNG，680 KiB，SHA-256 `46868a60c2108a15c8d14de2f3bb7b99d1946fad9cfdb1e914d2eee98c09d4b0`；人工核对 A–Z 各一次、第二轮点位正确。
- 浏览器：桌面 10 列 Bacon/盲文格清晰；猪圈图黑白无装饰；旗语 5 列双臂图与方向文字可读；凯撒/栅栏无展开表。
- 数据：盲文 26 字母 + 10 数字；旗语 A–Z 26 个唯一条目；图片路由返回 PNG。

## 验收逐项处置

| ID | 结果 | 证据 | 适用范围 / 下一步 |
|---|---|---|---|
| A01 | pass | 浏览器桌面 10 列；CSS `max-width:760px` 明确切换 5 列 | 密码页面 |
| A02 | pass | 浏览器图片可见 + PNG API/字节测试 + 人工字母点位核对 | 密码页面/静态资源 |
| A03 | pass | visual routing 单测为 `none`；浏览器无展开控件 | 密码页面 |
| A04 | pass | 36 项完整性测试 + 浏览器黑白六点图和数字标志说明 | 密码页面 |
| A05 | pass | 26 项方向已知向量测试 + 浏览器双臂图与方向文字 | 密码页面 |
| A06 | pass | 全量 178 项通过，服务仍运行于 8017 | 全项目 |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 后续 todo

- 若后续增加旗语数字，应复用数字标志语义，不把字母姿势静默当数字。

---
id: P0017
title: 新人可执行 README 与文档索引
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_task: T0016
acceptance_contract: v1
related_docs:
  - ../docs/index-by-topic.md
  - ../docs/01-puzzle-agent-architecture.md
  - P0016-rule-derived-paper-puzzle-methods.md
evidence:
  - "用户要求完全不了解项目的人把 README 交给 Codex 后即可理解 Agent 核心能力，并能用仓库示例无痛演示"
  - "当前 README 混合产品介绍、深层实现、评测调度和自动发布，首次阅读缺少能力地图、推荐演示路径和 Codex 接手顺序"
---

# P0017 · 新人可执行 README 与文档索引

> 用户已直接要求完善 README 与文档索引，按 skip-review 实施。只改文档与示例导航，不改变运行时行为。

## 1. 目标与边界

把根 README 改造成项目唯一新人入口，使人类或 Codex 在一次顺序阅读后能回答：项目解决什么问题、有哪些核心能力、哪些能力是确定性的、如何启动、如何用现成示例演示、哪里查架构与历史、哪些操作会调用付费模型。

同时把 `haiknow-doc/docs/index-by-topic.md` 从历史链接清单升级为按读者任务路由的索引，并补充演示题目录的操作脚本。

不修改 solver、Web、CLI、provider、示例数据或测试语义；不新增付费调用；不把离线 fixture 宣称为真实 DeepSeek 能力证据。

## 2. 实施方案

1. README 前半段固定为：一句话定位、能力地图、可信边界、五分钟启动、推荐演示路线。
2. 为运营演示提供按时长排列的脚本，明确每一步选择什么题型、上传哪个文件、应观察什么结果。
3. 为 Codex 提供“阅读顺序、代码地图、常用验证命令、权限红线”，使其不必从 300 行历史说明中自行猜测。
4. 深层 CLI、复杂图、benchmark、周期评测和自动发布保留为进阶章节，但从新人主路径移出。
5. 文档索引按“第一次了解 / 开发修改 / 推理研究 / 历史追溯”分类，并区分 current owner 与历史 P/T。
6. 为 demo README 增加逐题网页操作、离线验证和预期观察点。

## 4. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | 根 README | 首屏即可看到定位、核心能力、能力边界和推荐入口 |
| A02 | yes | 安装/启动 | macOS/Linux 新人可复制命令启动无登录本地 Web，并知道如何配置或不配置 DeepSeek |
| A03 | yes | 演示流程 | README 至少给出离线零费用、图片纸笔、规则自研、复杂 Agent、密码/扫雷五类可执行演示 |
| A04 | yes | Demo assets | 每个演示引用仓库中真实存在的文件，并说明选择项、操作和预期观察点 |
| A05 | yes | Codex onboarding | README 给出 Codex 阅读顺序、代码地图、验证命令和不得擅自付费/push 的边界 |
| A06 | yes | 文档索引 | index 按任务分类，能从新人入口路由到架构、设计学习、示例、研究和历史记录 |
| A07 | yes | Evidence integrity | 清楚区分真实 DeepSeek、fake/scripted provider、离线 deterministic engine 与浏览器游戏 |
| A08 | yes | Validation | README 命令与 CLI help/真实文件一致，链接检查、示例 smoke、全量测试和 HAiKnow gates 通过 |

## 5. 风险与恢复

- README 过长：把“第一次使用”保持在前半段，深层运行方式折叠为进阶导航，不删除重要能力。
- 文档漂移：所有命令从当前 CLI help 和 `pyproject.toml` 核实；示例路径由脚本检查存在。
- 能力夸大：每条 demo 标明真实模型、离线 fixture 或 scripted provider 的证据身份。
- 恢复简单：本任务只改 Markdown，可按文件回退，不影响运行时。

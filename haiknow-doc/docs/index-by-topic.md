# 项目知识索引

本页是 README 之后的第二入口。先按当前任务选择一个区域，不要从历史 plan/task 逆向猜测现有行为。

## 第一次了解或演示项目

| 你要做什么 | 先读什么 | 得到什么 |
|---|---|---|
| 从零认识 Agent | [根 README](../../README.md) | 能力地图、可信边界、安装、演示路线和 Codex 接手入口 |
| 选择可演示样例 | [示例导航](../../examples/README.md) | 零费用 smoke、纸笔题顺序、运营演示时长建议 |
| 演示纸笔谜题 | [纸笔谜题演示题库](../../examples/paper-puzzle-demos/README.md) | 五题的图片、规则、预期过程与离线复算方式 |
| 查看可用纸笔 case | [演示 manifest](../../examples/paper-puzzle-demos/manifest.json) | case ID、题型、engine、能力标签和真实模型依赖 |
| 演示普通谜题分层推理 | [普通谜题中等难度演示](../../examples/general-puzzle-demos/README.md) | 三道原创 CCBC 风格题、图片、oracle、工具轨迹与证据边界 |
| 查看普通谜题 case | [普通题 manifest](../../examples/general-puzzle-demos/manifest.json) | case ID、机制链与难度 |

新人推荐阅读顺序：`README → examples/README → 当前架构`。只有需要理解设计演化时才继续读学习日志和历史 P/T。

## 当前权威文档

- [当前架构与运行契约](01-puzzle-agent-architecture.md)：Web、normalizer、纸笔组件、复杂图、状态、工具、持久化、安全和测试边界的当前说明。
- [Agent 设计学习日志](02-agent-design-journey.md)：每次架构升级解决了什么真实失败；用于理解“为什么”，不替代当前架构。
- [CCBC16 第一阶段 24 题标准推理轨迹](03-ccbc16-24-case-solution-guide.md)：复杂题的公开证据链与研究样本。
- [D0001 · 第一阶段复盘](../decisions/D0001-puzzle-agent-stage1-retrospective.md)：第一阶段结论与方向判断。

## 按开发任务路由

| 改动主题 | 先读 | 主要代码/数据 |
|---|---|---|
| 本地 Web、图片输入、确认页 | [当前架构 §1–2](01-puzzle-agent-architecture.md) | `src/puzzle_agent/web/`、`src/puzzle_agent/intake/` |
| 数独、数织、扫雷 | [纸笔 demo](../../examples/paper-puzzle-demos/README.md) + [P0018 难度合同](../plans/P0018-harder-paper-puzzle-demos.md) + 当前架构 | `src/puzzle_agent/paper_puzzle/components/` |
| 未知规则纸笔题 | [P0016](../plans/P0016-rule-derived-paper-puzzle-methods.md) + [T0015](../tasks/T0015-rule-derived-paper-puzzle-methods.md) | `components/rule_based/`、demo manifest |
| 普通复杂 Agent | [当前架构 §3–7](01-puzzle-agent-architecture.md) + [设计日志](02-agent-design-journey.md) | `complex_graph.py`、`complex_session.py`、`domain.py` |
| 密码与确定性工具 | [根 README 的能力/代码地图](../../README.md) | `cipher_workbench.py`、`cipher_reference.py`、`tool_registry.py` |
| Benchmark / cycle | [当前架构 §9](01-puzzle-agent-architecture.md) | `benchmark.py`、`cycle_runner.py`、`benchmarks/` |
| 研究方法或 Skill | [TRACE-LIFT](../../research/ccbc16/methodology.md)、[HA-BRIDGE](../../research/human-association-reasoning.md) | `.agents/skills/`、`reasoning_reference.py` |
| README / 演示文档 | [P0017](../plans/P0017-newcomer-readme-and-document-index.md) + [T0016](../tasks/T0016-newcomer-readme-and-document-index.md) | `README.md`、`examples/README.md`、本索引 |

修改行为前应以当前代码和当前架构交叉核实；历史任务中的测试数量、模型表现和分支状态只代表当时快照。

## 推理研究与课程

- [TRACE-LIFT · CCBC16 蒸馏方法论](../../research/ccbc16/methodology.md)：保真转写、线索登记、竞争假设、有界计算、证据审计和终局验证。
- [HA-BRIDGE · CCBC12/15/16 人类联想路径](../../research/human-association-reasoning.md)：从表面异常到本体、桥接和机制验证。
- [CCBC16 机制卡](../../research/ccbc16/mechanism-cards.md)：跨题机制摘要，不是答案库。
- [推理鲁棒性课程](../../benchmarks/reasoning-curriculum-v1.json)：缺 artifact、关键词假阳性、版本冲突、多解不变量等无答案案例。
- `research/*.html`：五份离线研究报告；内容体量大，仅在研究任务中按需查阅，不进入生产 prompt。

## 历史计划与实施证据

这些文件用于追溯范围、授权、偏差和测试证据。现有行为仍以“当前权威文档 + 源码 + 当前测试”为准。

| 阶段 | Plan | Task |
|---|---|---|
| MVP | [P0001](../plans/P0001-puzzle-agent-mvp.md) | [T0001](../tasks/T0001-puzzle-agent-mvp.md) |
| 可恢复复杂 Agent | [P0002](../plans/P0002-complex-puzzlehunt-agent.md) | [T0002](../tasks/T0002-complex-puzzlehunt-agent.md) |
| 24 小时学习与周期评测 | [P0003](../plans/P0003-24h-ccbc-learning-and-evaluation.md) | [T0003](../tasks/T0003-24h-ccbc-learning-and-evaluation.md) |
| CCBC 文本题循环评测 | [P0005](../plans/_drafts/P0005-ccbc16-hourly-text-evaluation.md) | [T0004](../tasks/T0004-ccbc16-hourly-text-evaluation.md) |
| 图片 Web 与数独 | [P0006](../plans/P0006-multimodal-puzzle-web-sudoku.md) | [T0005](../tasks/T0005-multimodal-puzzle-web-sudoku.md) |
| 本地扫雷 | [P0007](../plans/P0007-local-minesweeper-game.md) | [T0006](../tasks/T0006-local-minesweeper-game.md) |
| 数织 | [P0008](../plans/P0008-nonogram-deduction-component.md) | [T0007](../tasks/T0007-nonogram-deduction-component.md) |
| DeepSeek 诊断与密码页面 | [P0009](../plans/P0009-deepseek-diagnostics-and-cipher-pages.md) | [T0008](../tasks/T0008-deepseek-diagnostics-and-cipher-pages.md) |
| 紧凑密码视觉表 | [P0010](../plans/P0010-compact-cipher-visual-reference.md) | [T0009](../tasks/T0009-compact-cipher-visual-reference.md) |
| Agent 密码资料路由 | [P0011](../plans/P0011-agent-cipher-reference-routing.md) | [T0010](../tasks/T0010-agent-cipher-reference-routing.md) |
| 玩家终止推理 | [P0012](../plans/P0012-player-cancel-reasoning.md) | [T0011](../tasks/T0011-player-cancel-reasoning.md) |
| 纸笔路由/拖拽/数独提示 | [P0013](../plans/P0013-paper-intake-routing-dragdrop-sudoku-hint.md) | [T0012](../tasks/T0012-paper-intake-routing-dragdrop-sudoku-hint.md) |
| 鲁棒推理与键盘导航 | [P0014](../plans/P0014-robust-reasoning-and-sudoku-keyboard.md) | [T0013](../tasks/T0013-robust-reasoning-and-sudoku-keyboard.md) |
| CCBC 研究产品化 | [P0015](../plans/P0015-ccbc-reasoning-operationalization.md) | [T0014](../tasks/T0014-ccbc-reasoning-operationalization.md) |
| 按规则归纳纸笔解法 | [P0016](../plans/P0016-rule-derived-paper-puzzle-methods.md) | [T0015](../tasks/T0015-rule-derived-paper-puzzle-methods.md) |
| 新人 README 与索引 | [P0017](../plans/P0017-newcomer-readme-and-document-index.md) | [T0016](../tasks/T0016-newcomer-readme-and-document-index.md) |
| 纸笔演示题难度升级 | [P0018](../plans/P0018-harder-paper-puzzle-demos.md) | [T0017](../tasks/T0017-harder-paper-puzzle-demos.md) |
| 数织入口修复与普通题演示 | [P0019](../plans/P0019-nonogram-intake-and-general-demos.md) | [T0018](../tasks/T0018-nonogram-intake-and-general-demos.md) |
| 普通题风味与推理层次升级 | [P0020](../plans/P0020-flavored-general-puzzle-demos.md) | [T0019](../tasks/T0019-flavored-general-puzzle-demos.md) |

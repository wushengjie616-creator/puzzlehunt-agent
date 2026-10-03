---
id: P0013
title: 纸笔入口路由、图片拖拽与数独单步提示
status: completed
created_at: 2026-10-03
paired_task: T0012
acceptance_contract: v1
plan_completed_at: 2026-10-03
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
evidence:
  - "paper-puzzles.html 链接使用 ?kind=sudoku/nonogram，但 app.js 不读取 URLSearchParams"
  - "create_intake/DeepSeekNormalizer 不接收玩家题型偏好，session 仅按模型 envelope.kind 分派"
  - "solve_sudoku 已有 max_steps 参数，但达到限制后与逻辑固定点同为 STALLED，step 只有机器 premises"
---

# P0013 · 纸笔入口路由、图片拖拽与数独单步提示

<!-- 一旦执行此 plan 即冻结；偏差只写到对应 task，不回改本 plan。 -->

## 1. 目标与非目标

- 首页支持点击选择或拖拽 PNG/JPEG/WebP，继续复用既有服务端 MIME、大小、像素安全门。
- 首页增加题型选择：自动识别、普通谜题、普通数独、数织；纸笔页链接进入后自动预选对应组件。
- 玩家指定题型仍必须经过 DeepSeek normalization；模型输出若与指定题型不符则失败关闭，不静默落入 general。
- 选择数独时显示“只提示下一步 / 完整解题”；单步模式找到第一个可证明数字后停止，并给出人类可观察的理由。
- 不为每种纸笔谜题复制上传页面，不绕过确认回执，不增加猜数、搜索或回溯。

## 2. 方案与数据流

1. 首页 `puzzle-kind` 消费 URL `kind`，显示当前路由；数独时显示 `sudoku-mode`。
2. intake 请求增加可选 `preferred_kind`，normalizer prompt 明确玩家声明并校验输出 kind 一致。
3. session 请求增加 `solve_mode=full|next_step`；仅数独接受 `next_step`，网关映射到 `max_steps=1`。
4. 数独达到一步上限时返回 `STEP_LIMIT` 而非 `STALLED`，因此不会请求 stall advisory；step 增加由 candidates/unit premise 确定性生成的 `explanation`。
5. drop zone 只改变文件取得方式；base64、服务端验证和 DeepSeek 图片链路保持不变。

## 3. 风险与恢复

- 玩家误选题型：normalizer 明确报“输出与所选类型不符”，允许用户改回自动识别后重试。
- 单步模式被误当完整答案：独立 `STEP_LIMIT` 状态、一步计数和提示文案，不显示“已完成”。
- query 参数伪造：前端只接受 allowlist，服务端再次校验 `preferred_kind/solve_mode`。
- 拖拽绕过 input accept：服务端仍检查声明 MIME、真实 magic、解码、10 MiB 和 2400 万像素。

## 4. 验收标准

| ID | 必需 | 可观察结果 | 适用范围 |
|---|---|---|---|
| A01 | 是 | 图片可点击选择或拖入 drop zone；文件名与拖拽状态可见，后端安全门不变 | Web UI/上传 |
| A02 | 是 | `/?kind=sudoku` 和 `/?kind=nonogram` 自动预选对应题型；首页也可手动选自动/普通/纸笔 | Web UI |
| A03 | 是 | 玩家指定题型进入 normalizer prompt，输出 kind 不一致失败关闭 | intake/API |
| A04 | 是 | 数独 `next_step` 恰好最多执行一步，未完成时为 `STEP_LIMIT`，不调用 stall advisory | 数独/Web |
| A05 | 是 | 每个数独步骤含基于候选或行列宫唯一位置的中文观察说明，页面优先展示该说明 | 数独/UI |
| A06 | 是 | 非数独不接受 `next_step`；全量回归、JS、diff、lifecycle 与本地重启通过 | 安全/全项目 |

## 5. 成稿自审记录

- 日期：2026-10-03。
- 审核者：主 agent；宿主策略不允许启动独立 subagent，按 workflow 从文件完整重读降级自审。
- 意图与范围：三项用户目标分别落在上传、显式路由、数独单步；保留所有输入先过 DeepSeek 的既定边界。
- 事实与假设：query 未消费、后端无 preferred kind、solver 已有 max_steps 均由当前源码确认。
- 方案与步骤：统一入口避免复制表单；preferred kind 贯穿 prompt/校验；solve mode 只在 session 执行阶段生效。
- 影响范围：normalizer、Web API、gateway、Sudoku solver、首页 HTML/JS/CSS、纸笔链接、测试和架构文档。
- 风险与恢复：类型冲突失败关闭；单步独立状态；上传后端安全门不放宽；各字段默认保持旧行为。
- 验证与验收：已知数独一步 oracle、normalizer prompt/冲突、API 正负例、静态页面契约、全量与实服检查。
- 授权与冻结：用户明确要求实现；不含 commit、merge、push 或额外付费冒烟。
- Findings：当前 dirty 分支承载 P0009–P0012 同一 Web/密码/Agent 演进，preflight 因未提交而 stop；不切分支、不覆盖无关改动。无 blocker。
- 结论：成稿通过，可冻结并实施。

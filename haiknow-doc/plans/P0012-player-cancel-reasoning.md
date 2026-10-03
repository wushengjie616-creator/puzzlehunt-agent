---
id: P0012
title: 玩家主动终止复杂 Agent 推理
status: completed
created_at: 2026-10-03
paired_task: T0011
acceptance_contract: v1
plan_completed_at: 2026-10-03
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
evidence:
  - "当前 Web 的 POST /api/sessions/{id}/run 同步等待 SessionManager.run，页面没有停止控件或停止 API"
  - "DeepSeekProvider 使用单次非流式 HTTP 请求，Python 线程无法安全强杀；只能在请求边界协作终止"
---

# P0012 · 玩家主动终止复杂 Agent 推理

<!-- 一旦执行此 plan 即冻结；偏差只写到对应 task，不回改本 plan。 -->

## 1. 目标与非目标

- 通用复杂 Agent 运行时显示“终止推理”按钮；点击后浏览器立即停止等待，并向服务端发送停止请求。
- 服务端在当前 DeepSeek 调用返回后阻止后续节点，将 session 标记为 `CANCELLED`，持久记录请求与完成事件。
- 停止接口继续经过 capability、Host、Origin 与 JSON 安全门；非运行中、纸笔组件或终态 session 不伪报成功。
- 不强杀 Python 线程、不损坏 SQLite checkpoint，不声称能撤回已经发往 DeepSeek 的单次请求。

## 2. 方案与影响面

1. `SessionManager` 增加运行中集合、线程锁、原子 stop marker、协作式 provider wrapper 和 `request_stop()`。
2. `/api/sessions/{id}/stop` 只接受正在运行的 general session；run 结束后同步 Web session 状态。
3. 首页增加默认隐藏的停止按钮；运行时显示，点击先发送 stop，再 abort 当前 fetch，并轮询 session 直到 `CANCELLED`。
4. 状态机 checkpoint 保留最后一个完整节点；停止状态由 session 目录中的原子 marker 持久化，恢复查询仍返回 `CANCELLED`。

## 3. 风险与恢复

- 当前模型请求可能仍持续到服务端响应：页面明确显示“正在终止当前请求”，随后阻止一切后续节点。
- stop/run 存在竞态：锁保护运行集合；只有真实运行中的 session 接受 stop，终态返回冲突。
- 浏览器断开不能作为服务端取消依据：AbortController 仅负责 UI，真实停止以 stop API/marker 为准。
- marker 与 checkpoint 分离：只覆盖呈现状态，不改写最后一个完整 checkpoint；新 run 检查 marker 后拒绝继续。

## 4. 验收标准

| ID | 必需 | 可观察结果 | 适用范围 |
|---|---|---|---|
| A01 | 是 | general Agent 运行时显示可点击的“终止推理”，非运行时隐藏或禁用 | Web UI |
| A02 | 是 | stop API 对运行中 session 返回 `STOP_REQUESTED`，当前调用结束后 run/status 返回 `CANCELLED` | Web/API |
| A03 | 是 | 停止后不再发生下一次 provider 调用，stop requested/cancelled 事件可回读 | SessionManager |
| A04 | 是 | 非运行中或非 general session 停止失败关闭，不影响既有数独/数织/扫雷 | 安全/兼容 |
| A05 | 是 | 全量测试、JS 语法、diff 与 HAiKnow lifecycle 通过；8017 重启加载新行为 | 全项目 |

## 5. 成稿自审记录

- 日期：2026-10-03。
- 审核者：主 agent；宿主策略不允许为此启动独立 subagent，故从文件完整重读降级自审。
- 意图与范围：覆盖玩家可见按钮、真实服务端停止、终态与审计；明确不承诺强杀在途 HTTP。
- 事实与假设：现有 run 是同步阻塞且无 stop API；provider 非流式，均由当前代码确认。
- 方案与步骤：浏览器 abort 与服务端 marker 分责；锁、原子文件和调用边界检查闭合竞态与持久化。
- 影响范围：SessionManager、Web API、首页 HTML/JS/CSS、测试和架构文档；不改 DeepSeek 协议或纸笔引擎。
- 风险与恢复：保留最后完整 checkpoint，停止标记可独立移除；不使用线程强杀。
- 验证与验收：含阻塞 provider 并发测试、API 正负例、页面控件、全量回归和实际重启。
- 授权与冻结：用户明确要求增加功能，实施授权充分；不含 commit、merge、push 或付费调用。
- Findings：`haiknow task preflight` 因同一 feature 分支有 P0009–P0011 未提交改动而 stop；已确认不切分支、不覆盖无关改动。无实施 blocker。
- 结论：成稿通过，可冻结并实施。

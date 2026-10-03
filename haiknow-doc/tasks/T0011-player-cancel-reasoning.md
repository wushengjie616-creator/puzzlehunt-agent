---
id: T0011
title: 玩家主动终止复杂 Agent 推理
status: completed
created_at: 2026-10-03
paired_plan: P0012
acceptance_contract: v1
plan_completed_at: 2026-10-03
---

# T0011 · 玩家主动终止复杂 Agent 推理

## 实际步骤

- 已确认浏览器只有同步 run fetch，服务端没有停止 API 或 cooperative cancellation。
- 已按 TDD 增加 SessionManager 停止语义、Web API、页面按钮与状态反馈。
- `stop.json` 以临时文件替换方式原子写入，provider wrapper 在每次模型调用前后检查停止状态。
- 页面先发送 stop 请求，再 abort run fetch，并轮询 session 呈现最终 `CANCELLED`。

## 与计划的偏差

- 当前 DeepSeek 适配器为非流式请求，无法安全中断已经进入 `urlopen` 的单次调用；实现遵循计划，在该调用返回后终止后续节点。

## 关键 commit

- 尚未提交；用户本轮未授权 commit、merge 或 push。

## 测试 / 验证

- RED：聚焦测试得到 1 error + 2 failures，分别证明缺 `request_stop()`、停止路由和页面按钮。
- GREEN：`tests.test_complex_session tests.test_web_api` 共 14 项通过。
- 全量：`unittest discover` 共 184 项通过；三个前端脚本 `node --check` 通过；`git diff --check` 通过。
- 并发已知向量：阻塞 provider 开始后请求 stop，释放当前调用后返回 `CANCELLED`，provider 总调用数保持 1，事件含 requested/cancelled。
- 本地部署：8017 健康检查通过；页面含默认隐藏的“终止推理”；无 capability 的 stop 请求返回 403。

## 验收逐项处置

| ID | 结果 | 证据 |
|---|---|---|
| A01 | pass | 首页 HTML 控件测试；JS 仅在 general run 时显示，结束后隐藏 |
| A02 | pass | API 路由测试 + SessionManager 阻塞 provider 并发测试 |
| A03 | pass | provider 调用数为 1，事件文件含两类停止事件 |
| A04 | pass | 纸笔 session stop 返回 409；无 capability 实服返回 403；既有回归通过 |
| A05 | pass | 184 项、JS、diff、lifecycle 与 8017 重启证据 |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 后续 todo

- 若未来 DeepSeek 支持稳定的可取消流式传输，可把“等待当前请求返回”升级成传输层即时取消；本轮不引入该协议变化。

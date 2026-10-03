---
id: T0005
title: 本地多模态谜题 Web 与普通数独组件
status: completed
created_at: 2026-10-03
updated_at: 2026-10-03
plan_completed_at: 2026-10-03
paired_plan: P0006
acceptance_contract: v1
tags: [web, puzzle, sudoku, deepseek, local-deployment]
---

# T0005 本地多模态谜题 Web 与普通数独组件

## 目标

按已批准并冻结的 P0006 实现无需登录的本地 Web 入口、DeepSeek 强制规范化管线、纸笔谜题专栏与可回放的普通数独推理解算器，并完成本地部署和验收。

## 执行边界

- 默认仅监听 `127.0.0.1`，不实施公网部署。
- 所有用户输入在进入谜题路由前必须取得服务端签发的 DeepSeek 规范化回执。
- 数独 v1 只使用确定性人类技巧：裸单与行、列、宫隐藏单；禁止搜索、枚举、回溯和猜测。
- DeepSeek 在确定性流程停滞后只提供未验证建议，不可伪装为已证明步骤。
- 真实付费 DeepSeek 冒烟请求需另行获得授权。

## 实施记录

- 2026-10-03：用户批准 P0006，选择本地部署；计划转正并冻结，创建本任务。
- 2026-10-03：按 RED→GREEN 实现可变尺寸 Sudoku spec、候选矩阵、裸单、行/列/宫隐单、固定点停滞、状态指纹和严格 trace replay；无搜索、回溯或猜数路径。
- 2026-10-03：实现 DeepSeek text/image content parts、强制 NORMALIZE_INPUT、图片 magic/MIME/大小/像素校验与重编码，以及绑定 source/envelope/canonical hash 的 HMAC 回执。
- 2026-10-03：实现 PaperPuzzleGateway、Sudoku 与 disabled roadmap catalog；STALLED 后模型建议被裁剪为 `UNVERIFIED_ADVISORY`，不能携带 assignment 或修改盘面。
- 2026-10-03：实现 FastAPI 本地服务、无构建前端、后台 normalization job 与事件轮询、可编辑确认、Sudoku trace、existing complex Agent dispatch，以及 Host/Origin/Content-Type/capability 门。
- 2026-10-03：新增 `[web]` extra、静态资源 package data 和 `puzzle-agent web` 命令；在 fresh `.venv` 安装 49 个解析依赖，服务监听 `127.0.0.1:8017`。
- 2026-10-03：修复历史 automation tests 硬编码 `python` 导致 clean macOS 失败的问题，改为当前 `sys.executable`。
- 2026-10-03：同步更新 README 和 current architecture；真实 Chrome 成功加载首页并目视确认桌面布局、上传入口及纸笔谜题卡片。

## 验证记录

- RED 证据：Sudoku/intake 模块缺失导致 2 个 import error；normalizer/gateway 缺失导致 2 个 import error；Web app 缺失导致 1 个 import error；advisory/general run 契约缺失导致 2 个 error。
- GREEN 证据：`.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q` → 148 tests，全部通过（2026-10-03 fresh run）。
- 差异卫生：`git diff --check` 通过。
- HAiKnow：`haiknow docs lifecycle --repo .` → PASS，4 个 plan-owned pair，live index stable。
- 部署：Uvicorn PID 70566 在 `http://127.0.0.1:8017` 运行；`GET /health` 返回 `{"status":"ok","mode":"local"}`。
- 浏览器：真实 Chrome 成功加载标题“Puzzle Agent · 本地解谜台”，可访问文字/图片入口、普通数独、扫雷路线图和 no-login 声明。
- DeepSeek：fake provider 覆盖文字/图片 multipart content contract、JSON/schema fail-closed 和 key 不泄漏；依批准边界未发起真实付费视觉 smoke。

## 偏差记录

- 进度传输采用有界事件轮询而不是 SSE；属于 P0006 明确允许的“或等价机制”，可刷新并按 event ID 增量读取。
- 原图不写临时文件，而是在内存完成校验、重编码与模型请求后释放；这比 TTL 文件删除更小化留存面。
- P0006 frontmatter 在转正时遗留三处错误的 `../../` 相对链接；收尾时仅修正引用路径并记录于此，未改动冻结的设计正文。

## 验收处置

- A01–A18：通过本地实现、自动化测试、fresh install、健康检查及 Chrome smoke 验收。
- A03 的真实外部模型效果与 A14 的付费图片 journey 没有冒充验证；已验证官方 content-parts 契约和完整 fake journey，真实 paid smoke 等用户另行授权。
- A19：pending。公网无登录部署不在本次授权范围内，未实施。

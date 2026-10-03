---
id: T0008
title: DeepSeek 可用性诊断与密码工具子页面
status: completed
created_at: 2026-10-03
paired_plan: P0009
acceptance_contract: v1
plan_completed_at: 2026-10-03
---

# T0008 · DeepSeek 可用性诊断与密码工具子页面

## 实际步骤

- 已确认当前 DeepSeek 不可用的直接原因是未配置 `DEEPSEEK_API_KEY`；模型与图像消息格式符合当前官方文档。
- 先写密码核心、bootstrap 状态、API 和子页面测试，观察模块缺失、字段缺失与 404 的正确 RED。
- 实现有界密码参考/转换模块、Agent Bacon/ASCII 候选、DeepSeek 安全状态和两个子页面。
- 浏览器走通首页缺 Key 提示、纸笔页扫雷、密码搜索、Caesar、ASCII 和三进制转换，并部署至 8017。

## 与计划的偏差

- `haiknow task preflight` 在成功 fetch 后仍将 remote state 报为 unknown；人工用 `git merge-base` 与 `git rev-list --left-right --count` 确认 `origin/main` 为 HEAD 祖先且结果为 `0 4`，从本地 main 建分支继续。

## 关键 commit

- 当前改动尚未提交；用户本轮未授权 commit/push/merge。

## 测试 / 验证

- RED：`python -m unittest tests.test_cipher_reference tests.test_web_api -v` → 缺模块、缺 bootstrap 字段、子页面 404。
- 第二轮 RED：`python -m unittest tests.test_ciphers -v` → 缺少 Bacon/ASCII decoder 导入。
- GREEN：聚焦 15 项测试通过。
- 全量：`python -m unittest discover -s tests -p 'test_*.py' -q` → 177 项通过。
- JavaScript：三个脚本 `node --check` 全部通过；`git diff --check` 通过。
- 独立性质检查：Bacon A–Z、可打印 ASCII、0..127 二/三/十进制交叉换算通过。
- 浏览器：8019 验收后部署 8017；可见缺 Key 指引、两个子页面、猪圈搜索、Caesar shift=3 → Hello、ASCII 72 105 33 → Hi!、三进制 2102 → 十进制 65 / ASCII A。
- 服务：`curl -fsS http://127.0.0.1:8017/health` → `{"status":"ok","mode":"local"}`。
- 文档：`haiknow docs lifecycle --repo .` → PASS（7 对 P/T）。

## 验收逐项处置

| ID | 结果 | 证据 | 适用范围 / 下一步 |
|---|---|---|---|
| A01 | pass | 无 Key bootstrap 测试 + 浏览器显示 `.env.local` 指引；响应无 secret | 本地 Web |
| A02 | pass | configured env 测试显示两模型且不回传 Key；既有 normalizer 强制链路测试通过 | 本地 Web |
| A03 | pass | reference 单测 + 浏览器搜索“猪圈”只返回猪圈密码 | 密码资料库 |
| A04 | pass | 已知向量、往返测试、Caesar 26 行和浏览器三类转换 | 密码 API/页面 |
| A05 | pass | 非法 Bacon/ASCII/Braille/radix/operation/超长输入测试均失败关闭；API 返回 422 | 密码 API |
| A06 | pass | 路由测试与浏览器分别打开 `/paper-puzzles`、`/cipher-tools` | Web 页面 |
| A07 | pass | 全量 177 项测试通过 | 全项目 |
| A08 | pass | 8017 浏览器与健康检查通过；未触发付费模型 | 本地部署 |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 后续 todo

- 若用户提供 DeepSeek Key，可另行授权一次真实付费文字/图片冒烟；本任务没有调用付费模型。
- 若用户要求发布，再单独 commit/merge/push；当前保留在 `feat/cipher-tools-and-pages` 工作树。

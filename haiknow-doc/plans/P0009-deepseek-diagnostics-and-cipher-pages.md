---
id: P0009
title: DeepSeek 可用性诊断与密码工具子页面
status: completed
created_at: 2026-10-03
paired_task: T0008
acceptance_contract: v1
plan_completed_at: 2026-10-03
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
evidence:
  - "2026-10-03: load_env_local 后 key_present=False；仓库仅存在 .env.example，不存在 .env.local"
  - "2026-10-03: DeepSeek 官方模型列表与 Vision 指南确认 deepseek-flash 支持 OpenAI Chat Completions image_url 输入"
  - "2026-10-03: git rev-list --left-right --count origin/main...HEAD 输出 0 4；当前工作区 clean"
---

# P0009 · DeepSeek 可用性诊断与密码工具子页面

<!-- 一旦执行此 plan 即冻结；偏差只写到对应 task 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景与结论

当前本地 Web 在缺少 `DEEPSEEK_API_KEY` 时仍能启动，但只有提交题目后才异步失败，页面没有在入口处解释配置状态。现场检查确认当前进程与 `.env.local` 均没有 Key；当前默认 `deepseek-flash`、`/chat/completions` 和 `image_url` 数据格式符合 DeepSeek 官方接口，因此本次故障先按“缺少本地凭据且可观测性不足”修复，不改模型协议。

现有 `cipher_workbench.py` 已覆盖 Caesar、A1Z26、Rail Fence 等部分确定性分析，但没有面向用户的可检索古典密码资料库，也没有 Web 转换页面。此次复用其确定性实现，新建单一密码参考/转换服务，避免前后端各维护一份算法真相。

## 2. 目标与非目标

目标：

- 首页在调用前显示 DeepSeek 是否已配置、使用的视觉/Agent 模型和安全的修复指引，不暴露 Key。
- 提供可检索的古典密码资料库，首批包含培根、猪圈、凯撒、栅栏和 ASCII。
- 提供独立“纸笔谜题”与“密码工具”子页面，并从全站导航到达。
- 密码工具提供 Caesar 全移位、培根、A1Z26、ASCII、二/三/十进制转换与盲文点位转换/对照表。
- 转换函数有长度、字符和数值边界；结果只作为机械转换，不宣称谜题答案。

非目标：

- 不内置密码字典暴力破解、语言模型猜 key 或无限枚举。
- 不把猪圈图片自动识别伪装成可靠文本解码；本期提供图形/位置对照资料。
- 不调用真实付费 DeepSeek API，不写入或显示用户 Key。
- 不推送、发布公网或改变仅本机访问的安全边界。

## 3. 方案与实施拆分

1. DeepSeek 状态：给默认 normalizer/provider 增加安全的配置描述，`/api/bootstrap` 返回 `configured`、模型和非敏感原因；前端入口立即渲染状态。
2. 密码核心：扩展 canonical cipher 模块，加入 Bacon、ASCII、Braille、A1Z26 编解码和 2/3/10 进制整数转换；新增只读 reference catalog 与有界搜索。
3. Web API：增加 `/api/ciphers/references` 与 `/api/ciphers/transform`；所有写请求继续走 capability、Host、Origin、JSON 安全门。
4. 页面：保留首页题目入口，新增 `/paper-puzzles` 和 `/cipher-tools`，共享导航和视觉语言；纸笔页汇总数独、数织、扫雷，密码页提供搜索、表格和交互转换。
5. 文档：同步 README、`.env.example` 和当前架构文档。

## 4. 验收标准

| ID | 必需 | 可观察结果 | 适用范围 |
|---|---|---|---|
| A01 | 是 | 未配置 Key 时 bootstrap 与首页明确显示不可用原因和 `.env.local` 修复方式，且响应不含 Key | 本地 Web |
| A02 | 是 | 已配置时状态显示视觉模型/Agent 模型，正常输入仍强制经过 DeepSeek normalizer | 本地 Web |
| A03 | 是 | 古典密码库可检索到培根、猪圈、凯撒、栅栏、ASCII，条目含用途、规则和注意事项 | 密码资料库 |
| A04 | 是 | Caesar 输出 26 个确定性移位；Bacon、A1Z26、ASCII、盲文与 2/3/10 进制有正反向或明确方向的转换 | 密码 API/页面 |
| A05 | 是 | 无效字符、越界数值、超长输入返回 4xx，不产生无界工作 | 密码 API |
| A06 | 是 | `/paper-puzzles` 与 `/cipher-tools` 可直接访问，并能从首页导航进入 | Web 页面 |
| A07 | 是 | 既有数独、数织、扫雷与通用 Agent 测试不回归 | 全项目 |
| A08 | 是 | 浏览器实测显示 DeepSeek 状态、两个子页面、参考搜索及至少三种转换结果 | 本地部署 |

## 5. 风险与恢复

- 密码传统存在多种字母表变体：API 明确返回 variant，默认 Bacon 使用 26 字母现代变体；资料卡同时说明古典 I/J、U/V 合并形式。
- 猪圈符号跨字体不稳定：用位置/围栏/点位描述和页面图例，不接受模糊 Unicode 当作自动解码输入。
- 前端多页面可能复制状态：只让密码算法驻留 Python；JS 仅做 API 调用和展示。
- DeepSeek 状态只证明“已配置”，不证明余额、网络或 Key 有效；不做付费探测，实际请求失败保留服务端错误码摘要。

## 6. 验证方式

- TDD：先写密码核心、Web API、bootstrap/页面路由的失败测试，观察正确 RED，再最小实现到 GREEN。
- 运行聚焦测试、完整 `unittest discover`、`node --check`、`git diff --check`。
- 独立字面量 oracle 检查 Bacon/A1Z26/ASCII/进制样例；浏览器走真实本地页面但不触发付费模型。
- HAiKnow changed-contract、lifecycle 与完成自审。

## 7. 成稿自审记录

- 日期：2026-10-03
- 审核者：主 agent（宿主策略禁止为此启动独立 subagent，按 workflow 降级为从文件完整重读）
- 被审版本：本文件初稿完整正文
- 意图与范围：三项用户要求均有对应目标；明确不做暴力破解、真实付费调用或公网发布。
- 事实与假设：Key 缺失由本机无敏感值探针确认；DeepSeek 协议由官方模型列表与 Vision 文档确认；Git 基线由 merge-base/rev-list 确认。
- 方案与步骤：SSOT 为 Python cipher 模块，API 与页面为消费者；DeepSeek 状态只公开非敏感元数据。
- 影响范围：覆盖 config/provider、bootstrap/API、静态路由/页面、测试、README 与架构文档；历史 completed P/T 不回写。
- 风险与恢复：变体、猪圈字体、配置状态边界均明确；新路由与模块可单独回退。
- 验证与验收：A01–A08 均为调用者可观察结果，含负例、全量回归和浏览器证据。
- 授权与冻结：用户已明确要求实施；不含 push、付费调用或公网发布。进入实施后冻结本计划。
- Findings：无 blocker。局限是未用真实 Key 验证账户余额/网络，已作为非目标与状态语义写明。
- 结论：通过，可进入实施。

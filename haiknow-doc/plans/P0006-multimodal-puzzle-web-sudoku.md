---
id: P0006
title: 无登录多模态 Puzzle Web 与普通数独纵向切片
status: completed
created_at: 2026-10-03
plan_completed_at: 2026-10-03
paired_task: T0005
acceptance_contract: v1
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - ../docs/02-agent-design-journey.md
  - ../decisions/D0001-puzzle-agent-stage1-retrospective.md
evidence:
  - "当前分支 plan/p0006-paper-pencil-components，HEAD 与 origin/main 均为 3dbc3898d8012af5049dd29fd4fa1021e35ac3f8；除本 draft 外无用户改动"
  - "README.md 与 haiknow-doc/docs/01-puzzle-agent-architecture.md：项目当前只有 CLI，既有 DeepSeek adapter 按 text-only 设计，视觉 artifact 需人工转写"
  - "src/puzzle_agent/providers/deepseek.py：当前 provider 只发送字符串 content，没有 image content part 或文件上传路径"
  - "src/puzzle_agent/complex_session.py：已有 session、artifact、interrupt/resume 和持久化基础，但 artifact 当前按文本文件保存"
  - "DeepSeek 官方 Vision 文档：https://api-docs.deepseek.com/guides/vision/；deepseek-flash 支持混合文本/图片输入及 base64、URL、Files API 三种图片来源"
  - "DeepSeek 官方 Chat Completions 文档：https://api-docs.deepseek.com/api/create-chat-completion/；user content 可为 text/image_url/file content parts"
---

# P0006 · 无登录多模态 Puzzle Web 与普通数独纵向切片

> **模式**：已批准执行。本文自 2026-10-03 起冻结；不调用未经另行授权的付费模型，也不部署公网。
>
> <!-- 一旦执行此 plan 即冻结；偏差只写到对应 task 的“与计划的偏差”章节，不回改本 plan -->

## 0. TL;DR

交付一个无需登录、默认仅监听 `127.0.0.1` 的 Puzzle Agent Web 界面。用户可以输入文字、上传图片或同时
提供两者；所有入口都先经过 DeepSeek 规范化，再把经过用户预览确认的 canonical puzzle 交给现有 Agent。

首页增加“纸笔谜题”专区。第一期只有普通数独是可用组件；扫雷及其他常见类型只显示为“待实现”，不借用
当前零散工具冒充完整解法器。数独 v1 支持结构化 9×9，并为其他尺寸保留显式 symbols/regions 契约；脚本
循环裸单和行/列/宫隐单，完整展示每一步的待选数、依据、填数和盘面。固定点仍未解完时，DeepSeek Agent
只能给出下一策略建议，不能未经 verifier 验证就填数。

DeepSeek 官方现已由 `deepseek-flash` 提供视觉输入，因此图片解析技术上可行。图片和文字都会先进入一个
独立的 `NORMALIZE_INPUT` 阶段；DeepSeek 输出不直接当真，必须通过 schema/数独约束校验并在 UI 中允许
用户修正和确认。这样避免视觉模型把一个数字看错后，确定性求解器“正确地解出错误题目”。

## 1. 范围变化与 durable owner

此前 P0006 draft 只设计纸笔谜题组件网关，尚未批准或冻结。用户现在明确扩大为：

1. 无登录 Web 前端；
2. 文字和图片上传；
3. 所有谜题输入先经 DeepSeek；
4. 图片由 DeepSeek 视觉模型解析；
5. 纸笔谜题专区；
6. 第一项可用解法器为普通数独，并展示完整过程；
7. 完成首期后列出常见纸笔谜题，逐个设计做题流程；
8. 部署可用。

这些内容构成一个新的端到端产品切片，旧 draft 不再足以作为 owner。本稿沿用尚未消耗的 P0006 编号，完整
替换旧 draft；不是修改已冻结计划。

## 2. 已确认事实、假设与待决边界

### 2.1 Confirmed

- 项目当前是 Python CLI，无 Web server、页面、上传 API 或浏览器资产。
- 当前 DeepSeek provider 只接受文本字符串；视觉接入需要扩展 provider contract。
- 当前 Agent 已有 artifact、session、checkpoint、evidence 和 blocker，可复用而不是另造第二套 Agent。
- DeepSeek 官方 `deepseek-flash` 现支持原生图像输入；官方允许 base64 data URL、外部 URL、Files API。
- 用户要求所有文字/图片入口都先经过 DeepSeek，不允许“格式看起来规整就绕过”。
- 用户要求无登录；这不等于允许客户端持有 DeepSeek key。
- 用户已给出数独 v1 的两类确定性规则：裸单和行/列/宫隐单。

### 2.2 Assumptions

- **A-DEPLOY**：未指定公网托管平台。首期“完成部署”默认指本机 Web 部署，监听 `127.0.0.1`；公网发布
  在用户指定 host、域名和费用/滥用策略后另行执行。
- **A-UPLOAD**：首期每次最多上传 1 张图片；支持 PNG/JPEG/WebP，应用层上限 10 MiB。GIF 虽被官方 API
  支持，但动画、多帧与题面选择会扩大范围，首期拒绝。
- **A-FRONTEND**：使用 FastAPI + 静态 HTML/CSS/JavaScript，不引入 Node 构建链。新增 Python Web extra
  是本范围内的必要依赖；确切兼容版本在实施时以 Python 3.11/3.12 fresh install 验证确定。
- **A-SUDOKU**：首期产品承诺只覆盖能由裸单/隐单到达终局的普通数独；更高阶技巧按后续组件迭代增加。

若用户要求直接公网无登录部署，A-DEPLOY 失效，必须先补托管目标和强制滥用防护；不能把本地安全假设
带到公网。

## 3. 用户旅程

```text
打开首页（无需登录）
  → 输入题目文字 / 上传图片 / 两者同时
  → 服务端校验并临时保存 immutable source
  → 所有输入调用 DeepSeek NORMALIZE_INPUT
  → 展示“模型识别结果”预览
      ├─ 普通题：标题、风味、正文、artifact 描述、识别置信与疑点
      └─ 数独：可编辑网格、尺寸、数字域、宫结构、逐格置信与疑点
  → 用户确认或修改 canonical input
  → 服务端签发绑定 source/canonical hash 的 normalization receipt
  → 创建 Agent session
  → 普通题进入现有 complex Agent
  → 数独进入 paper_puzzle/sudoku 组件
      → 展示逐步推理时间线
      → SOLVED 或 STALLED
  → 页面展示答案、过程、blockers 与可下载 JSON 结果
```

“无登录”只移除账号系统，不移除输入确认、费用提示、隐私提示和安全限制。

## 4. 方案选择

### 4.1 推荐：FastAPI 单体 + 无构建静态前端

一个 Python 进程同时提供 API 与静态页面：

```text
Browser
  ├─ static HTML/CSS/JS
  └─ /api/*
       ├─ Intake / upload
       ├─ DeepSeek normalization
       ├─ session / solve
       └─ SSE progress stream

Python service
  ├─ existing puzzle_agent core
  ├─ DeepSeek text + vision adapters
  ├─ paper puzzle gateway
  └─ Sudoku v1 component
```

优点：复用 Python 领域代码；没有前端构建链；本地一条命令启动；SSE 足够承载单向进度。代价是 UI 交互
由原生 JavaScript 管理，但首期页面规模有限。

### 4.2 替代：React/Vite SPA + Python API

组件生态更丰富，但引入 Node、第二套依赖和构建/部署链。当前只有上传、网格编辑、进度和过程时间线，收益
不足以覆盖复杂度，首期不采用。若后续需要大型可视化编辑器再评估。

### 4.3 替代：纯浏览器调用 DeepSeek

实现最少，但会把 API key 暴露给浏览器，任何访问者都可盗用；也无法可靠执行上传限制、费用控制和服务端
session。禁止采用。

## 5. 前端信息架构

### 5.1 首页

- 顶部：项目名称、文字/图片统一上传框、隐私与计费提示。
- 普通谜题入口：将规范化结果交给现有 Agent。
- 纸笔谜题专区：卡片式目录。
  - **普通数独**：首期可用。
  - **扫雷**：待实现，不显示“可解”。现有 `minesweeper_propagate` 只是局部确定性工具，不冒充完整组件。
  - 其他谜题：部署完成后的共同规划清单，以 disabled/roadmap 状态展示。

### 5.2 规范化确认页

- 左侧显示原始文字/图片预览及 source hash。
- 右侧显示 DeepSeek 识别出的 puzzle family、canonical text/结构、置信与未确认项。
- 数独显示可编辑 N×N 网格；修改格高亮，确认前运行结构校验。
- “确认并开始”是 canonical input 的冻结点；后续 Agent 只读该版本。
- 不允许模型输出自动越过确认页开始付费多阶段解题。

### 5.3 数独过程页

- 当前盘面与初始题面并列；givens、脚本填数、用户修正用不同样式。
- 每一步展示：序号、规则、坐标、填入值、该步之前的待选数、行/列/宫依据。
- 支持上一/下一步、自动播放、跳到最终盘面。
- 摘要显示裸单/隐单数量、未解格、剩余待选数总量和状态。
- `STALLED` 时显示当前 candidate matrix、已穷尽的规则及 DeepSeek 的下一策略建议；建议明确标为
  `UNVERIFIED_ADVISORY`，不得伪装成已执行步骤。

## 6. 所有输入先过 DeepSeek

### 6.1 独立 NORMALIZE_INPUT 阶段

在现有 `OBSERVE_CLASSIFY` 之前新增服务层入口，不直接把不完美输入塞入 Agent state：

```text
RawSubmission
  → upload safety gate
  → DeepSeekNormalizer
  → NormalizedPuzzleEnvelope
  → schema/domain validation
  → user correction/confirmation
  → immutable PuzzleInput + artifacts
```

文字输入同样调用 DeepSeek；没有“纯文本快速绕过”。测试使用 fake normalizer，不触发网络或计费。

### 6.2 模型路由

- 视觉/混合输入：`deepseek-flash`，Chat Completions 的 user content parts，图片使用 inline base64 data URL。
- 纯文本规范化：默认仍用 `deepseek-flash`，保持同一 normalization contract；后续允许配置但不能绕过阶段。
- 正式解题：继续使用项目现有 reasoning model 配置，例如 `deepseek-v4-pro`。
- 新增独立配置键，避免误把 vision model 与 reasoning model 当成同一能力：

```text
DEEPSEEK_NORMALIZER_MODEL=deepseek-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
```

API key 只保存在服务端；浏览器永远拿不到。

### 6.3 NormalizedPuzzleEnvelope

```json
{
  "source_hashes": ["sha256:..."],
  "family_candidates": [
    {"family": "sudoku", "confidence": 0.97, "evidence": ["9x9 grid", "digits 1-9"]}
  ],
  "selected_family": "sudoku|null",
  "title": "",
  "flavor_text": "",
  "content": "",
  "artifacts": [],
  "structured_payload": {},
  "uncertainties": [],
  "model": "deepseek-flash",
  "protocol_version": "normalizer-v1"
}
```

该对象是模型输出；服务端完成 schema/domain validation 后另生成不可由浏览器伪造的 normalization receipt，
绑定 raw source hash、normalized envelope hash、模型、协议和生成时点。用户修正后，confirmation 再绑定最终
canonical hash。任何创建普通 Agent 或纸笔组件 session 的后端路径都必须验证 receipt + confirmation；
不能只在前端隐藏一个“跳过 DeepSeek”的按钮。

模型必须输出 JSON；非法、截断或非对象响应不猜补。可以对明确的传输错误做一次 checkpoint-safe retry；
内容错误回到确认页，不进行隐式多次“直到看起来正确”。

### 6.4 Sudoku 视觉输出

`structured_payload` 至少包含：

```text
size / symbols / grid / regions-or-box-shape
cell_confidence
ambiguous_cells
visual_notes（粗线、额外标记、是否可能为变体）
```

若检测到对角线、笼、箭头、温度计等额外约束，不能降级成普通数独；标为 unsupported variant 并要求确认。
若存在低置信格或违反数独 givens 的冲突，禁止自动开始。

## 7. 上传、隐私与生命周期

### 7.1 上传门

- 只接受一个明确 allowlist：PNG/JPEG/WebP；校验 magic bytes，不信任扩展名或浏览器 MIME。
- 10 MiB 应用上限，像素尺寸与解压后像素数另设上限，拒绝压缩炸弹。
- 解码后重新编码为安全格式再发送给 DeepSeek；不保留 EXIF/元数据。
- 文件名不参与路径；所有临时文件使用服务端生成 ID。

### 7.2 生命周期

- 原图只在 normalization/session 需要期间存在；默认 session 结束或 TTL 到期删除。
- 持久化结果保留 source hash、canonical input、模型/协议、推理 trace，不默认保留原始图片。
- UI 明示“图片/文字将发送给 DeepSeek API”，用户确认后才上传处理。
- 日志禁止记录 base64、API key、完整图片和未经裁剪的敏感正文。

## 8. 纸笔谜题统一入口

保留原 P0006 的核心边界，但作为本纵向切片的一部分实现：

```text
paper_puzzle(
  action="inspect|reason",
  component="auto|sudoku",
  source_refs=["confirmed.structured_payload"],
  limits={"max_steps": ...}
)
```

- `PaperPuzzleRegistry` 管理组件能力与匹配；具体组件不进入 Agent 主图。
- Agent 只能引用确认后的 immutable canonical input，不能在 arguments 中重写 givens。
- 返回统一状态：`NO_MATCH / AMBIGUOUS / INVALID / STALLED / SOLVED`。
- 每次状态改变必须有可重放 `ReasoningStep`；只有 replay-verified `SOLVED` 可进入 final extraction。
- 完整 trace 持久化，但给后续 LLM 的 prompt view 只含摘要与 evidence ID，避免上下文爆炸。

## 9. Sudoku v1

### 9.1 输入模型

```text
size: N
symbols: N 个唯一整数
grid: N×N，空格为 null
regions: N 个区域，每区 N 格；或明确 box_rows × box_cols
givens_hash: 对确认后 givens/regions 的稳定摘要
```

- 标准 9×9 默认 3×3 宫。
- 其他尺寸不能仅靠 `sqrt(N)` 猜宫；必须显式给 box shape 或 regions。
- 首期只支持普通 all-different 行/列/宫数独，不支持额外约束变体。

### 9.2 小函数

每个操作是独立纯函数或受控 state transition：

```text
validate_spec
load_givens
validate_state
cells_for_row / cells_for_column / cells_for_region
candidates_for_cell
initialize_candidates
eliminate_from_peers
find_naked_singles
candidate_positions
find_hidden_singles_in_unit
scan_rows / scan_columns / scan_regions
apply_assignment
propagate_singles
summarize_stall
replay_step / replay_trace
```

行、列、宫扫描复用统一 `scan_unit(unit_cells, missing_symbols)`，不复制三套算法。

### 9.3 循环语义

```text
初始化待选数
while unsolved:
    校验无矛盾
    查找并应用裸单
    查找并应用行隐单
    查找并应用列隐单
    查找并应用宫隐单
    若本轮无 assignment → STALLED
完成后校验每行/列/宫恰含 symbols → SOLVED
```

实现可使用 dirty-unit queue：

- 已填满的行/列/宫跳过；
- 某数字已在 unit 中填入，则该 unit 的该数字隐单扫描跳过；
- assignment 后只把受影响的行、列、宫重新标 dirty；
- 优化不能改变确定性顺序、trace 或结果；先用全扫描 reference 实现验证等价，再启用队列。

### 9.4 推理步骤

```json
{
  "index": 2,
  "technique": "hidden_single_row",
  "target": "R1C9",
  "value": 6,
  "premises": {
    "unit": "R1",
    "missing_symbol": 6,
    "candidate_positions": ["R1C9"],
    "target_candidates_before": [1, 5, 6, 7]
  },
  "before_fingerprint": "...",
  "after_fingerprint": "..."
}
```

verifier 从 canonical givens 重放所有步骤；改写 given、无前提填数、候选不一致、fingerprint 不连续或终局
约束未满足都必须失败。

### 9.5 Agent 接管

当 singles 固定点停滞：

1. 脚本输出 candidate matrix、未解 unit、已用技巧和最后状态 hash。
2. DeepSeek Agent 分析“下一种人类技巧可能是什么”，形成建议与证据引用。
3. v1 中没有对应 deterministic verifier 的建议仅显示为 `UNVERIFIED_ADVISORY`，不得修改盘面。
4. 后续新增 locked candidates、pairs/triples 等规则时，先实现函数与 verifier，再允许 Agent 调用并应用。

这保留“Agent 开始思考”的产品体验，同时不让自由文本推理偷偷变成猜数。

## 10. Web API 与运行时

建议路由：

```text
POST /api/intake                  文字/图片上传，创建 normalization job
GET  /api/jobs/{id}/events       SSE：上传、DeepSeek、校验进度
GET  /api/intakes/{id}           读取 normalization 结果
POST /api/intakes/{id}/confirm   提交用户修正并冻结 canonical input
POST /api/sessions               创建普通/纸笔 Agent session
POST /api/sessions/{id}/run      运行或继续
GET  /api/sessions/{id}          当前状态和摘要
GET  /api/sessions/{id}/trace    有界推理步骤
```

- API 使用随机 opaque ID，不使用用户文件名。
- 无账号、无长期身份 cookie；本地模式可以使用内存/临时目录 job store。
- session 创建必须持有服务端签发且匹配当前 canonical hash 的 normalization receipt/confirmation，直接构造
  API 请求不能绕过 DeepSeek 阶段。
- DeepSeek 与求解在后台 task 中执行，浏览器断开不破坏状态；SSE 重连可按 event ID 续读。
- 刷新页面可用 session ID 恢复当前结果，但不承诺跨 TTL 永久保存。

## 11. 部署与安全边界

### 11.1 本计划默认交付

- `puzzle-agent web --host 127.0.0.1 --port <port>` 或等价入口。
- 健康检查、优雅停止、临时目录清理、服务端 key 配置和本地浏览器 smoke。
- 每次启动生成随机 local capability/CSRF token，注入同源页面并要求所有付费/写操作携带；严格检查 Host、
  Origin 与 Content-Type，不开启宽泛 CORS。该 token 是本机进程防伪，不是用户账号或登录。
- 不自动打开防火墙、不监听 `0.0.0.0`、不创建公网域名。

### 11.2 公网无登录模式

公网没有登录并不代表可以没有访问控制。实际发布前至少需要：

- TLS 与反向代理；
- IP/设备级 rate limit 和并发上限；
- 每请求上传、模型 token、求解步数与 wall-clock 限额；
- 每日费用预算/熔断；
- bot challenge（可不使用账号登录）；
- ephemeral storage、隐私声明和删除策略；
- host-specific 日志与 secret 配置。

未指定托管平台时，这些只能设计和测试接口，不能诚实声称公网部署完成。

## 12. Contract impact map

### 12.1 Canonical contracts

| 契约 | SSOT |
|---|---|
| 原始提交 → canonical puzzle | 新 `intake/contracts.py` |
| DeepSeek text/image transport | `providers/deepseek.py` 或拆分后的 provider contracts |
| Web API | 新 `web/api.py` + request/response schemas |
| 纸笔组件 | 新 `paper_puzzle/contracts.py` |
| Sudoku state/trace | 新 `paper_puzzle/components/sudoku/contracts.py` |

### 12.2 计划新增

```text
src/puzzle_agent/
  intake/
    contracts.py
    normalizer.py
    uploads.py
  paper_puzzle/
    contracts.py
    registry.py
    gateway.py
    replay.py
    components/sudoku/
      contracts.py
      grid.py
      candidates.py
      singles.py
      solver.py
      replay.py
  web/
    app.py
    api.py
    jobs.py
    static/index.html
    static/app.js
    static/styles.css

tests/
  test_intake_normalizer.py
  test_upload_safety.py
  test_paper_puzzle_gateway.py
  test_sudoku_*.py
  test_web_api.py
  test_web_journey.py
```

### 12.3 现有文件影响

| 文件 | 影响 |
|---|---|
| `pyproject.toml` | 新增 `[web]` extra 与 Web CLI entry/support |
| `providers/deepseek.py` | 支持 content parts 或拆分通用 transport；保持旧文本调用兼容 |
| `complex_domain.py` | canonical source refs、component runs 摘要 |
| `complex_graph.py` | paper_puzzle 目录签名、dispatch、evidence prompt view |
| `complex_session.py` | confirmed intake 与 bounded binary artifact 生命周期 |
| `cli.py` | `web` 入口，不改变现有 CLI 默认行为 |
| `README.md` | Web 用法、视觉能力、隐私/计费、Sudoku v1 限制 |
| `docs/01-puzzle-agent-architecture.md` | 实施完成后更新 current architecture，纠正旧 text-only 声明 |

P0001–P0005、T0001–T0004 和 D0001 作为历史证据不回写。

## 13. 实施拆分

### M1 · DeepSeek normalization 与上传门

- 先写 text/image content-part provider RED tests。
- 建 RawSubmission/NormalizedPuzzleEnvelope、fake normalizer 和 schema gate。
- 实现安全上传、图片重编码、source hash、临时生命周期。
- 用官方允许格式的最小 fixture 验证；真实 DeepSeek smoke 仍需明确付费调用授权。

### M2 · Paper gateway 与 Sudoku v1

- 建统一组件 contract/registry/gateway/replay。
- 以 TDD 实现可变尺寸 grid、regions、候选矩阵、裸单、隐单、固定点循环和 trace verifier。
- 使用至少三类题：可全解、会停滞、输入矛盾；禁止任何 search/backtracking dependency。

### M3 · Web API 与前端

- 建 FastAPI app、静态页面、job/session API 和 SSE。
- 完成文字/图片 → DeepSeek → 预览编辑 → 确认 → Sudoku → 逐步展示的真实浏览器 journey。
- 普通谜题路径复用现有 Agent，不能只做 Sudoku 专用孤岛。

### M4 · 本地部署与文档

- fresh install `[web]`，启动本地服务，验证健康检查、上传、刷新恢复和退出清理。
- 更新 README/current architecture，不声称未验证的公网能力或高阶 Sudoku 技巧。
- 完成用户验收后，输出常见纸笔谜题候选目录与建议实现顺序，和用户共同选择下一组件。

## 14. 验证策略

### 14.1 DeepSeek 与输入保真

- 文本和图片路径都断言调用 normalizer；绕过调用的 mutation 必须失败。
- 伪造、过期、source hash 不匹配或 canonical 修正后未更新的 receipt 必须阻止 session 创建。
- multipart 请求必须包含正确 user image content part；key/base64 不进入日志、事件和浏览器响应。
- 非法 JSON、截断、超限、错误 MIME、magic mismatch、超像素和变体数独 fail closed。
- DeepSeek 误读一个 given 的 fixture 必须在确认/数独校验阶段被发现或允许用户修正，不能静默求解。

### 14.2 Sudoku

- 每个小函数有 known vector 与无效输入测试。
- 示例题产生确定性完整 trace：包含裸单和隐单，最终盘面满足所有 unit。
- 每一步从上一 fingerprint 重放；移除 premise/改 target/改 value 必须 RED。
- 需要更高阶技巧的题返回 STALLED，不试数、不回溯、不生成 final answer。
- 不同尺寸使用显式 region fixture；非法 region partition 被拒绝。

### 14.3 Web

- API contract、上传限额、job 状态机、SSE 重连、session 恢复与错误显示。
- 浏览器 journey：输入文字；上传数独图片；编辑误识别格；确认；查看逐步过程；看到 SOLVED/STALLED。
- 页面在窄屏/宽屏均可用，键盘可编辑网格，过程状态不只靠颜色表达。
- 无网络测试使用 fake DeepSeek；真实视觉 smoke 单独标记 opt-in，不能混入默认 suite。

### 14.4 回归

- 现有 simple/complex CLI、ToolRegistry、benchmark 和 oracle isolation 保持 fresh GREEN。
- 修复当前已知的 clean macOS 测试入口可移植性问题后，才能把 Web fresh matrix 宣称为 GREEN；不把历史
  128/128 记录代替当前验证。

## 15. 验收标准

- **A01（必需，Web）**：用户无需登录即可在本地浏览器打开页面，输入文字或选择一张支持格式图片。
- **A02（必需，统一入口）**：文字、图片、混合输入都必须调用 DeepSeek NORMALIZE_INPUT；session 创建要求绑定 source/canonical hash 的服务端 receipt，机械测试能阻止前端或直接 API 绕过。
- **A03（必需，视觉）**：图片通过 `deepseek-flash` 官方 image content contract 发送，API key 永不进入浏览器或日志。
- **A04（必需，确认）**：DeepSeek 结果先进入可编辑预览；未确认、低置信冲突或 unsupported variant 不得启动求解。
- **A05（必需，普通题兼容）**：非纸笔题的 confirmed canonical input 能进入现有 complex Agent，而非只能处理 Sudoku。
- **A06（必需，专区）**：首页有纸笔谜题专区；Sudoku 标为可用，扫雷等未实现项明确 disabled/roadmap。
- **A07（必需，Sudoku 输入）**：标准 9×9 可直接使用；其他 N 必须显式提供合法 symbols/regions，不猜宫结构。
- **A08（必需，基础推理）**：Sudoku v1 脚本实现裸单、行隐单、列隐单、宫隐单并循环到 SOLVED/STALLED。
- **A09（必需，过程）**：每一步显示 technique、坐标、值、待选数和 unit premise，并能从 givens 完整重放。
- **A10（必需，非枚举）**：需要未支持技巧的题稳定 STALLED；代码/依赖审计和 mutation test 证明没有回溯、试数或枚举路径。
- **A11（必需，Agent 接管）**：STALLED 后 DeepSeek 可给下一策略建议，但无 verifier 的建议不能改变盘面或产生 final answer。
- **A12（必需，安全上传）**：格式、magic、大小、像素和路径边界受测；原图按 TTL 删除且默认不进入长期结果。
- **A13（必需，进度）**：DeepSeek/求解过程通过 SSE 或等价机制可见；刷新后可用 opaque session ID 恢复 TTL 内状态。
- **A14（必需，本地部署）**：fresh environment 能以文档命令监听 `127.0.0.1`，完成真实浏览器 smoke 并优雅停止。
- **A15（必需，本地调用安全）**：跨站表单、错误 Host/Origin、缺失或错误 local capability token 不能触发上传、DeepSeek 调用或求解；不引入账号登录。
- **A16（必需，回归）**：现有 CLI/Agent/benchmark fresh tests 通过；Web extra 不破坏 base 零依赖安装。
- **A17（必需，诚实声明）**：README 区分本地部署与公网部署、基础 Sudoku 与高阶技巧、fake 测试与真实 DeepSeek 证据。
- **A18（后续交付）**：本纵向切片完成后给用户一份常见纸笔谜题候选表，按输入难度、规则复杂度、可验证性和建议顺序共同选下一项。
- **A19（待用户决定，公网）**：只有用户指定 host 与滥用/费用策略后，才可把公网无登录部署从 pending 转为 pass。

## 16. 风险与恢复

| 风险 | 控制 |
|---|---|
| 视觉模型误读数字 | 逐格置信、约束校验、可编辑预览、用户确认 |
| “所有输入过模型”增加费用/延迟 | 独立 normalizer 模型、单次调用、SSE、明确计费提示；不暗中重试内容错误 |
| 无登录公网被刷 API | 默认 localhost；公网必须 rate limit、预算熔断、bot challenge |
| 图片包含隐私数据 | 明示第三方传输、去元数据、TTL 删除、日志脱敏 |
| Web 扩大攻击面 | 严格 allowlist/limits、随机 ID、同源 API、不信任 MIME/文件名 |
| 恶意网页调用 localhost 消耗 API | loopback bind、Host/Origin 检查、每次启动的 capability/CSRF token、禁宽泛 CORS |
| Sudoku 视觉变体被错当普通题 | extra-constraint 检测与 unsupported gate |
| Agent 在 STALLED 后猜数 | advisory 与 executable deduction 分离；verifier 是唯一写盘入口 |
| 长 trace 挤爆 prompt | 完整 trace 持久化，LLM 只看有界摘要/evidence ref |
| 新依赖破坏 base 模式 | `[web]` optional extra；base import/test 不加载 Web 包 |

回退顺序：停 Web 入口 → 禁用 vision normalizer → 禁用 Sudoku registry 项。现有 CLI 与历史 session 数据保持
可读；不删除用户历史证据。若视觉 API contract 漂移，图片入口 fail closed，文字 CLI 不受影响。

## 17. 完成后的纸笔谜题共创

部署与 Sudoku v1 验收完成后，另交付候选表；每项至少列：

- 题型与常见变体；
- 输入载体（纯文字、规则网格、图片、颜色、连线等）；
- 最小状态模型；
- 人类基础技巧和停滞点；
- 是否容易构造逐步 verifier；
- 图像解析难度；
- 推荐实现顺序。

该清单用于和用户共同选择，不在本 plan 里提前承诺实现所有题型。

## 18. 授权与冻结边界

- 用户已明确要求产品方向和最终部署，但此前 P0006 尚未批准；本稿先完成 architectural review object。
- 用户批准本稿后才 promote P0006、建立配对 T，并开始 M1–M4。
- 本地实施授权不自动包含真实付费 DeepSeek smoke；执行到该门时需确认允许计费调用。
- 本地实施授权不自动包含公网发布、域名、云资源购买、push、PR 或 merge。
- 若用户没有另选部署目标，实施按 A-DEPLOY 完成本机 `127.0.0.1` 部署，不对公网暴露。

## 19. 成稿自审记录

- 日期：2026-10-03。
- 审核者：Codex 主 agent；当前策略不允许在用户未要求时启动 subagent，因此为作者完整重读，不是独立
  fresh-context review。
- 被审版本：本文件 §0–§18；正文 SHA-256 见下方最终复核记录。
- 意图与范围：通过。覆盖无登录 Web、统一 DeepSeek intake、图片理解、纸笔专区、Sudoku v1、过程展示、
  本地部署和部署后题型共创；没有擅自承诺全部纸笔谜题或公网发布。
- 事实与假设：通过。仓库 text-only 基线来自现有代码/文档；DeepSeek vision 能力来自 2026-10-03 查阅的
  官方 Vision/Chat Completions 文档。localhost、单图、FastAPI 与基础 Sudoku 覆盖均显式标 assumption。
- 方案与步骤：首轮发现 blocker——“所有输入过 DeepSeek”只有流程描述，直接 API 可绕过；已增加绑定
  source/canonical hash 的服务端 normalization receipt/confirmation，并加入 API、测试与 A02。
- 安全与恢复：首轮发现 blocker——localhost 无登录写 API 仍可能被恶意网页跨站触发并消耗付费 key；已加入
  loopback、Host/Origin、Content-Type、每次启动 capability/CSRF token、禁宽泛 CORS 与 A15。上传、隐私、
  费用、公网 abuse、变体误判、STALLED 猜数和回退路径均有边界。
- 影响范围：通过。provider、domain/graph/session/CLI、Web、intake、paper gateway、Sudoku、测试、README 与
  current architecture 均列入；历史 P/T/D 不回写。
- 验证与验收：通过。A01–A19 覆盖纵向旅程和负例；fake DeepSeek 不冒充真实视觉证据，公网 A19 明确
  等待目标和授权，不阻塞本地切片完成。
- 授权与冻结：通过。当前仅是 draft；真实计费 smoke、公网、云资源、push/PR/merge 不由本计划批准自动获得。
- 完整 findings：2 个 blocker，均在冻结前整改；无剩余 blocker。非阻断局限：审核不是独立 reviewer；
  FastAPI/依赖确切版本和公网 host 尚未知，分别由 fresh install gate 与 A19 承接。
- 最终复核：修订后完整重读通过；验收 ID A01–A19 连续且唯一；§0–§18 SHA-256 =
  `17aea1c449398591b823c55d5c3d12a09b428b52250f071deb4d32dba97983b4`；related_docs 3/3 存在。
- 最终结论：成稿自审通过，可交用户 review；尚未批准、未冻结、不得实施。

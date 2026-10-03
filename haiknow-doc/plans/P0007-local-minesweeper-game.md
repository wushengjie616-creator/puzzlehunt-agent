---
id: P0007
title: 本地交互式扫雷小游戏
status: completed
created_at: 2026-10-03
plan_completed_at: 2026-10-03
paired_task: T0006
acceptance_contract: v1
related_docs:
  - ../docs/01-puzzle-agent-architecture.md
  - P0006
evidence:
  - "2026-10-03 fresh preflight：branch plan/p0006-paper-pencil-components，HEAD b17a1d2255accbabacaeff7274eea3a9a5ecca07，origin/main behind=0、ahead=1、worktree clean，decision=use-current/fresh-feature"
  - "src/puzzle_agent/web/app.py 与 static/* 已提供本地 no-login FastAPI 页面、capability/Host/Origin 写门和纸笔谜题卡片"
  - "src/puzzle_agent/tool_registry.py:minesweeper_propagate 已有确定性八邻域推理，但只接受静态字符网格，不管理游戏生命周期"
  - "tests 使用 unittest；P0006 fresh 回归为 148/148 GREEN"
---

# P0007 · 本地交互式扫雷小游戏

<!-- 一旦执行此 plan 即冻结；偏差只写到 T0006 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景与意图

用户明确指出扫雷是互动式游戏，不应复制数独的“提交题面后自动求解”产品形态。本计划在已有本地 Web 的
纸笔谜题专区中加入一款真正可玩的扫雷，同时保留 Puzzle Agent 的特点：提示是可验证的局面分析，不自动
代玩、不暗看雷位、不把概率猜测包装成必然结论。

用户已直接要求实现，并在 preflight 阻塞后授权先提交 P0006 再继续，因此本计划走 skip-review；本地代码、
测试、文档和本地服务重启在授权内，push、公网部署和付费模型调用不在授权内。

## 2. 目标与非目标

### 目标

- 首页扫雷卡片变为可点击的“本地小游戏”。
- 支持初级 9×9/10 雷、中级 16×16/40 雷、高级 16×30/99 雷。
- 首次翻格安全，随后随机布雷；数字、空白连锁展开、插旗、胜负、计时、剩余雷数和重开符合常见扫雷语义。
- 服务端保存权威雷盘，未结束时 API 不泄漏隐藏雷位；页面刷新可凭 game ID 恢复当前局面。
- “逻辑提示”复用确定性约束思想，只返回当前可证明安全或必为雷的一格及依据，不改变棋盘；无结论时明确
  返回 `STALLED`，不猜概率。

### 非目标

- 不把用户上传的扫雷截图转成可玩盘面；上传谜题仍走 DeepSeek NORMALIZE_INPUT，游戏入口不属于外部题面。
- 不实现账号、排行榜、云存档、多人模式、自定义尺寸、动画皮肤或概率提示。
- 不调用 DeepSeek；本地小游戏和确定性提示均零模型费用。
- 不删除既有 `minesweeper_propagate` 工具，也不把游戏内部真实雷位暴露给该工具或浏览器。

## 3. 方案与契约

### 3.1 服务端权威状态机

新增 `paper_puzzle/components/minesweeper/game.py`：

```text
READY --reveal(first)--> PLAYING --reveal/chord--> WON
                               └--reveal mine--> LOST
READY/PLAYING/WON/LOST --new game--> READY
```

游戏对象保存 rows、columns、mine_count、状态、已揭格、旗子、首次操作时间和结束时间。雷位只存在服务端。
首次 reveal 时从除点击格外的坐标中均匀抽样；测试可注入 seed，HTTP API 不接受 seed。

纯/受控小操作分解为：`neighbors`、`place_mines`、`adjacent_count`、`reveal_cell`、`flood_reveal`、
`toggle_flag`、`chord_cell`、`check_win`、`public_state`、`logical_hint`。越界、终局后操作、对已揭格插旗、
旗子超上限等都显式拒绝或返回稳定 no-op，不隐式重置。

### 3.2 HTTP API

```text
POST /api/minesweeper/games                 {difficulty}
GET  /api/minesweeper/games/{game_id}
POST /api/minesweeper/games/{game_id}/actions  {action,row,column}
POST /api/minesweeper/games/{game_id}/hint     {}
```

写路由继承 P0006 的 capability、Host、Origin 和 JSON 门。ID 为随机 opaque value，store 仅在当前进程内，
不承诺重启恢复。公开 cell 只含 `covered|flagged|revealed|exploded` 与已揭数字；终局可额外使用 `mine`
展示真实雷位。`READY/PLAYING` 绝不返回 `mine`、雷位集合或 seed。

### 3.3 浏览器交互

- 扫雷卡片打开独立游戏 panel，不经过上传/DeepSeek 表单。
- 左键翻格、右键插旗并阻止浏览器菜单；双击已揭数字执行 chord。
- 工具栏显示难度、状态、剩余雷数、计时、重开和逻辑提示。
- game ID 存 `sessionStorage`，刷新时 GET 恢复；进程重启或 ID 失效则创建新局。
- 按钮有可访问名称，格子可用键盘聚焦；Enter 翻格、Space 插旗；状态不只靠颜色表达，窄屏允许棋盘横向滚动。

### 3.4 提示边界

提示只能消费与玩家相同的公开局面：已揭数字和所有未揭格；玩家旗子不当作真雷，以避免错误旗子污染证明。
复用或抽取当前 `minesweeper_propagate` 的确定性规则：若某数字周围已证明雷数等于 clue，则其他未知格安全；
若剩余雷数等于未知格数，则这些格必为雷。返回一个按行列稳定排序的结论、来源 clue 和解释。没有结论即
`STALLED`。提示不调用 reveal/flag，不改变计时或状态。

## 4. Contract impact map

| 维度 | 影响 |
|---|---|
| canonical SSOT | 新 `components/minesweeper/game.py` 定义游戏状态；既有 `minesweeper_propagate` 继续作为静态工具 |
| active consumers | `web/app.py`、`static/index.html`、`static/app.js`、`static/styles.css`、PaperPuzzleGateway catalog |
| templates/generators | 无生成器；`pyproject.toml` 已递归打包 Python，静态资源通配已覆盖现有扩展名 |
| mechanical checks | 新 engine/API 测试；现有 Web 安全、ToolRegistry、Sudoku 和全量 suite 回归 |
| historical snapshots | P0006/T0005 已完成并冻结，不回写；当前架构与 README 同步新游戏入口 |
| search terms | `minesweeper|扫雷|roadmap|disabled|puzzle-card|paper_puzzle` 全仓检查旧声明 |

## 5. 实施拆分

1. RED：游戏引擎测试覆盖首击安全、邻雷数、零区展开、旗子、踩雷、胜利、终局禁写和提示不变盘。
2. GREEN：实现独立 minesweeper game engine 与内存 store。
3. RED/GREEN：加入受本地安全门保护的 API contract 与刷新恢复测试。
4. 前端：启用卡片、游戏 panel、鼠标/键盘动作、计时和响应式棋盘；不改变上传/数独 journey。
5. 同步 README/current architecture，运行聚焦/全量测试、diff 检查、本地服务与真实浏览器 smoke。

## 6. 风险与恢复

- **隐藏雷泄漏**：API 测试递归检查 PLAYING 响应不含 mines/seed/答案；故意泄漏应使测试 RED。
- **首击后才布雷的恢复问题**：READY 状态不含 mines；首次 reveal 原子化布雷并翻格，store 由锁保护。
- **错误旗子导致危险提示**：提示忽略旗子的真实性，只基于公开 clue 推导；结果不执行动作。
- **大棋盘移动端难用**：固定格宽并允许横向滚动，不压缩到无法点击。
- **进程内存增长**：本地单用户 store 限制最多 64 局，创建新局时淘汰最旧终局/最旧记录。
- **恢复**：前端卡片可重新降级为路线图，API/engine 为隔离新增模块；不需迁移持久数据。

## 7. 验证策略

- Engine 使用固定 seed 和手算小盘作独立 oracle；断言真实公开 state，而非私有 helper 调用。
- mutation probe：去掉首击排除、把零区展开改成单格、在 PLAYING 响应加入 mine 坐标、让 hint 自动 reveal，
  至少各有一项测试会失败。
- API 使用 FastAPI TestClient 走真实 middleware；验证缺 token、跨 Origin、未知 ID、越界 action。
- 浏览器 smoke 验证开始游戏、翻格、插旗、重开、切难度、提示与窄屏滚动；不触发 DeepSeek。
- 回归运行全部 unittest，既有 148 项不得退化。

## 8. 验收标准

- **A01（必需，入口）**：纸笔谜题专区的扫雷卡片标为可用并能打开本地游戏，不进入 DeepSeek 上传流程。
- **A02（必需，规则）**：三档难度的尺寸与雷数正确，首次 reveal 永不踩雷。
- **A03（必需，交互）**：左键 reveal、右键 flag、双击 chord、重开和难度切换可用。
- **A04（必需，展开）**：零邻雷区域及其数字边界自动展开，普通数字只翻自身。
- **A05（必需，终局）**：踩雷进入 LOST 并展示雷；所有非雷格揭开进入 WON；终局后不能继续改盘。
- **A06（必需，信息）**：状态、计时、剩余雷数和旗子数量实时显示，胜负不只靠颜色表达。
- **A07（必需，保密）**：READY/PLAYING 响应不含隐藏雷位、seed 或可反推出完整答案的字段。
- **A08（必需，提示）**：逻辑提示只消费公开局面，返回确定性安全/雷结论或 STALLED，且不改变游戏状态。
- **A09（必需，恢复）**：刷新页面能凭 game ID 恢复进程内尚存局面；未知/过期 ID 能安全新建。
- **A10（必需，安全）**：所有写 API 继续受 capability、Host、Origin 与 JSON 门保护，非法动作 fail closed。
- **A11（必需，无模型）**：游戏与提示不调用 DeepSeek，不产生模型费用；上传题面路径的强制 normalization 不变。
- **A12（必需，可用性）**：桌面和窄屏均可操作；高级盘横向滚动，格子有键盘焦点和可访问名称。
- **A13（必需，回归）**：新增聚焦测试和既有全量 suite fresh GREEN，base 零依赖与 Web extra 契约不退化。
- **A14（必需，文档）**：README/current architecture 将扫雷从路线图更新为本地游戏，并诚实声明进程内存档边界。

## 9. 授权与冻结边界

授权覆盖本地实现、测试、文档、提交前自审和本地服务重启。未授权 push、PR/merge、公网部署、付费调用或
删除用户数据。本文进入执行后冻结；实现偏差、验收证据和后续候选只写 T0006。

## 10. 成稿自审记录

- 日期：2026-10-03。
- 审核者与上下文：主 agent 从文件完整重读；宿主规则禁止未获用户要求的 subagent，因此未冒充独立审核。
- 被审版本：排除本节的正文 SHA-256 `a222ed31b32d8f1073a9d7ca6f63887a43670c174f5c7e7f4a22e74882e9adc0`。
- 意图与范围：把扫雷从求解器路线图改为本地互动游戏；DeepSeek、截图导入、云存档和概率猜测边界明确。
- 事实与假设：fresh preflight、现有 Web 与静态工具均有文件/命令证据；没有依赖未验证外部 API 的前提。
- 方案与步骤：服务端权威状态、动作 API、浏览器事件和确定性 hint 的责任闭合，TDD 顺序明确。
- 影响范围：canonical、active consumers、静态资源、测试、历史边界和 repo-wide search terms 已列全。
- 风险与恢复：首击安全、隐藏雷泄漏、错误旗子、内存增长、移动端与回退均有控制和负例。
- 验证与验收：A01–A14 可观察；engine/API/browser/docs 分层，mock 未冒充真实浏览器证据。
- Findings：首轮发现终局公开 cell 枚举未包含 `mine`、键盘语义不够精确；已补 `mine` 仅终局可见及 Enter/Space 契约，重读未发现新 blocker。
- 最终结论：通过，可按用户已有本地实施授权冻结执行。局限是作者自审；不构成 push、merge 或公网授权。

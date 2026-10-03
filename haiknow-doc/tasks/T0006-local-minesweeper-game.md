---
id: T0006
title: 本地交互式扫雷小游戏
status: completed
created_at: 2026-10-03
paired_plan: P0007
acceptance_contract: v1
related_commits: []
---

# T0006 · 本地交互式扫雷小游戏

## 范围结论

按已冻结 P0007 实现本地互动扫雷；本任务不包含 push、公网部署、付费模型、排行榜或截图导入。

## 实际步骤

- 2026-10-03：P0006/T0005 及数独 Web 基线以 `b17a1d2` 提交；fresh preflight 返回 `use-current/fresh-feature`。
- 2026-10-03：P0007 以 skip-review 入口完成两轮完整重读和成稿自审，进入执行。
- 2026-10-03：按 TDD 先建立可导入但无行为的 engine/store scaffolding；7 项 engine 测试如预期 RED（7 failures），随后实现服务端权威状态机、首击后布雷、零区展开、旗子、chord、胜负、计时、公开 state、确定性提示与 64 局有界 store，聚焦测试 7/7 GREEN。
- 2026-10-03：API journey 先因 404/catalog disabled RED；随后加入 create/get/action/hint 路由并复用既有本地写门。刷新恢复测试又因缺 `difficulty` RED，补齐响应字段和前端难度同步后 GREEN。
- 2026-10-03：启用扫雷卡片和独立游戏 panel，加入三档难度、鼠标/键盘交互、客户端计时、sessionStorage 恢复和横向滚动；同步 README 与 current architecture。
- 2026-10-03：真实 Chrome 验证初级局首击安全与零区展开、右键插旗（剩余雷 10→9）、逻辑提示（`R1C5 必为雷` 且不改盘）、刷新续局和计时。视觉检查发现初级盘容器过宽，修正为 `fit-content` 后复验通过。

## 与计划的偏差

无范围或架构偏差。内部方法名采用 Python 风格 `reveal` / `chord` 而非计划中的描述性名字；公开契约不变。

## 关键 commit

基线 commit 为 `b17a1d2255accbabacaeff7274eea3a9a5ecca07`。本轮扫雷改动尚未提交；不默认获得 commit/push 授权。

## 测试 / 验证

- RED：`.venv/bin/python -m unittest tests.test_minesweeper_game -v` → 7 failures（行为尚未实现）。
- GREEN：engine 7/7；engine + Web API + gateway + Web 回归 17/17。
- 全量：`.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q` → 158/158 GREEN。
- 静态：`node --check src/puzzle_agent/web/static/app.js`、`git diff --check` GREEN。
- 浏览器：Chrome 真实页面完成打开、首次 reveal、右键 flag、hint、刷新恢复和布局复验；未调用 DeepSeek。

## 验收逐项处置

- A01–A03：卡片可玩；三档参数、首击安全、鼠标动作、重开和切换由 engine/API/前端契约覆盖，真实浏览器验证入口、reveal、flag。
- A04–A06：固定 seed 小盘证明零区边界与胜负；终局禁写、计时、状态和剩余雷由测试与浏览器状态条覆盖。
- A07–A08：PLAYING 响应递归检查无 mine/seed；hint 使用公开 clue、稳定排序且前后 state 相同。
- A09–A11：GET + sessionStorage 真实刷新续局；未知 ID/非法动作/缺 capability/跨 Origin fail closed；fake normalizer 断言调用数始终为 0。
- A12：每格具中文可访问名称与键盘处理，CSS 在窄屏保留固定格宽及横向滚动；Chrome 桌面视觉复验通过。
- A13：新增 10 项，项目全量 158/158 fresh GREEN。
- A14：README 与 `docs/01-puzzle-agent-architecture.md` 已同步进程内存档、无模型与提示边界。

## 后续 todo

- 可另立任务增加可选皮肤、排行榜、持久存档或截图转盘；本轮不预埋这些范围。

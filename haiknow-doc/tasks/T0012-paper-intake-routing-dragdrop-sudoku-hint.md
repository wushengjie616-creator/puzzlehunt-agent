---
id: T0012
title: 纸笔入口路由、图片拖拽与数独单步提示
status: completed
created_at: 2026-10-03
paired_plan: P0013
acceptance_contract: v1
plan_completed_at: 2026-10-03
---

# T0012 · 纸笔入口路由、图片拖拽与数独单步提示

## 实际步骤

- 已定位纸笔链接 query 未被首页消费、后端无 preferred kind、数独 max_steps 无独立状态和观察说明。
- 已按 TDD 让 `preferred_kind` 贯穿 Web API、DeepSeek prompt 与输出一致性校验；非法或不匹配题型失败关闭。
- 已增加 auto/general/sudoku/nonogram 选择器，纸笔页 query 自动预选；数独选择后显示单步/完整模式。
- 已实现拖拽图片区，复用既有文件读取与服务端图片安全门。
- 已让数独单步模式在首个确定赋值后返回 `STEP_LIMIT`，附带可重放校验的中文观察说明并高亮目标格。
- 浏览器验收发现拖拽监听器漏传事件名导致启动脚本中断；已修正并增加静态回归断言。
- 后续截图回归暴露 OCR 重复 clue 在确认页之前被严格校验拦截；现将数独校验拆为“识别阶段结构校验”和
  “确认阶段严格语义校验”，重复/候选冲突可进入编辑棋盘并提示，行列宫冲突格会随编辑即时标红或消除。

## 与计划的偏差

- 实施内容未偏离计划；额外修复了浏览器验收发现的 `addEventListener` 参数缺失，并将实机控制台作为验证证据。

## 关键 commit

- 尚未提交；用户本轮未授权 commit、merge 或 push。

## 测试 / 验证

- RED：聚焦测试出现 2 errors + 3 failures，分别证明缺 preferred kind、单步状态/说明和 Web solve mode。
- GREEN：normalizer、Sudoku、gateway、Web API 聚焦测试共 25 项通过。
- 浏览器缺陷回归：控制台曾报告 `addEventListener` 缺第二参数；修复后控制台 0 error，页面显示 DeepSeek 已配置、普通数独已预选、只提示下一步已选中。
- 全量：`unittest discover` 共 188 项通过；三个前端脚本 `node --check` 通过；`git diff --check` 通过。
- OCR 冲突回归：新增识别阶段容错/严格确认边界、Web 422 和冲突 UI 静态契约测试；当前全量 192 项通过，
  三个前端脚本语法检查与 `git diff --check` 通过。
- 本地部署：`127.0.0.1:8017/health` 返回 ok；从 `/paper-puzzles` 点击“提交数独”实机落到 `/?kind=sudoku` 并显示正确控件。

## 验收逐项处置

| ID | 结果 | 证据 |
|---|---|---|
| A01 | pass | drop zone、拖拽监听器与文件名反馈已实现；服务端上传安全测试保持通过 |
| A02 | pass | 实机从纸笔页点击“提交数独”后普通数独被选中；query/控件测试通过 |
| A03 | pass | normalizer prompt、kind mismatch 和 API allowlist 测试通过 |
| A04 | pass | 已知盘面恰好一步、`STEP_LIMIT`、无 advisory；gateway/API 测试通过 |
| A05 | pass | step 中文观察说明、replay 校验、页面 trace 与目标格高亮已覆盖 |
| A06 | pass | 非数独 next_step 失败关闭；188 项、JS、diff、本地服务和 lifecycle 均通过 |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 后续 todo

- 更高阶数独技巧仍按既有边界交还 Agent；本轮未增加搜索、回溯或猜数。
- 未执行真实付费 DeepSeek 图片调用；配置与本地链路已验证，付费视觉冒烟需另行授权。

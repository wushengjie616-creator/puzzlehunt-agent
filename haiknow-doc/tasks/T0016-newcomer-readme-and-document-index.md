---
id: T0016
title: 新人可执行 README 与文档索引
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_plan: P0017
acceptance_contract: v1
---

# T0016 · 新人可执行 README 与文档索引

## 实际步骤

- 2026-10-04：核对当前 README、CLI help、`pyproject.toml`、`.env.example`、纸笔 demo manifest、研究目录和 HAiKnow 文档索引。
- 2026-10-04：确认本任务只重构文档入口，不修改运行时或示例语义。
- 2026-10-04：将根 README 重构为能力地图、证据身份、五分钟启动、六段演示路线、Agent 工作流、Codex 接手入口、代码地图和进阶导航。
- 2026-10-04：新增 `examples/README.md`，把零费用 smoke、五道纸笔题、复杂 session 和运营演示时长组织成可执行目录。
- 2026-10-04：把主题索引从历史链接列表改为“第一次了解、当前权威、开发任务、推理研究、历史证据”五层路由；同步补强纸笔 demo README。
- 2026-10-04：新增文档契约测试，检查新人文档本地链接、核心章节、代码地图和 manifest 中每个 demo 的完整性。

## 与计划的偏差

- 未新增独立 newcomer guide；为避免 README 与另一份入门文档形成双 SSOT，全部新人合同直接放在根 README，`examples/README.md` 只拥有演示路由。

## 关键 commit

- 本任务尚未获得新的 commit 指令；改动保留在当前工作树供用户审阅。

## 测试 / 验证

- 实际执行 `.venv/bin/puzzle-agent solve --file examples/sample_puzzle.json --offline`，得到 `answer=hello`。
- 实际执行 `.venv/bin/puzzle-agent ciphers --text uryyb --limit 5`，首项为 Caesar shift 13 → `hello`。
- 实际按 README 创建并运行 offline complex session，最终 `SOLVED/hello`；验证后删除本次临时 session。
- `.venv/bin/python -m unittest tests.test_documentation_onboarding -v`：3/3，通过本地链接、能力/证据入口及 demo 完整性检查。
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q`：224/224。
- `git diff --check`：通过。

## 验收逐项处置

| ID | 结果 | 证据引用 | 适用身份 | 承接或授权 |
|---|---|---|---|---|
| A01 | pass | README 首屏一句话定位、能力表和四类证据身份 | 根 README | T0016 completed |
| A02 | pass | Python 3.11、web extra、`.env.local` 和 localhost 启动命令均与当前配置/CLI 核对 | macOS/Linux + Windows 路径提示 | T0016 completed |
| A03 | pass | README 六段演示：offline、数独、数织、规则题、complex session、工具/扫雷 | newcomer/运营路径 | T0016 completed |
| A04 | pass | demo 链接测试 + manifest 五题六文件完整性检查 | repository examples | T0016 completed |
| A05 | pass | Codex 阅读顺序、代码地图、验证命令和付费/push/merge 红线 | Codex onboarding | T0016 completed |
| A06 | pass | index 按首次了解/current/dev/research/history 路由且链接检查通过 | current docs index | T0016 completed |
| A07 | pass | README、examples README、paper demo README 均分开真实模型/确定性/scripted/game 证据 | documentation claims | T0016 completed |
| A08 | pass | 三条命令实跑、3 项 doc contract、224 项全量、diff check、HAiKnow gates | current worktree | T0016 completed |

## 范围结论

- task_scope: complete
- overall_goal: complete
- README 与索引已达到新人/Codex 可执行入口目标；工作树尚未提交，等待用户决定是否 commit。

## 后续 todo

- 用户审阅后如需固化，可提交本批 README、索引、示例导航和文档契约测试。

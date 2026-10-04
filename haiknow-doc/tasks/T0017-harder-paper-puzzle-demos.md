---
id: T0017
title: 纸笔演示题难度升级
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_plan: P0018
acceptance_contract: v1
---

# T0017 · 纸笔演示题难度升级

## 实际步骤

- 2026-10-04：确认现有五题均为最小 smoke 规模；Futoshiki 轨迹未使用其声明的 `less_than_support`。
- 2026-10-04：冻结 P0018 难度合同，采用尺寸、未知量、步数和实际技术四类可执行指标。
- 2026-10-04：先增强 `tests/test_paper_demo_examples.py`；旧 manifest 因五个旧尺寸 ID 与新合同不一致而 RED。
- 2026-10-04：用固定随机种子筛选原创、无全局搜索即可收敛的题面，并用独立期望结果锁定终局。
- 2026-10-04：将五题升级为 9×9 数独、10×10 数织、5×5 Futoshiki、3×3 交叉和值和 4×4 Skyscrapers；同步目录名、规则、讲解与新人演示链接。
- 2026-10-04：重构图片生成器以适配不同尺寸，并绘制 3×3 宫粗线、数织多段线索、不等号、和值提示和楼房边缘提示。

## 与计划的偏差

- Kakuro 保留 1 个给定数、8 个未知格；纯六组和值且 9 格全空在当前局部弧一致传播器下未找到可收敛实例。它仍从原 4 格/3 约束升级为 9 格/6 约束，并保持无全局搜索。

## 关键 commit

- 本轮未收到新的提交指令；改动保留在工作树，并与尚未提交的 P0017/T0016 文档批次共存。

## 测试 / 验证

- RED：增强后的 demo contract 首次运行因五个旧 case ID 全部不匹配而失败。
- GREEN：`tests.test_paper_demo_examples` 与 `tests.test_documentation_onboarding` 共 4/4 通过。
- 全量：`.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q`，224/224 通过。
- 轨迹统计：Sudoku 55 步（46 naked、5 row hidden、3 column hidden、1 region hidden）；Nonogram 40 步；Futoshiki 55 步（36 less-than、19 all-different）；Kakuro 10 步；Skyscrapers 15 步。
- Mutation probe：运行时移除数独全部 hidden-single 步，合同测试按预期失败并报告只剩 `naked_single`。
- 图片生成器连续执行两次，五张 PNG 的 SHA-256 保持一致；逐张视觉检查通过。
- `git diff --check`：通过。

## 验收逐项处置

| ID | 结果 | 证据引用 | 适用身份 | 承接或授权 |
|---|---|---|---|---|
| A01 | pass | `sudoku-9x9-image`：9×9、3×3 宫、55 空格、55 步、四类单数技术 | repository demo | T0017 completed |
| A02 | pass | `nonogram-10x10-image`：100 未知格、多段提示、40 步 line intersection | repository demo | T0017 completed |
| A03 | pass | `futoshiki-5x5-rules`：21 未知格、18 个不等式、两类核心技术均出现 | repository demo | T0017 completed |
| A04 | pass | `kakuro-3x3-cross-sums`：9 格、6 个和值约束、10 步 sum support | repository demo | T0017 completed |
| A05 | pass | `skyscrapers-4x4-rules`：16 未知格、16 条边缘提示、15 步 visibility support | repository demo | T0017 completed |
| A06 | pass | 五题 SOLVED；rule-based 轨迹 replay fingerprint 一致且 search_used=false | deterministic engines | T0017 completed |
| A07 | pass | 五图人工检查通过；重复生成哈希一致 | generated PNG assets | T0017 completed |
| A08 | pass | 旧目录名引用扫描为空；文档合同与 224 项全量测试通过 | current worktree | T0017 completed |

## 范围结论

- task_scope: complete
- overall_goal: complete

## 后续 todo

- 如未来扩展 solver 技巧，可另建高级题集；不得降低当前 manifest 的 difficulty 合同来迁就回归。

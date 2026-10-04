---
id: P0020
title: 普通谜题演示风味与推理层次升级
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_task: T0019
acceptance_contract: v1
related_docs:
  - ../docs/03-ccbc16-24-case-solution-guide.md
  - P0019-nonogram-intake-and-general-demos.md
evidence:
  - "现有三份 puzzle.txt 分别直接写出 0/1 位权、取字位置与三格位移、字母距离与 A1Z26，用户确认题目过于简单"
  - "tests/test_general_puzzle_demos.py 已能逐步重放当前 ToolRegistry 调用并核对独立 oracle"
---

# P0020 · 普通谜题演示风味与推理层次升级

> 用户已要求直接优化题目，按 skip-review 执行。
>
> <!-- 一旦执行此 plan 即冻结；偏差只写到 T0019 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景与目标

P0019 的三题证明了确定性工具链可以复演，但题面把核心操作几乎逐字说明，玩家无需提出或证伪机制假设。本轮保留三个 case ID 和现有工具边界，把它们升级为具有情境、隐性机制提示和多阶段中间载体的中等题。

目标不是追求 CCBC 决赛难度，而是让演示能观察到：异常登记、竞争假设、最小测试、识别/排序/提取分层、错误方向排除和全局核验。

## 2. 方案与边界

| 题目 | 升级后机制 | 风味 |
|---|---|---|
| `case-shift-change` | 大小写作为灯态 → 五位字符 → 操作指令 → Caesar 双方向比较 | 暴风夜灯塔换岗与锈蚀密码盘 |
| `night-watch-order` | 叙事约束唯一排班 → 灯标数量作索引 → Caesar | 灯塔七名守夜人的交接记录 |
| `mirror-calibration` | 近回文裂口 → 字母刻度距离 → `FOLLOW` → 箭头网格路径 | 镜廊失窃与镜匠校准纸 |

边界：

- 不新增 ToolRegistry 工具或生产 Agent 行为。
- 不复制 CCBC 原题、原数据或答案。
- 不把提示删到只能靠作者脑洞；每种关键转换至少保留两个相互支持的题面信号。
- 图片、文本、oracle、轨迹和 walkthrough 同步修改；旧答案不作为兼容接口保留。

## 3. 实施与验证

1. RED：扩展 demo contract，禁止旧题面的算法直白提示，并要求每题记录竞争假设、至少两次关键推断和完整信号覆盖。
2. GREEN：改写三题文本、oracle、工具轨迹和 walkthrough；更新图片生成器并重生 PNG。
3. 逐题人工独立推导答案；由 ToolRegistry 重放所有机械步骤。
4. 人工检查图片层级、大小写、灯标、网格、箭头及移动端缩放可读性。
5. 运行聚焦、全量、mutation、diff、敏感信息、HAiKnow acceptance/lifecycle 门。

## 4. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | source | 三份题面不再直写旧版 0/1、取字位置、三格移位、字母距离或 A1Z26 操作指令 |
| A02 | yes | source | 每题至少三层机制，且首层结果不是最终答案 |
| A03 | yes | source | 每题 oracle 记录至少一个被排除的竞争假设、关键推断和信号消费情况 |
| A04 | yes | source | walkthrough 明确包含竞争假设、最小可证伪测试、分层中间结果和终局验证 |
| A05 | yes | source | 三题仅使用当前 ToolRegistry，轨迹 fresh replay 与独立 oracle 完全一致 |
| A06 | yes | artifact | 三张新图片风味完整、信息无截断，大小写/灯标/网格/箭头均可辨认 |
| A07 | yes | docs | 示例索引准确描述升级后的机制和答案，不保留旧机制说明 |
| A08 | yes | validation | 聚焦与全量测试、mutation、diff、文档与 HAiKnow gates 通过 |

## 5. 风险

- 隐喻过弱会让题目变成无根据猜法：由 oracle 的 signal coverage 和 walkthrough 的最小测试反查。
- 隐喻过强会退回教程题：测试禁止旧版直白措辞，人工审题检查题面是否仍直接宣布算法。
- 图片大小写 OCR 不稳定：文本 fixture 保留精确转写；图片用于真实视觉演示，确认页仍允许用户校正。
- 工作树已有上一轮未提交内容：只改本轮列出的普通题资产与文档，不 reset、stash、clean 或提交。

## 6. 成稿自审记录

- 日期 / 审核者：2026-10-04 / 主 Agent 自审。
- 上下文：宿主策略禁止未获用户明确要求的子 Agent，因此无法使用独立 fresh-context reviewer；从落盘文件完整重读自审，不声称独立审核。
- 意图与范围：只提升既有三题的风味和推理层次，不扩展 Agent 能力或新增依赖。
- 事实与方案：旧题直白提示由三份 `puzzle.txt` 可直接核实；三条新机制均映射当前注册工具。
- 风险与验证：同时覆盖“过难”和“过明示”两侧，确定性 replay、独立 oracle、视觉检查与全量回归可观察。
- findings：preflight 因上一轮未提交工作返回 stop-and-ask；用户已明确要求在当前项目继续优化，故保留工作树原地实施，并在 T0019 记录偏差。未发现需要用户另行决定的关键方向。
- 结论：成稿可按已有 skip-review 授权实施；不包含 commit、push、merge 或付费模型调用授权。

# P0005 · CCBC16 文本题八小时循环评测

状态：执行中（用户于 2026-08-28 14:xx +08 更新目标）

## 目标

在八小时窗口内，把 CCBC16 非 Meta 中可以保真转换为文本的题目构造成可重复、oracle 隔离的测试集；同时验证模型产出的中间答案与最终答案。每小时运行一次，打印带时间戳的人类可读报告，并依据报告中的失败证据选择下一轮 framework、prompt 或确定性 tool 改进。

## 约束

- 官方题面、解答与答案保存在 ignored runtime test cache；Git 只提交生成器、来源清单、摘要元数据和脱敏报告。
- “可文本化”由实际 player-facing HTML/content 检测决定；不能只看顶层 `image`/`script` 字段。图片 URL placeholder 不算题面。
- worker 只读取 input；中间与最终 oracle 均在 worker 退出后由父进程读取。
- 中间答案必须有独立 checkpoint 评分；最终答案正确不能掩盖缺失的中间推理，反之亦然。
- 每轮冻结 Git commit，逐题记录耗时、调用数、答案、阶段 checkpoint、节点作用和失败分类。
- 每份小时报告必须包含本地时间戳、总体结果、逐题结果、节点汇总、失败分析和下一轮优化假设。

## 实施顺序

1. 修复官方转换器，使其消费真实 `html` surface，并识别内联图片、交互脚本和空题面。
2. 从官方 solution/analysis 提取可审计的中间 checkpoint，生成可重复文本 suite。
3. 增加显式 intermediate verification node 与 evaluator-only checkpoint scorer。
4. 建立 1h × 8h 可恢复 scheduler 和 stdout/Markdown 双报告。
5. 运行首轮，按报告只修改被证据指向的 graph/prompt/tool；每轮保留 before/after。

## 完成证据

- 生成器对 49 道非 Meta 给出 included/excluded 及理由，included 全部通过 oracle leak 与非空题面验证。
- 每个 included case 有 final oracle；有官方可抽取 checkpoint 的题具备非空 intermediate oracle。
- graph trace 显示 intermediate verification 与 final verification 分离。
- 八个小时锚点均有时间戳报告，或明确记录因构建/失败错过的锚点且不伪造批次。
- 每轮改进都有报告证据、测试 RED/GREEN 和下一轮验证结果。

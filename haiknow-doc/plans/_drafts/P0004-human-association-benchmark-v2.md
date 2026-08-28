# P0004 · 人类联想路径研究与复杂评测集 v2

状态：执行中（用户于 2026-08-28 明确要求纠正）

## 问题

现有 `benchmarks/cycles/cases/v1` 把 operator、参数、执行顺序甚至提取方式直接写进风味文本，主要测 instruction following 和 ToolRegistry 契约，不足以测试从题面异常联想到语义域、主题和机制的能力。此前 CCBC16 subagent 研究覆盖机制分类，但没有系统记录人类联想桥、合理错路与 falsifier；也没有覆盖 CCBC15、CCBC12。

## 目标

1. 从 CCBC16、CCBC15、CCBC12 官方题面与解析抽样研究人类解题路径。
2. 形成 `observable → association → theme → competing mechanism → falsifier → verified intermediate → extraction` 的可反驳方法论。
3. 保留 v1 为显式机制 smoke baseline，新增五道原创 v2；不覆盖历史评测证据。
4. v2 每题至少三层，风味文本最多提供一个语义域或表面异常，不给准确工具名、参数、操作顺序或最终提取。
5. 对 v2 做 shortcut red-team、title/flavor ablation、oracle 隔离和 trace rubric 验证，再恢复原 24 小时窗口内尚未发生的周期评测。

## 研究分工

- `ccbc16_human_reasoning`：至少 10 道代表题的人类联想路径与 v2 约束。
- `ccbc15_human_reasoning`：至少 10 道非-meta，重点是弱风味、跨域联想和结构消歧。
- `ccbc12_human_reasoning`：至少 10 道非-meta，重点是语义、空间、跨层载体和错误假设。
- 主 Agent：直接复核官方 CCBCArchive；合并交集与分歧；设计、测试并冻结 v2。

## v2 验收门

- 每题有至少两个合理错误假设与题内可观察 falsifier。
- 单看 title+flavor 不能确定 operator；只给 flavor 不可解。
- 题面主体可在无外部浏览的条件下验证核心背景桥，不把冷门事实作为唯一入口。
- 正确路径解释至少 90% 显著 token/格式特征，未消费线索必须为零。
- 禁止准确 cipher/tool 名、参数、方向序列、排序法、索引法和最终提取法出现在 flavor。
- 首尾字、长度、A1Z26、全工具枚举等单步 shortcut 不能直接产出答案。
- trace rubric 独立评分 observation、theme leap、两假设、falsifier、intermediate、extraction、coverage；幸运猜中不算 reasoning pass。
- 题型至少覆盖文化 association、异构 feeder、文本空间/状态、样例归纳 operator algebra、残缺重建中的四类。

## 迁移与调度

- v1 历史三轮改标 `explicit-baseline`，不删除、不重算。
- 15:00 旧 scheduler 已暂停，避免继续生成无效基线。
- v2 完成、lint 与离线契约测试通过后，使用相同结束锚点恢复未完成周期；每轮冻结 Git commit，运行中保持 evaluation lock。
- 只有同一冻结版 v2 五题全部正确才触发 CCBC16 非-meta hard set 一次性门。

## 失败策略

若 v2 未能在下一锚点前通过验收，不为赶时间恢复旧题；记录错过的锚点与原因，在下一个三小时边界运行。不得把作者知道答案的 walkthrough 当 blind difficulty 证据。

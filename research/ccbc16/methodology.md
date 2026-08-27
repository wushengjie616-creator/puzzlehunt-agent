# TRACE-LIFT：PuzzleHunt 可审计解题方法论

本方法论由 CCBC16 非 Meta 题及公开解析的机制共性蒸馏而来，但不保存、复述或向模型发送完整题面、题解与答案。来源事实见 [source-ledger.json](source-ledger.json)；以下框架与术语是本项目的二次抽象。

## 1. 九步主循环

`TRACE-LIFT` 不是让模型展示私有思维链，而是要求它留下可复验的工作产物。

| 步 | 名称 | 必须产物 | 反例门 |
|---|---|---|---|
| T | Transcribe · 保真转写 | 原始文本、大小写、空格、坐标、方向、颜色/字体说明 | 不在观察前统一大小写、转码或重排 |
| R | Register · 线索登记 | 标题、风味、题面、顺序、标签、图标、边界、题号、artifact 清单 | 不把风味当装饰，不把联想当事实 |
| A | Alternatives · 竞争假设 | 至少两个机制假设，各自的预测与可证伪条件 | 不先猜答案再倒推机制 |
| C | Compute · 有界实验 | 工具名、显式参数、输入 fingerprint、状态与输出 | 工具结果只是 evidence，不是答案 |
| E | Evaluate · 证据审计 | 支持/削弱/反驳、覆盖率、唯一性、歧义和预算状态 | `BUDGET_EXHAUSTED` 不得伪装成唯一解 |
| L | Layer · 层级检查 | “当前答案是否仍是载体”、下一层可观察属性 | 得到可读词不自动停止 |
| I | Inventory · 未消费项 | 尚未解释的标题词、颜色、顺序、坐标、异常、反馈 | 任一显著元素未使用时降置信度 |
| F | Falsify · 不变量与反证 | 多解交并差、留出样本、checksum、往返转换 | 多解不等于题坏了，可能要提取不变量 |
| T | Terminal verify · 终局验证 | 独立 derivation、格式、全线索消费、风味回扣 | 主题联想不能替代完整提取账本 |

## 2. 五个高频机制家族

### 2.1 表面属性是第二信道

大小写、颜色、粗细、有无、点划、朝向和题号图标都可能承载二进制或分类值。预处理必须保留原貌；工具必须记录 polarity、bit order、视角和 normalization。

### 2.2 异常、缺失与冲突本身是信息

语义图中的缺边、分类离群项、乱码、被遮挡线索、横纵交点冲突和逻辑题多解都应生成“故意异常”竞争假设。先比较正常结构和异常结构，再决定是修复采集错误还是提取差异。

### 2.3 中间答案仍可能是载体

解出 emoji、单词、子题或逻辑盘后，继续检查其长度、字形、位置、共有字符、拼音、顺序和对应图标。`intermediate_answers` 与 `extractions` 必须分账，防止把 feeder 当 final。

### 2.4 复杂题是状态图或子任务 DAG

操作顺序、依赖、循环、实物翻面、随机分支和 recursive callback 应显式建图。执行顺序不一定等于提取顺序；每个节点记录输入来源、输出、消费者和未解决依赖。

### 2.5 唯一性与不变量优先于“看起来合理”

对于多解纸笔题、约束排序和候选密码，分别追踪：线索补法是否唯一、解是否唯一、不同解是否共享同一提取。短可读词只有在覆盖率、消费率和独立验证同时成立时才能提升为答案。

## 3. 方法卡格式

每个新机制用同一模板进入本项目知识库：

```text
name              稳定名称
source_refs       官方 URL，只供研究 provenance
observable_signals 触发它的题面事实
hypothesis        可检验机制，不写成事实
operation         人工或工具步骤
intermediate      可复验中间产物
falsifiers        哪些结果会推翻机制
ambiguities       视角、位序、编码、坐标、词表版本
agent_landing     observation / hypothesis / tool / evidence / verify
automation_level  deterministic / bounded-solver / model / human-artifact
```

只有同时具备稳定输入契约、有限计算、独立 known vector 和清楚失败状态的卡片才能进入 ToolRegistry。

## 4. 工具分级

### L0 · 纯机械转换

Caesar、Atbash、A1Z26、bit pattern、interleave、网格变换、位置提取、字符串交并差、排序与码点转换。返回 `output + parameters + provenance`。

### L1 · 有界小型求解器

约束排序、扫雷枚举、拉丁方、吸收马尔可夫链、词链、有限置换。统一返回：

```text
SAT | UNSAT | AMBIGUOUS | BUDGET_EXHAUSTED
solution_count
truncated
convention / coordinate_system / normalization
```

### L2 · 模型判断或知识研究

语义离群项、品牌/作品联想、中文谐音拆字、开放语料匹配。必须附来源、覆盖率和反例；不能伪装为确定性脚本。

### L3 · 人工或视觉 artifact

任意图像拼合、折纸、实地交互、复杂 3D。文本 Agent 只管理转写契约和 interrupt，不把 placeholder 当 artifact。

## 5. 对 Agent 节点的约束

- `artifact_inventory`：判断输入是否保留版式/原始字节；文字题不应误触发人工中断。
- `observe_classify`：分离事实、异常、风味联想；列出所有 clue channels。
- `hypothesize_plan`：比较主体机制、答案仍是载体、冲突是机制三类解释；计划必须可证伪。
- `tool_dispatch`：只执行显式参数的 bounded 工具；保留 fingerprint、失败状态和 extraction provenance。
- `evaluate_evidence`：固定检查 coverage、consumption、uniqueness、invariant、reversibility。
- `verify_answer`：要求 format、evidence、flavor callback、clue coverage、all elements consumed、independent derivation 全部为真。

## 6. 当前工具 backlog

优先候选：二态样式转 bit、mojibake 修复、自定义 token Morse、Playfair、Braille、九键、旗语、猪圈规范 token、字符串公共符号、网格变换、置换、吸收马尔可夫、扫雷解集差异、拉丁方唯一性、拼音韵母/声调比较。

暂不工具化：开放式文化联想、任意中文字谜、无限词典爆破、未限定纸笔 solver、视觉相似度猜密码。它们缺少可防误报的稳定契约。

## 7. 学习闭环

每次评测只允许从失败证据产生改动：缺观察 → 改 clue ledger；选错机制 → 改竞争假设/反证；机械步骤失败 → 加工具或修契约；工具成功但答案错 → 查层级/提取；正确但证据链断裂 → 加验证门。下一批必须冻结新的 Git commit，不能在同一批五题之间改框架。

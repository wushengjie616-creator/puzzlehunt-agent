# 从题面到主题：CCBC12/15/16 人类联想路径研究

## 研究边界

本研究直接复核官方题面与公开解析，不把官方原题、完整题解或答案复制进仓库，也不将它们交给 DeepSeek。官方来源为 [CCBCArchive](https://github.com/cipherpuzzles/CCBCArchive) 和 [CCBC16 归档站](https://ccbc16.cipherpuzzles.com/)。三条独立研究流共复核 37 道代表性非 Meta：CCBC16 13 道、CCBC15 11 道、CCBC12 13 道。

旧研究的范围需要明确：`ccbc_01_20_audit`、`ccbc_21_40_audit`、`ccbc_41_55_audit` 完成的是 CCBC16 机制覆盖和工具落点，不包含逐题的人类联想路径，也没有研究 CCBC15/12。新研究流为 `ccbc16_human_reasoning`、`ccbc15_human_reasoning`、`ccbc12_human_reasoning`。

## v1 为什么不是 reasoning benchmark

`benchmarks/cycles/cases/v1` 的五道题分别直接透露了逐行位移和索引、异类与唯一排序、reverse/interleave/A1Z26、起点和方向来源、每包 codec/依赖/最终取字。它们能测试 provider、工具参数、状态持久化和节点追踪，却没有保留从异常到主题的发现问题。前三轮因此只归类为 `explicit-baseline`。

## 37 题的代表性路径

以下只记抽象认知路径，不记答案。

### CCBC16

| 题目 | 人类联想桥 | 关键证伪/验证 |
|---|---|---|
| 小题大做 | 规范专名大小写 → 五位表面 bit | 单纯取首字或数大写不能消费位置差异 |
| 五音俱全 | 中国五声 → 西洋唱名载体 → 方向读取 | 映射必须完整填槽并解释箭头 |
| 举旗不定 | 扫雷恰有两解 → 解差方向 → 旗语 | 第一解不是事实；必须枚举并比较全解空间 |
| 浮想联翩 | 联想图异常词 → 同一文化语料 → 补边穿字 | 自由联想须被邻接、字形和语料顺序共同约束 |
| 就是为了这点醋 | 异构 feeder → 共同词法关系 → 字形部件 bit | 统一密码假设无法解释各子题局部 checksum |
| 周而复始 | 纸环状态 → 中文词链 → 英文共享字母 | 必须复演状态图；任意看图命名不算证据 |
| 复习资料 | 生成题反馈 → 远端参数 → 规律 holdout 外推 | 目标远超枚举范围；样本规律需在保留集验证 |
| 烫烫烫 | 乱码症状 → 多源编码各自逆转 → 全局句约束 | 单一 codec 只能修复局部；残缺候选由全局收敛 |
| 只说明书 | 说明反推题面 → 动作状态机 → 时间变量破环 | “回到同一布局”不等于完整状态相同 |
| 只剩提取 | 输出 residue → 三种 rule family → 递归 micro-meta | 可读中间词可能是操作说明而非答案 |
| 福尔摩斯探案集 | rebus → 规范文化 corpus → 最小编辑差 | corpus 能解释全部碎片且编辑距离一致 |
| 你说话带括号 | Unicode token → 语义 operator → 嵌套复合 | 每个 operator 至少两个例子归纳、一个 holdout 验证 |
| 千字谜 | canonical corpus → 每列规则归纳 → anchor 排序 | 变换必须对整列成立，不能只拟合特殊格 |

### CCBC15

| 题目 | 人类联想桥 | 关键证伪/验证 |
|---|---|---|
| 镜中何物 | 字母先换入多套图形表示 → 镜像关系 | 直接倒序/Atbash 不能解释标签和三值结构 |
| 北京人儿在纽约 | 北京儿化 → 跨语言后缀 → 文化配对 | 单一醒目配对只是 anchor，其余行必须一致 |
| CCBC MOE | 动态票数不变量 + 5/2/红黑 → 扑克 ontology | 比较多次状态；变化数值是诱饵，稳定排序才是信号 |
| 梵天千变咒 | 字符操作 → 类比迁移到语义对象 | 必须同时保存 form operation 和 meaning operation |
| 外推法 | 异常数字曲线 → 现实命名系统 | 数学拟合无语义解释力，不能统一异常类别 |
| 河海解谜 | 异构章节 → 重复声韵 motif → 内部 meta | 子题结束仍有标题簇和章节输出未消费 |
| NO…thing is Everything | 空题面 → 原始 Unicode 承载层 | 显示长度与码点长度不一致，隐藏 token 有稳定分类 |
| 狮头蝎尾 | 动物+希腊字母 → 星体实体 → 坐标 gestalt | 头尾拼词或旗语不能解释实体坐标和连续重叠 |
| Bill，人工智能助手 | 异常对话 → 重置对照实验 → 人格/作品 corpus | 单次回复不是事实，触发必须可复现 |
| 豆捞学园 | 英文释义 → 汉字候选 → 部件约束 → 再回英文 | 翻译 lattice 由字形和主题反选，不可贪心 |
| 对不起 | 交互反馈 → 分支 differential → 稳定叙事锚计数 | 初始风味也是状态 0，遗漏会破坏完整序列 |

### CCBC12

| 题目 | 人类联想桥 | 关键证伪/验证 |
|---|---|---|
| 奇怪的瓶子 | 物体 affordance → 液面/连通物理过程 | 高低直读或迷宫路径不能解释容量和覆盖 |
| 丢失的瓷砖 | 独立 panel → 常识有限序列 → 缺项短语 | 不应先强求全局单一机制 |
| 多彩座钟 | 精确日期 → 人物/方法参数；段几何 → 点划 | 日期不是答案域，颜色不是简单编号 |
| 玄幻小说 | 拗口断句 → 标点边界术语 → 专业 ontology | 异常集中位置比藏头或笔画有更高覆盖率 |
| 破碎的海报 | 滑块路径 → 历史实体 → 月份参数 → 日历提取 | 背景知识负责补参数，不直接负责猜答案 |
| 黑色方碑 | 同一符号的天体/金属双重语义 | 双域三联关系解释全部数对并产生合法索引 |
| 红色便签纸 | 每行局部类别 ∩ 跨行共同 codebook | 局部同义候选靠全局集合交收敛 |
| 楔形文字 | 每 token 两种 decoder → 词约束选分支 → 分支 bit | 明文不是载荷，decoder provenance 才是下一层信息 |
| A/I | 镜像恢复主题 → 版式作为维度代数语法 | 像素/颜色编码不能解释上下布局和两部分选择 |
| 灰红蓝绿 | 现实分类正确性 → 点阵 mask → 中间指令 | 第一次可读输出是 instruction，不是答案 |
| 十四行诗 | 失真翻译 → 规范原文重建 → 单编辑差 | 藏头不能解释逐行异常和编辑标记 |
| 车票 | 站点识别线路 → 线路色+票面色 → 外部标准 | 线路号不能消费颜色对和成束意象 |
| 积木 | exact cover 几何约束 ↔ 覆盖词语义约束 | 单独做几何或找词都多解，必须交替传播 |

## HA-BRIDGE：人类联想的可审计循环

`TRACE-LIFT` 管理完整解题生命周期；新增 `HA-BRIDGE` 管理从观察到机制承诺之前的认知跃迁：

1. **H · Highlight tension**：只登记最不自然的事实；不报密码名。
2. **A · Association fanout**：为每个 tension 扩展 3–5 个语义邻域，并标记可能角色：theme、parameter、ordering、decoder、extractor 或 instruction。
3. **B · Bridge objects**：明确题面对象如何映射到候选本体对象；桥至少解释两个独立信号。
4. **R · Risk a prediction**：选择尚未处理的 holdout，先写出假设会预测什么。
5. **I · Invalidate cheaply**：用一行、一个 panel、一个状态差或一个 token 做最低成本证伪。
6. **D · Develop material**：预测通过后才全量展开，生成表格、图、状态日志或候选 lattice。
7. **G · Grade the intermediate**：将产物分类为 answer、instruction、parameter、ordering key 或 transformed artifact。
8. **E · Explain leftovers**：审计标题、风味、数字、顺序、版式、异常与反馈是否全部消费。

核心规则：联想到某主题只形成 hypothesis；只有 holdout 预测、中间物和覆盖账本成立后才形成 evidence。

## 阶段 memory 契约

每个候选桥至少保存：

```json
{
  "tension_ids": ["t1", "t2"],
  "ontology": "candidate domain",
  "association_role": "theme|parameter|ordering|decoder|extractor|instruction",
  "bridge": [{"surface": "...", "domain": "..."}],
  "predicted_holdout": "...",
  "cheap_test": "...",
  "falsifier": "...",
  "prediction_result": "pass|fail|unknown",
  "supports": ["signal-id"],
  "contradictions": [],
  "intermediate_type": "...",
  "unconsumed_signals": ["..."],
  "confidence": 0.0
}
```

模型不得把“很像”写进 evidence；工具不得替模型选择 ontology；失败预测必须保留而不是覆盖。

## 风味文本泄漏量表

| 级别 | 内容 | 用途 |
|---|---|---|
| L0 | 纯叙事，无有效 orientation | 可用，但需确保主体自足 |
| L1 | 暗示一个语义域或指出一个表面异常 | v2 目标 |
| L2 | 暗示一种表示切换，但不含 operator/参数 | 仅在后续仍有两层时可接受 |
| L3 | 给出 operator 或 cipher family | 只能做教学/工具基线 |
| L4 | 给出参数、顺序或索引法 | instruction-following baseline |
| L5 | 给出完整 pipeline 或最终提取 | 不算 reasoning test |

v2 每题必须为 L0–L1；第一层特别困难时最多 L2，但不得同时泄露第二层。

## Agent 结构变化

- `observe_classify` 拆出 surface tension，只保存事实和异常。
- 新增 `associate_theme`：ontology beam、跨域 bridge、角色和待验证预测；此时不可见完整工具目录。
- `hypothesize_plan`：只允许从 association ledger 形成机制，计划必须包含 prediction 和 falsifier，再按假设检索有限工具。
- `evaluate_evidence`：保留预测失败、分类中间物、更新未消费线索和信息增益。
- `verify_answer`：答案 exact match 之外，要求 bridge、holdout、intermediate、extraction provenance 和 coverage 全部成立。

## v2 评测要求

- 每题至少三层：orientation/theme、经验证的 mechanism/intermediate、非显然 extraction。
- 每题两个合理错路及题内 falsifier；至少两个独立信号支持正确 bridge。
- 单看 title+flavor 不可确定 operator；只给 flavor 不可解。
- 单次确定性工具调用不得直接产出最终答案。
- 至少三题的第一层产物是 instruction/parameter/ordering key，而非答案。
- 自动检查常见 shortcut：首尾字、长度、A1Z26、直接 Caesar/Atbash/Base、全工具枚举。
- trace rubric：theme/bridge 30%，证据覆盖 25%，中间物 20%，提取 15%，终局 10%；只猜中答案标 `lucky-answer`。
- 分别记录 discovery、mechanism execution、extraction/verification latency。
- title/flavor ablation：完整题应更快定位；无 flavor 仍能由主体求解但更慢；只给 flavor 必须不可解。

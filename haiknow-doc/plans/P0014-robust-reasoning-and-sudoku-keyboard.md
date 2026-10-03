---
id: P0014
title: 普通谜题鲁棒推理链与数独键盘导航
status: completed
created_at: 2026-10-03
plan_completed_at: 2026-10-04
mode: review
paired_task: T0013
acceptance_contract: v1
related_docs:
  - ../../docs/01-puzzle-agent-architecture.md
  - ../../../research/human-association-reasoning.md
  - ../P0011-agent-cipher-reference-routing.md
evidence:
  - "git rev-list --left-right --count origin/main...HEAD → 0 5；origin/main 是 HEAD 祖先；基线 commit ec22f1c"
  - "src/puzzle_agent/web/static/app.js:21-54 已有数独可编辑 input 网格与冲突检测，但没有 keydown 导航"
  - "src/puzzle_agent/complex_graph.py:62-160 已有观察、联想、假设、工具、证据与验证阶段，但没有显式表示假设/映射约束账本"
  - "src/puzzle_agent/cipher_reference.py:180-210 已有关键词索引和资料 lookup；cipher_workbench.py:82-98 的 Bacon 解码只有现代 26 字母版本"
  - "src/puzzle_agent/web/static/app.js:11,74 的普通谜题结果当前只显示状态与最终答案，不显示可审计解题轨迹"
---

# P0014 · 普通谜题鲁棒推理链与数独键盘导航

> **触发**：用户要求数独识别确认表格支持方向键移动，并要求参考“培根提示 → 符号展开 → 固定宽度约束 → 密码变体比较 → 答案长度与语言交叉验证”的例题，提升普通谜题 Agent 的思维能力；明确要求学习鲁棒推理方法，不得过拟合该题。
> **模式**：review；用户于 2026-10-03 批准实施并要求 session-alive 无人值守执行。授权包含本地实现、测试与 commit，不包含付费模型调用、push、merge 或公网部署。
>
> <!-- 一旦执行此 plan 即冻结；偏差只写到对应 task 的“与计划的偏差”章节，不回改本 plan -->

## 1. 背景 / evidence

### 1.1 已确认的现状

1. 数独识别结果已经渲染为逐格 `<input>`，支持鼠标点击、直接编辑、行列宫冲突标红；目前没有 `keydown`
   处理，所以方向键不会按照数独坐标稳定移动焦点。
2. 普通谜题复杂 Agent 已有 HA-BRIDGE 风格的八阶段状态图：观察异常、联想主题、拆分子题、验证子题、
   建立假设并规划工具、评价证据、验证中间产物、验证答案。现有设计能防止“看到培根就直接当答案”，但
   对“一个题面 token 可能展开为多个基础符号”“映射是否满足全组长度约束”“同一密码的多个标准变体”
   仍缺少可持久、可执行、可验证的中间表示。
3. 密码关键词已经能路由到内置资料，复杂 Agent 可调用 `cipher_reference_lookup`；因此本计划不重复建设
   密码搜索库，而是补齐“如何把资料与题面异常连接成可证伪实验”的中间层。
4. Web 普通谜题路径目前只把 Agent 状态和最终答案显示给玩家。即使内部 state 保存了 observations、
   hypotheses、attempts、evidence 和 checks，玩家也看不到“看到什么 → 联想到什么 → 查了什么 → 怎样验证”。

### 1.2 从例题抽象出的能力，而不是题目特判

例题中的关键能力不是“记住 `吧=BA`”，而是以下可迁移结构：

| 抽象能力 | 例题表现 | 可迁移场景 |
|---|---|---|
| 线索只负责路由 | “培根”提示 Bacon family，但不是答案证据 | 标题、风味、专名、日期、颜色提示某资料域 |
| token 可组合展开 | 一个可见字可能对应 0/1/多个基础符号 | 拟声词、缩写、合字、方向组合、重复笔画、emoji 组合 |
| 用全局约束筛映射 | 七组展开后都恰为五位 | 固定宽度、等长、校验和、分组数、位置关系、答案格式 |
| 竞争解释而非单路强解 | 24/26 字母 Bacon 变体并行 | 码表变体、镜像方向、bit order、索引基准、语言版本 |
| 独立信号交叉验证 | 标题、五位分组、7 字母格式、英文成词共同成立 | 题面覆盖、holdout 预测、格式、语言、风味回扣 |
| 保留失败解释 | 24 字母版输出不自然且覆盖较差 | 防止只展示成功路径、事后合理化或 lucky answer |

### 1.3 设计原则

- 模型负责提出少量、题面有依据的表示假设；脚本负责机械展开、计数、查表和验证，不允许脚本无界枚举映射。
- “搜”默认先查项目内确定性资料库；本计划不新增自动互联网搜索，避免成本、来源和注入边界扩大。
- 输出的是可审计的结论链与证据，不暴露或要求模型隐藏 chain-of-thought。
- 例题是正向验收样例之一；必须同时用非 Bacon、反例和歧义样例证明没有过拟合。

## 2. 范围 / 方案

### 2.1 方案选择

| 方案 | 做法 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| A · 只改 prompt | 告诉模型注意双字符展开、长度和变体 | 改动小 | 不可机械复验，容易复述示例并过拟合 | 不采用 |
| B · 表示账本 + 通用约束工具 | 在现有阶段加入 typed representation hypothesis，由通用脚本验证展开和约束 | 可迁移、可测试、无需增加模型轮次 | 需要扩展 state/schema、工具与 UI | **推荐** |
| C · 新增独立 LLM 推理阶段 | 在联想与规划间增加一次“表示发现”调用 | 阶段语义最清楚 | 基线调用从 8 增至 9，replan 预算和 checkpoint 都要迁移 | 暂不采用；B 有真实失败证据后再评估 |

### 2.2 交付轨 A：数独键盘导航

在数独确认网格使用事件委托监听 `keydown`：

- `ArrowUp / ArrowDown / ArrowLeft / ArrowRight` 按行列坐标移动焦点；边界采用 **clamp**，不环绕，避免误跳到另一行或另一宫。
- 仅在 Sudoku editor 内拦截四个方向键并 `preventDefault()`；数字键、Backspace、Delete、Tab、Shift+Tab
  和输入法行为保持浏览器原生语义。
- 所有识别数字与空格都可获得焦点，因为确认页的目的就是允许修正 OCR；不跳过“已知数”。
- 沿用现有可见 focus 样式和 `aria-label`，移动后调用 `.focus()`，不改变值、不自动提交、不触发求解。
- 鼠标、触摸和 Tab 导航继续可用；移动端软键盘行为不作为本次方向键验收前提。

预计影响：`web/static/app.js`、必要时 `styles.css`，以及 Web 静态契约/浏览器行为验收。

### 2.3 交付轨 B：显式的“表示假设”账本

在现有复杂 Agent state 增加 `answer_constraints` 与 `representation_hypotheses`，不增加 LLM stage：

```json
{
  "answer_constraints": [
    {"id":"c1","kind":"length","value":7,"signal_ids":["o-format"],"explicit":true}
  ],
  "representation_hypotheses": [
    {
      "id":"r1",
      "association_id":"a-bacon",
      "units":[["吧","啊","吧"],["啊","吧","啊","啊"]],
      "mapping":[
        {"token":"啊","expansion":"A","basis":"phonetic","signal_ids":["o-symbols"]},
        {"token":"吧","expansion":"BA","basis":"phonetic-composition","signal_ids":["o-symbols"]}
      ],
      "invariants":[{"kind":"expanded_width","value":5,"signal_ids":["ref-bacon"]}],
      "prediction":"all groups expand to width 5",
      "falsifier":"an observed group has another width or an unmapped token"
    }
  ]
}
```

运行时契约：

- `OBSERVE_CLASSIFY` 只抽取题面明确给出的答案长度、分组、重复 token 等事实，形成
  `answer_constraints`；不得凭语言感觉制造格式约束。
- `ASSOCIATE_THEME` 仍只生成 ontology/bridge/prediction，不直接写映射。
- `HYPOTHESIZE_PLAN` 可生成最多 4 个表示假设；每个映射必须给出题面依据和 signal IDs，每个假设必须有
  至少一个可机器检验 invariant、prediction 和 falsifier。
- 计划项引用 `representation_id`，使工具结果能回连到提出它的解释，而不是散落的自由文本。
- mapping、units、expansion、数量和字符总长均设上限；未知 token、重复键、空扩展或越界输入失败关闭。

这套 schema 不写死 A/B、中文谐音或 Bacon；它表达的是“题面 token → 基础载荷”的一般组合表示。

### 2.4 交付轨 C：两个有界确定性工具

#### C1. `expand_symbol_groups`

通用工具，不猜映射、不枚举：

- 输入：token groups、显式 mapping、可选 allowed alphabet、可选 expected width。
- 输出：每组原 token、逐 token expansion、拼接结果、实际宽度、每条 invariant pass/fail、未映射 token。
- 结果保留 group 顺序并提供输入/输出 fingerprint；同一参数重复调用沿用既有去重规则。
- 适用于 Bacon/Morse/bit/方向/图形部件等多种表示；不能根据英文可读性自行修改 mapping。

#### C2. 显式变体的 Bacon decoder

扩展现有 Bacon 能力而不把它混入通用工具：

- 接受已经得到的五位 A/B groups，显式选择 `modern26` 或 `classic24`。
- 返回 variant ID、逐组 code/letter 和完整输出；非法码组明确失败。
- 两种变体必须由两个独立计划项执行，工具不按“像英文”自动选优。
- 24 字母表的 I/J、U/V 合并语义必须来自同一密码资料 SSOT，并在网页和 Agent lookup 中一致呈现。

通用展开与领域解码分层，可以证明 Agent 是“先验证表示，再使用码表”，而不是把整题塞给专用函数。

### 2.5 交付轨 D：证据评价和终局机器门

扩展现有评价与验证契约：

1. `EVALUATE_EVIDENCE` 必须分别记录每个 representation hypothesis 被支持、削弱或否决的原因，并保留失败变体。
2. 只有工具证明全部目标组满足不变量，相关 mapping 才可从 hypothesis 升为 evidence。
3. `answer_constraints` 中的显式长度/模式由运行时机械复核；模型把 check 写成 true 不能覆盖机器失败。
4. 高置信答案至少满足：可重放表示、明确 codebook/variant、题面格式、两条独立线索覆盖；自然语言可读性只能
   加分，不能单独证明答案。
5. 若两个变体都通过机械约束且缺少独立信号区分，结果必须是 `NEEDS_REVIEW`，不能因其中一个更像英文就
   偷偷判定。
6. keyword hint、资料 lookup 与 phonetic/shape association 始终是 routing/basis，不直接算解码证据。

### 2.6 交付轨 E：玩家可见的可审计过程

为普通谜题结果新增结构化过程视图，从已持久化 state 派生，不追加模型请求：

- **看到什么**：observations、tensions、显式答案格式。
- **联想到什么**：候选 ontology、桥接信号、尚未解释元素。
- **查了什么**：命中的内置资料及 variant，标明“提示，不是证据”。
- **怎么验证**：表示 mapping、逐组展开、宽度/字符集检查、工具结果、被否决替代项。
- **为什么接受/停下**：答案检查、线索覆盖、未解决问题与 blocker。

UI 只展示短结论、显式假设、工具输入输出和验证结果；不显示原始模型 prompt、隐藏思维链或 API 配置。
状态为 `NEEDS_REVIEW` 时也完整展示已证内容和未决点，避免“没有答案等于没有思考”。

### 2.7 实施拆分

| 顺序 | 子项 | 预计文件 | 实施方式 |
|---|---|---|---|
| 1 | 数独方向键 RED/GREEN | `web/static/app.js`、`tests/test_web_api.py` 或轻量浏览器测试 | 先锁定边界、不改值、Tab 不受影响 |
| 2 | 通用展开工具 RED/GREEN | `tool_registry.py`、`tests/test_tool_registry.py` | 纯函数、明确上限、无枚举 |
| 3 | Bacon 24/26 SSOT 与工具 | `cipher_reference.py`、`cipher_workbench.py`、相应 tests | 变体显式、逐组 provenance |
| 4 | state 与阶段契约 | `complex_domain.py`、`complex_graph.py`、offline provider、graph tests | 不新增 LLM call；严格校验引用和机器门 |
| 5 | Web 可审计 trace | `web/app.py`、`web/static/index.html`、`app.js`、`styles.css`、Web tests | 从 state 派生，缺字段兼容旧 session |
| 6 | 泛化回归集 | 新增/扩展 complex journey fixtures | 正例、近似反例、非 Bacon、歧义与旧基准 |
| 7 | 文档与本地部署 | README、architecture、task；重启 8017 | 文档代码同批；真实付费调用仍需单独授权 |

### 2.8 Contract impact map

| 维度 | 结果 |
|---|---|
| canonical SSOT | `complex_domain.new_puzzle_state` 定义持久 state；`complex_graph._STAGE_INSTRUCTIONS` 定义阶段输出；`ToolRegistry` 定义可调用工具；`cipher_reference.py` 拥有密码资料/变体 |
| active consumers | complex CLI/session/Web 共用 graph state；Web result renderer 消费普通谜题结果；simple solver 继续使用现有 reference hints，但不承担多阶段 ledger |
| templates / generators | `complex_offline.py` 的 staged provider 与测试 provider 必须同步新增字段；无外部代码生成器 |
| mechanical checks | domain/graph/tool/Web 单元测试、全量 unittest、JS syntax、旧 checkpoint 缺字段兼容、diff check；可选真实模型评测须另授权 |
| historical snapshots（明确不改） | 已完成的 P0001–P0013、T0001–T0012、旧 benchmark 输出与旧 session checkpoint 不回写；读取时以 `.get(..., default)` 兼容 |
| repo-wide search terms | `observations|tensions|association_candidates|hypotheses|plan|evidence|verification_checks|cipher_reference_hints|decode_bacon|renderAgentStatus|sudoku-confirm-cell` |

## 3. 验证方式

### 3.1 数独交互

- 构造 9×9 识别确认盘，焦点从 R5C5 依次按四个方向键，断言落到相邻坐标且格值不变。
- 在 R1C1 按上/左、R9C9 按下/右，焦点保持原格；不环绕。
- 断言 Tab/Shift+Tab 未被 handler 阻止，数字输入、删除和冲突标红仍工作。
- 在真实浏览器可用时补桌面键盘 smoke；若宿主浏览器不可用，明确记为 NOT CHECKED，不以静态文本代替。

### 3.2 通用推理与工具

- **例题正例**：标题/正文触发 Bacon reference；模型提出 `啊→A、卟→B、吧→BA` 后，工具证明 7 组均为
  五位；26 字母版得到 `SINKING`，答案长度 7、题面覆盖和可重放性通过；24 字母版作为被否决替代保留。
- **Bacon 近似反例**：保留“培根”关键词，但至少一组无法在同一映射下满足五位；不得输出确定答案。
- **无关键词结构例**：不给密码名，只给足以形成固定宽度预测的载荷；允许形成候选，但只有查表/工具与
  holdout 全部通过才升级为证据。
- **非 Bacon 泛化例**：一个 token 展开为多个方向或点划基础符号，使用相同 `expand_symbol_groups` 验证固定
  宽度/字符集，再交给另一确定性 decoder；证明工具没有写死 A/B 或中文 token。
- **歧义例**：两种 mapping 或 codebook variant 都满足机械约束，且题面无额外区分信号；必须返回
  `NEEDS_REVIEW` 并展示双方证据。
- **关键词假阳性**：标题出现食物意义的培根、正文没有相符载荷；reference 只作为 hint，不能产生答案。

### 3.3 回归和证据等级

- RED→GREEN 运行聚焦的 ToolRegistry、complex domain/graph/session、Web API/前端检查。
- 运行全量 `python -m unittest discover`、三个前端脚本 `node --check`、`git diff --check`。
- 使用 offline/scripted provider 验证控制流，不冒充真实模型会自主发现映射。
- 至少一次真实 DeepSeek 例题/泛化对照属于付费评测，必须获得单独授权；没有该证据时 overall model quality
  保持 `unknown`，不能宣称“Agent 已经更聪明”。

## 🔴 红线 / 风险

- **过拟合**：不得在 prompt、工具或代码中写入 `啊/卟/吧`、`SINKING` 或例题专属 mapping；测试 fixture
  可以包含题面，但生产实现只能依赖通用 schema、显式 mapping 和 invariant。
- **伪推理**：可视 trace 必须由 state/tool evidence 派生，不允许最后让模型另写一篇看似合理的故事。
- **无界搜索**：工具不枚举 token→字符串的组合，不按词典穷举答案；模型最多提出 4 个有依据的候选。
- **可读性偏见**：英文成词不是唯一性证明；机械约束、题面信号和格式必须独立成立。
- **调用成本**：推荐方案不新增阶段调用；如果实施发现现有阶段无法稳定生成表示假设，先记录证据并回到用户，
  不擅自加第九次调用。
- **兼容性**：新 state 字段必须有默认值，旧 checkpoint/session 能读取；不能为了 schema 清理旧状态。
- **外部动作**：本 plan 不授权真实付费 DeepSeek、push、merge、release 或部署到公网。

## 4. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | Web Sudoku | 数独确认网格支持四方向键移动；边界不环绕，值不改变，Tab/数字/删除保持原行为 |
| A02 | yes | Complex state | 普通谜题 state 持久化显式答案约束和有来源、预测、证伪条件的表示假设；不存在例题专属生产规则 |
| A03 | yes | ToolRegistry | 通用 token expansion 工具可重放逐组展开并机械验证宽度/字符集；不猜映射、不无界枚举 |
| A04 | yes | Cipher variants | Bacon 24/26 变体均可显式调用并返回 provenance；工具不替 Agent 选择“更像单词”的结果 |
| A05 | yes | Runtime gate | 未通过展开不变量、显式答案格式或唯一性验证时不能 `SOLVED`；歧义结果进入 `NEEDS_REVIEW` |
| A06 | yes | Web general | 玩家能看到“看到/联想/查表/验证/接受或停下”的证据轨迹以及失败替代项，不暴露隐藏思维链 |
| A07 | yes | Robustness suite | 提供例题正例、Bacon 近似反例、无关键词结构例、非 Bacon 展开例、歧义例、关键词假阳性六类测试 |
| A08 | yes | Regression | 不增加正常路径 LLM 调用数；旧 session 缺新字段可读；现有测试、JS syntax 与 diff check 全部通过 |
| A09 | conditional | Overall model | 只有另获付费调用授权并在例题及至少一个非 Bacon 盲测上成功，才可声明真实模型发现能力提升；否则记 unknown |

## 5. 成稿自审记录

- 日期 / 审核者：2026-10-03，Codex 主执行者自审。
- 实际上下文 / 能力降级原因：当前宿主规则禁止在用户未明确要求时启动 subagent，因此无法使用独立
  fresh-context reviewer；主执行者在首次成稿后从文件完整重读，未依赖写作中记忆代替审核。
- 被审版本：基线 `ec22f1c` 上的本 draft 全文，排除本自审记录自身。
- 维度结论 / 证据：
  - 意图与范围：同时覆盖用户明确提出的数独键盘操作和普通谜题推理升级；实施、付费调用与发布边界清楚。
  - 事实与假设：现状均落到当前 Web/graph/reference 实现；preflight 在 fresh fetch 后仍报告 remote unknown，
    另用 `git rev-list` 与 `merge-base` 确认 `origin/main` 为 HEAD 祖先、结果为 `0 behind / 5 ahead`。
  - 方案与步骤：优先复用八阶段图，不增加模型调用；通用表示工具与 Bacon 领域 decoder 分层，下一位执行者
    无需猜测数据流、失败语义或测试样例。
  - 影响范围：state、stage contract、tool registry、cipher SSOT、offline provider、Web consumer、旧 checkpoint
    和机械检查均已进入 impact map；历史计划/结果明确不改。
  - 风险与恢复：过拟合、伪推理、无界搜索、可读性偏见、调用成本与兼容性均有 fail-closed 边界；新增字段
    使用默认值，单个工具或 UI 子项可独立回退。
  - 验证与验收：A01–A09 覆盖交互、工具、状态、机器门、UI、泛化反例和证据等级；真实模型能力没有用 mock
    冒充，付费盲测保留 conditional。
  - 授权与冻结：成稿自审时仅获准提交既有基线和创建草案；用户随后于 2026-10-03 批准实施并要求
    session-alive 无人值守执行，正文自实施开始冻结。
- 完整 findings / 处理 / 修订后复核：
  - 非阻断：例题出现在 schema 示例与测试设计中，存在被误读为生产常量的风险；已由“红线”明确禁止在
    prompt/工具/代码写入例题 token 或答案，并以非 Bacon/假阳性/歧义样例作为必需验收。
  - 非阻断：24 字母 Bacon 码表必须在实施时从权威定义核对，不能从示例输出反推；已要求资料、网页和 Agent
    共用同一 SSOT，并让变体显式返回 provenance。
  - 非阻断：当前环境的浏览器控制通道可能不可用；已要求行为测试与真实浏览器 smoke 分级，后者不可用时
    必须记 NOT CHECKED，不能用字符串断言冒充。
  - 修订后复核：上述三项均有具体边界和验收承接，无需改变目标或方案。
- 最终结论 / 剩余 blocker / 局限：成稿自审通过，用户已批准实施。没有实施 blocker；真实 DeepSeek 是否能
  自主提出高质量表示假设仍需另获付费盲测授权，在此之前只能证明流程和工具能力。

> 执行开始后本 plan 正文冻结；实际偏差只写配对 task。

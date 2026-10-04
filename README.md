# Puzzle Solving Agent

一个面向 PuzzleHunt、纸笔谜题和古典密码题的本地解谜 Agent。它既能用 DeepSeek 观察、提出假设和验证答案，也把重复而可验证的部分交给确定性脚本；核心原则是：**模型负责理解与归纳，程序负责约束、重放和失败关闭。**

如果你第一次接触这个仓库，从本页顺序阅读即可。若你准备把项目交给 Codex，请让它先读本 README，再按“给 Codex 的接手入口”继续。

## 一分钟认识项目

| 能力 | 用户看到什么 | 谁在做推理 | 是否需要 DeepSeek |
|---|---|---|---|
| 统一文字/图片入口 | 上传题面，确认模型识别结果，再进入对应组件 | DeepSeek 只做输入规范化；用户可修正 | 是 |
| 普通谜题 Agent | “看到什么 → 联想到什么 → 查了什么 → 怎么验证 → 为什么接受或停下” | 多阶段 Agent + 确定性工具 + 机器终局门 | 是；离线 scripted demo 除外 |
| 数独 | 可编辑盘面、下一步提示或完整基础推理、逐步解释 | 裸单和行/列/宫隐单脚本 | 图片识别需要；求解器不需要 |
| 数织 Nonogram | 行列线索确认、合法排列交集和逐步涂格 | 确定性行列传播 | 图片识别需要；求解器不需要 |
| 按规则推理 | 同时提交题目与规则，Agent 先自研受限解法，再执行 | DeepSeek 合成白名单约束；通用引擎执行 | 方法合成需要 |
| 古典密码 | Caesar、Bacon、ASCII、A1Z26、盲文、旗语等检索和转换 | 本地密码表与确定性工具 | 页面工具不需要 |
| 扫雷 | 可直接玩的本地小游戏和不猜测的逻辑提示 | 服务端权威棋盘 + 确定性提示 | 不需要 |
| 研究与评测 | 原创 benchmark、节点证据、replay、oracle 隔离 | 离线 evaluator；真实 benchmark 显式 opt-in | 默认不需要 |

项目不是“把所有题都扔给一个大模型”。它明确区分四种证据身份：

- **真实 DeepSeek**：图片识别、未知规则的方法归纳、普通复杂题推理；会产生 API 调用。
- **确定性组件**：密码转换、数独、数织、规则约束传播、replay；同输入得到同结果。
- **scripted/fake provider**：只证明调用协议和流程，不证明真实模型会解题。
- **互动游戏**：扫雷由玩家操作，不冒充自动求解器。

## 五分钟启动本地 Web

要求 Python 3.11+。推荐在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[web]"
cp .env.example .env.local
```

编辑 `.env.local`，至少填入自己的 Key：

```dotenv
DEEPSEEK_API_KEY=replace-with-your-api-key
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_VISION_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

也可直接使用已被 `.gitignore` 排除的项目根 `.env`。加载优先级为：进程环境 > `.env.local` > `.env`；两种文件都不得提交真实 Key。

启动：

```bash
.venv/bin/puzzle-agent web --port 8000
```

打开 `http://127.0.0.1:8000`。无需登录，服务只允许监听 `127.0.0.1` 或 `localhost`。不要把这个本地模式直接暴露到公网。

三个页面：

- `/`：文字/图片提交、识别确认和推理过程。
- `/paper-puzzles`：数独、数织、按规则推理和本地扫雷。
- `/cipher-tools`：密码检索、转换表、猪圈示意、盲文和旗语。

没有配置 Key 时，题目规范化入口会明确显示不可用；密码工具和扫雷仍可本地使用。真实图片识别和真实 Agent 推理可能产生费用，自动测试不会偷偷调用 DeepSeek。

Windows PowerShell 使用 `.venv\Scripts\python.exe` 和 `.venv\Scripts\puzzle-agent.exe` 替换上面的 `.venv/bin/...`。

## 推荐演示路线

完整示例索引见 [`examples/README.md`](examples/README.md)。下面这条路线适合第一次向同事演示。

### 演示 1：零费用验证基础 Agent

```bash
.venv/bin/puzzle-agent solve --file examples/sample_puzzle.json --offline
.venv/bin/puzzle-agent ciphers --text uryyb --limit 5
```

观察点：第一个命令走本地离线 provider；第二个命令会列出 ROT/Caesar 等确定性候选。它们适合检查安装，不代表真实 DeepSeek 的复杂解题能力。

### 演示 2：图片识别 → 可视化校对 → 数独下一步

1. 打开首页，题目类型选择“普通数独”。
2. 选择“只提示下一步”。
3. 上传 [`sudoku-9x9-image/puzzle.png`](examples/paper-puzzle-demos/sudoku-9x9-image/puzzle.png)。
4. 在可视化表格中核对数字；可用方向键移动光标。
5. 确认后观察 Agent 只填一个确定数，并解释候选如何缩成唯一值。

这个演示的图片识别需要真实 DeepSeek；后半段数独推理是确定性脚本。示例本身就是标准 9×9、留空 55 格的题目，宫边界用粗线显示；OCR 重复数字会先标红让用户修正。完整求解包含裸单与行、列、宫隐藏单，不使用搜索或回溯。

### 演示 3：数织的行列传播

1. 题目类型选择“数织”。
2. 上传 [`nonogram-10x10-image/puzzle.png`](examples/paper-puzzle-demos/nonogram-10x10-image/puzzle.png)。
3. 核对行列线索后开始推理。

观察点：10×10 题面同时含整行、长段和多段提示；步骤会显示是哪条线、多少种合法排列共同确定了哪些格，并经过约 40 次横纵传播完成。

### 演示 4：题目带规则，Agent 先自研解法

以 [`futoshiki-5x5-rules`](examples/paper-puzzle-demos/futoshiki-5x5-rules/) 为例：

1. 首页选择“按规则推理”。
2. 上传 `puzzle.png`，把 `rules.txt` 的内容粘贴到题目文字。
3. 选择“只演示下一步”或“执行完整确定性推理”。
4. 核对模型提取出的规则、格子和线索引用。
5. 确认后观察方法摘要及每次候选域变化。

Agent 不能生成并执行任意代码。首版只允许 `all_different`、`less_than`、`sum_equals`、`visibility` 四类约束；规则覆盖、引用、候选预算、trace replay 和终局约束任一不通过都会失败关闭。

同目录还提供：

- [`kakuro-3x3-cross-sums`](examples/paper-puzzle-demos/kakuro-3x3-cross-sums/)：六组交叉和值约束。
- [`skyscrapers-4x4-rules`](examples/paper-puzzle-demos/skyscrapers-4x4-rules/)：无给定格的楼房可见数与行列互异。

五道纸笔题均可完全离线复算：

```bash
.venv/bin/python -m unittest tests.test_paper_demo_examples -v
```

该测试证明图片文件有效、保存的规范化输入可求解、结果可重放；它不冒充真实 DeepSeek 图片识别测试。

### 演示 5：复杂 Agent 的持久状态

```bash
.venv/bin/puzzle-agent session init --file examples/sample_puzzle.json --max-calls 10
.venv/bin/puzzle-agent session run <上一步返回的-session-id> --offline
.venv/bin/puzzle-agent session status <session-id>
.venv/bin/puzzle-agent session history <session-id>
```

观察点：session 保存阶段状态和历史，能够逐步执行、暂停补 artifact、恢复、从 checkpoint 分叉，并且只有通过机器验证的 `SOLVED` 才能 finalize。`--offline` 使用 scripted provider，只用于体验流程。

### 演示 6：无需模型的互动和工具页面

- 打开 `/paper-puzzles` 玩扫雷；首次点击安全，逻辑提示只给可证明结论。
- 打开 `/cipher-tools` 搜索“培根”“ASCII”“盲文”“旗语”等关键词，或查看 Caesar 全移位和数制转换。

## Agent 如何工作

普通复杂题使用可恢复的多阶段状态图：

```text
输入完整性检查
  → 观察与分类
  → 本体/主题联想
  → 子题物化与局部验证
  → 竞争假设与有界工具实验
  → 证据评价
  → 中间载体验证
  → 最终答案验证
  → SOLVED / NEEDS_REVIEW / EXHAUSTED / BLOCKED_INPUT
```

系统不保存或展示模型的私有思维链，只保留协作所需的观察、假设、工具调用、证据、反例、未解决项和简短解释。Web 按证据引用顺序展示确定性工具输入/输出与已验证中间结果，并在醒目结论栏区分“答案是”“可能答案是”和“未得出有效答案”；尚未通过核验的中间结果和答案候选会明确标注为待核验。

几个重要边界：

- 标题或关键词只负责路由，不直接证明机制。
- 工具候选或“像单词”不等于答案，必须通过来源和终局验证。
- 搜索/查询是 lookup，不单独证明答案。
- 数独、数织和规则传播固定点停滞时会诚实返回 `STALLED`，不会暗中猜解。
- 缺图片、表格或上游答案时返回 typed blocker，不用幻想补齐。
- 非流式 DeepSeek 请求无法在网络中途安全撤回；“终止推理”会阻止请求返回后的后续节点。

详细运行契约见 [当前架构](haiknow-doc/docs/01-puzzle-agent-architecture.md)，设计动机见 [Agent 设计学习日志](haiknow-doc/docs/02-agent-design-journey.md)。

## 三种运行入口

| 入口 | 适合场景 | 安装方式 |
|---|---|---|
| Web | 新用户、图片题、纸笔谜题、可视化过程 | `pip install -e ".[web]"` |
| simple CLI | 单题快速求解、密码候选、最小依赖 | `pip install -e .` |
| complex CLI | 持久 session、checkpoint、artifact、分叉、benchmark | `pip install -e ".[complex]"` |

常用命令：

```bash
puzzle-agent --help
puzzle-agent web --help
puzzle-agent solve --help
puzzle-agent ciphers --help
puzzle-agent session --help
puzzle-agent benchmark --help
```

基础包保持零第三方运行时依赖；Web extra 包含 FastAPI、Uvicorn、Pillow 以及 complex runtime。

## 示例与数据地图

| 路径 | 用途 | 是否含答案 |
|---|---|---|
| [`examples/sample_puzzle.json`](examples/sample_puzzle.json) | 最小 CLI 安装与 ROT13 smoke | 输入不直接写答案 |
| [`examples/paper-puzzle-demos/`](examples/paper-puzzle-demos/README.md) | 五道运营纸笔演示，含 PNG、规则、程序、结果和讲解 | 是，作为离线演示 fixture |
| [`examples/general-puzzle-demos/`](examples/general-puzzle-demos/README.md) | 三道原创 CCBC 风格普通题，含图片、稳定文本输入、oracle、工具轨迹和分层讲解；测试展示须用 `puzzle.txt`，图片识别不保证成功 | 是，作为离线工具复演 fixture |
| `benchmarks/derived/` | 原创 dev/blind PuzzleHunt cases | input 与 oracle 物理隔离 |
| [`benchmarks/reasoning-curriculum-v1.json`](benchmarks/reasoning-curriculum-v1.json) | 七类鲁棒性风险课程 | 不含答案 |
| [`research/ccbc16/`](research/ccbc16/) | 从 CCBC 研究蒸馏出的机制卡和方法论 | 不作为运行时答案库 |
| `research/*.html` | 原始离线研究报告 | 研究证据，不进入生产 prompt |

CCBC 资料用于学习通用方法，不把官方题面/题解直接交给模型。派生 benchmark 更换主题、数据和答案，并在 runtime 与 evaluator 之间隔离 oracle。

## 给 Codex 的接手入口

当本 README 被交给 Codex 时，按以下顺序建立项目上下文：

1. 读取当前生效的 `AGENTS.md` 指令；若仓库内另有 `AGENTS.md`，再应用最近作用域规则。随后执行 `haiknow project resolve "$PWD"` 判断本项目是否启用 HAiKnow。
2. 阅读本 README，确认用户要改的是 Web、通用 Agent、确定性工具、纸笔组件、benchmark 还是文档。
3. 阅读 [`haiknow-doc/docs/index-by-topic.md`](haiknow-doc/docs/index-by-topic.md)，只进入与任务相关的 current 文档。
4. 行为或架构改动前阅读 [`01-puzzle-agent-architecture.md`](haiknow-doc/docs/01-puzzle-agent-architecture.md)；推理策略改动再读 [`02-agent-design-journey.md`](haiknow-doc/docs/02-agent-design-journey.md)。
5. 演示相关任务先读 [`examples/README.md`](examples/README.md)、纸笔 [`manifest.json`](examples/paper-puzzle-demos/manifest.json) 和普通题 [`manifest.json`](examples/general-puzzle-demos/manifest.json)，不要重新发明 fixture。
6. 修改前检查 `git status`，保留用户已有改动；修改后运行与影响面匹配的测试和文档检查。

代码地图：

| 路径 | 责任 |
|---|---|
| `src/puzzle_agent/web/` | 无登录本地 Web、安全门、页面和 API |
| `src/puzzle_agent/intake/` | 图片/文字规范化合同与确认回执 |
| `src/puzzle_agent/paper_puzzle/` | Sudoku、Nonogram、Minesweeper、rule-based 组件与 gateway |
| `src/puzzle_agent/complex_graph.py` | 多阶段 Agent 节点、条件边与机器门 |
| `src/puzzle_agent/complex_session.py` | checkpoint、恢复、分叉、终止和 finalize |
| `src/puzzle_agent/tool_registry.py` | 通用确定性 PuzzleHunt 工具 |
| `src/puzzle_agent/cipher_workbench.py` | 古典密码转换核心 |
| `src/puzzle_agent/cipher_reference.py` | 密码搜索资料与 Web 转换表 |
| `.agents/skills/` | 项目内 Codex 推理 Skill；只引用 canonical runtime |
| `tests/` | 行为、回放、安全边界和 Web journey 回归 |

建议 Codex 先运行：

```bash
git status -sb
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
for file in src/puzzle_agent/web/static/*.js; do node --check "$file" || exit 1; done
git diff --check
```

除非用户明确授权，Codex 不应：调用付费 DeepSeek benchmark、启动 24 小时 scheduler、push/merge、公开部署本地 Web、执行 destructive Git 操作，或把 fake/scripted provider 的通过描述成真实模型能力。

## 开发验证

完整离线回归：

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
```

纸笔演示资产：

```bash
.venv/bin/python -m unittest tests.test_paper_demo_examples -v
.venv/bin/python scripts/generate_paper_demo_images.py
```

测试默认完全离线。只有显式使用真实 provider，例如 `benchmark run --provider deepseek`、`cycle schedule --provider deepseek` 或 Web 提交题目，才会调用 DeepSeek。

## 进阶能力入口

- CLI artifact、history、branch、finalize：运行 `puzzle-agent session --help`，并参考 [当前架构](haiknow-doc/docs/01-puzzle-agent-architecture.md)。
- 原创 dev/blind benchmark：运行 `puzzle-agent benchmark --help`。
- 周期评测和一次性 hard set：运行 `puzzle-agent cycle --help`；这类真实模型任务可能高费用，默认不要启动。
- Git 自动发布器：运行 `puzzle-agent automation --help`；它有独立 allowlist、secret scan 和工作树稳定门，不是普通开发的必需步骤。
- CCBC 推理方法：阅读 [TRACE-LIFT](research/ccbc16/methodology.md) 与 [HA-BRIDGE](research/human-association-reasoning.md)。

## 文档入口

- [项目知识索引](haiknow-doc/docs/index-by-topic.md)：按“第一次了解、开发修改、推理研究、历史追溯”路由。
- [当前架构与运行契约](haiknow-doc/docs/01-puzzle-agent-architecture.md)：当前行为的权威说明。
- [Agent 设计学习日志](haiknow-doc/docs/02-agent-design-journey.md)：为什么形成现在的架构。
- [纸笔谜题演示题库](examples/paper-puzzle-demos/README.md)：运营演示和离线复算。
- [普通谜题中等难度演示](examples/general-puzzle-demos/README.md)：三种分层机制、图片题面、独立 oracle 与工具轨迹。
- [CCBC16 标准推理轨迹](haiknow-doc/docs/03-ccbc16-24-case-solution-guide.md)：复杂题研究材料。

历史 plan/task 用于追溯决策与实施证据，不应替代上述 current 文档。完整历史路由见项目知识索引。

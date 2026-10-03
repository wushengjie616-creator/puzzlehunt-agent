# Puzzle Solving Agent

一个同时提供 CLI 与本地 Web 界面的 PuzzleHunt 解题 Agent。无需账号即可在本机提交文字或题面图片；Web
入口会强制先用 DeepSeek 规范化输入，再交给通用 Agent 或纸笔谜题组件。

## 本地 Web 与普通数独

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[web]"
.venv/bin/puzzle-agent web --port 8000
```

打开 `http://127.0.0.1:8000`。服务只允许监听 `127.0.0.1` / `localhost`，无需登录；每次启动会生成仅供
当前页面使用的本地 capability token，并同时校验 Host、Origin 和 JSON Content-Type。不要用反向代理把该
模式直接暴露到公网。

本地站点包含三个入口：

- `/`：文字/图片题目提交、DeepSeek 规范化确认和解题过程；
- `/paper-puzzles`：数独、数织、按规则推理入口和可直接游玩的本地扫雷；
- `/cipher-tools`：古典密码搜索库、凯撒全移位、培根、猪圈图、盲文、旗语、ASCII、A1Z26 与二/三/十进制转换。

页面接受文字、点击选择或拖拽加入的 PNG、JPEG 或 WebP（单图最大 10 MiB），所有输入都必须经过 `deepseek-flash` 的
`NORMALIZE_INPUT` 阶段。识别结果必须先由用户编辑、确认，随后服务端签发绑定 source、模型 envelope 与
canonical input hash 的短期回执；直接调用 session API 不能绕过该阶段。API Key 始终只在服务端。

题目入口可明确选择自动识别、普通谜题、普通数独、数织或“按规则推理”；从纸笔子页面进入会预选相应组件。显式选择会作为
`preferred_kind` 交给 DeepSeek，模型返回不同题型时失败关闭，避免数独误入通用 Agent。选择数独后还可选
“只提示下一步”或“使用基础技巧完整做完”。

确认识别结果时不显示 JSON：数独使用可直接修改的 N×N 棋盘，并按宫边界绘制粗线；数织使用逐行、逐列
线索表；规则题显示规则、实体值和线索引用；普通谜题使用文本编辑框。页面把修改结果重新组装为 canonical input，再交给同一服务端校验与
确认回执流程。若数独 OCR 在同一行、列或宫内抄出重复数字，识别结果仍会进入该棋盘，并把冲突格标红；
玩家修正后才可通过严格确认，不会把冲突盘面交给解题器。数独确认格支持方向键在相邻格间移动，边界不
环绕；数字、删除和 Tab 仍使用浏览器原生输入行为。

普通 9×9 图片识别会要求模型忽略截图中的日期、计时器、数字键盘等界面元素，只抄录盘内已知数且不预先
解题。若模型仅把 1–9 或空格写成字符串、`0`、`.` 等无歧义 JSON 形式，normalizer 会确定性转换为整数与
`null`，并在 warnings 中提醒玩家逐格核对。行列尺寸、未知符号等结构错误在识别阶段失败关闭；重复数字
或候选矛盾作为可修正警告进入确认页，若未修正则在确认阶段失败关闭。

纸笔谜题专区目前提供普通数独、数织、按规则推理解法器和本地互动扫雷。数独组件支持标准 9×9，以及显式提供宫结构的其他 N×N；它只应用
裸单和行/列/宫隐单，记录候选数、中文观察说明、依据和前后状态指纹，并可从 givens 重放。单步模式找到首个
确定数后返回 `STEP_LIMIT`；基础技巧不够时才返回 `STALLED` 和 `UNVERIFIED_ADVISORY`。两种模式都绝不
搜索、回溯或猜数。

扫雷不是自动求解器，而是服务端权威棋盘的本地小游戏：支持初级 9×9/10 雷、中级 16×16/40 雷和高级
16×30/99 雷；首次翻格安全，支持零区展开、右键插旗、双击数字 chord、计时、胜负、重开和刷新恢复。
“逻辑提示”只读取玩家已经看到的数字，返回一个可证明安全/必为雷的格子或 `STALLED`，不会自动操作，
也不会调用 DeepSeek。游戏仅保存在当前 Python 进程内；服务重启后重新开局。

数织组件接受 `row_clues`、`column_clues` 和可选的预填 `grid`（`null` 未知、`1` 黑格、`0` 空格）。
它逐行、逐列生成与当前状态兼容的合法区段排列，只填入所有排列共同确定的黑格或空格，并记录 line、线索、
兼容排列数、变更格和前后状态指纹供重放验证。组件不做整盘搜索、回溯或猜格；固定点未完成时返回
`STALLED`，Agent 建议只能标记为 `UNVERIFIED_ADVISORY`，不能直接改盘。

“按规则推理”用于题型未预先注册、但玩家同时提供明确规则和题面的纸笔题。`NORMALIZE_INPUT` 只保真整理
规则、整数符号、实体和可见线索；用户确认后，独立的 `METHOD_SYNTHESIS` 调用只能组合
`all_different`、`less_than`、`sum_equals`、`visibility` 四类白名单约束。确定性引擎随后反复缩小候选域，
记录规则/线索来源、候选变化和前后指纹，并支持“下一步”与完整模式。模型生成的 Python、JavaScript、
shell 或表达式不会被执行；全规则/线索覆盖、局部候选预算、trace 重放和终局逐约束复核任一不通过都会失败关闭。
首版可表达不等式数独、基础交叉和值和摩天楼，但不代表能处理任意图形或任意自然语言规则。

原创运营演示题位于 [`examples/paper-puzzle-demos/`](examples/paper-puzzle-demos/README.md)：首批五题均提交
PNG、规则、source、program、expected result 和 walkthrough，并由测试离线复算。图片上传的真实识别效果
仍取决于 DeepSeek；默认测试不发起付费调用。

真实图片识别会产生 DeepSeek 调用费用；默认测试使用 fake provider，本地验收不包含未经单独授权的
付费视觉冒烟。若未配置 `DEEPSEEK_API_KEY`，首页会在提交前显示不可用原因并禁用规范化按钮，不会绕过
模型。复制 `.env.example` 为 `.env.local`、填入 Key 并重启服务即可加载；配置状态不验证余额、网络或
Key 是否有效，实际调用错误仍会在题目进度中显示。

项目另有两种 CLI 运行方式：

- **simple mode**：零第三方运行时依赖；先按题面关键词索引相关古典密码规则，再运行本地常见密码候选，最后进行一次 DeepSeek 单轮请求。
- **complex mode**：可选 LangGraph/SQLite runtime；按观察、联想、子题物化、表示假设、工具实验、证据评价和答案验证进行多次独立 DeepSeek 单轮请求。关键词命中会写入紧凑资料提示，Agent 可按需调用完整密码对照表，并支持暂停、恢复、历史和分叉。

Web 中运行通用复杂 Agent 时会显示“终止推理”。点击后浏览器立即停止等待，服务端在当前 DeepSeek
请求返回后阻止后续节点，并把 session 持久标记为 `CANCELLED`。非流式在途请求无法安全强杀或撤回，
因此终止可能需要等待当前单次请求结束，但不会继续产生下一轮模型调用。

普通谜题完成或安全停下后，Web 从持久 state 展示“看到什么、联想到什么、查了什么、怎么验证、为什么
接受或停下”五段短证据链。该视图只显示观察、显式假设、工具结果和机器门，不生成事后补写的隐藏思维链。

## 安装

要求 Python 3.11+。

基础模式保持零依赖：

```powershell
python -m pip install -e .
puzzle-agent solve --file examples/sample_puzzle.json --offline
puzzle-agent ciphers --text uryyb --limit 5
```

复杂模式建议放在项目虚拟环境中，避免 LangGraph 的 Pydantic 依赖影响共享 Python：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[complex]"
.\.venv\Scripts\puzzle-agent.exe --help
```

## DeepSeek 配置

CLI 自动读取当前工作目录的 `.env.local`。该文件已被 `.gitignore` 排除：

```dotenv
DEEPSEEK_API_KEY=replace-with-your-api-key
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_VISION_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

shell 环境变量优先于 `.env.local`。只允许上述四个 `DEEPSEEK_*` 键；Key 不写入 checkpoint、事件、prompt dump 或错误正文。

当前 DeepSeek 适配器使用：

- `POST https://api.deepseek.com/chat/completions`
- thinking enabled，reasoning effort `high`
- JSON Object 输出，非流式
- 每个 graph LLM node 恰好一次独立请求；非法 JSON 不自动重试，也不猜补内容，而是带指纹安全终止为 `NEEDS_REVIEW`

## 复杂 Session 快速体验

创建一个题目文件：

```json
{
  "title": "Shift",
  "flavor_text": "Move thirteen",
  "content": "uryyb",
  "required_artifacts": []
}
```

然后运行：

```powershell
$pa = ".\.venv\Scripts\puzzle-agent.exe"

& $pa session init --file puzzle.json --max-calls 10
& $pa session run <session-id> --offline
& $pa session status <session-id>
& $pa session history <session-id>
& $pa session finalize <session-id>
```

`--offline` 使用确定性的 staged provider，不访问网络，适合体验状态图；它不能证明真实模型可以解决复杂谜题。去掉 `--offline` 才会调用 DeepSeek。

complex mode 的非阻塞流程至少包含四个独立推理节点：

```text
OBSERVE_CLASSIFY
  → ASSOCIATE_THEME
  → MATERIALIZE_SUBPROBLEMS
  → VALIDATE_SUBPROBLEMS
      └─ semantic coverage < 50% and six calls remain
         → PREPARE_SEMANTIC_REFINEMENT
         → MATERIALIZE_SUBPROBLEMS → VALIDATE_SUBPROBLEMS  # at most once
  → HYPOTHESIZE_PLAN
  → deterministic tool dispatch
  → EVALUATE_EVIDENCE
  → VERIFY_INTERMEDIATES
  → VERIFY_ANSWER
```

第一次局部验证覆盖不足一半时，complex mode 会在工具规划前使用唯一一次语义恢复轮：已有 supported 值是不可改写锚点；首轮全空时只补 1–3 个高杠杆候选。该路径固定占用十次模型节点，因此之后不再进入第二轮 tool replan。明确的 TLS、连接中断或不完整 HTTP body 会从同一 checkpoint 最多重试一次。非法 JSON/非对象响应不重试，记录长度与摘要指纹后安全终止；恢复轮中引用未知子题的结果会被丢弃，无 signal 或缺少执行契约的计划项也会被丢弃。所有这类机器归一化都会留下 blocker，禁止终局误报 `SOLVED`。

也可以逐节点学习和调试：

```powershell
& $pa session step <session-id> --offline
```

### CLI 中缺失图片或表格

传统 complex CLI 的 artifact 流程仍以文本转写为主；Web 入口已经可以用 DeepSeek Vision 读取题面图片。
CLI 题目可以声明必须转写的 artifact：

```json
{
  "content": "按图中路径读取",
  "required_artifacts": ["grid"]
}
```

运行到缺失点时状态会成为 `BLOCKED_INPUT`，不会调用模型。补充文本转写后恢复：

```powershell
& $pa session add-artifact <session-id> --name grid --file grid.txt --offline
```

### 历史、分叉和最终确认

```powershell
& $pa session history <session-id>
& $pa session branch <session-id> --checkpoint <checkpoint-id>
& $pa session finalize <session-id>
```

只有 `SOLVED` 状态可以 finalize。session 数据位于 `.puzzle-agent/sessions/<id>/`，包括 SQLite checkpoint、不可变初始输入、`events.jsonl`、artifact 转写和 `final.json`。

`branch` 会同时复制所选 checkpoint 的公开 state 与 LangGraph 执行游标；分支随后从该 checkpoint 的下一节点继续，不会从 `INTAKE` 重跑。对于只有一个原子子题、局部语义结果和确定性工具结果完全一致的题，`VERIFY_INTERMEDIATES` 可记录受机器门约束的 direct-answer 路径；复杂题仍必须提供与最终答案不同的中间载体。

## 确定性工具

密码工作台包括：

- Caesar/ROT、Atbash、Base16/32/64、二进制、Morse、A1Z26、现代 26 字母培根与十进制 ASCII
- Vigenère（显式 key）、Rail Fence、反转、奇偶位、首尾字母

Web 密码资料库另外提供猪圈密码的位置/点位对照。猪圈图形跨字体且存在变体，因此本期不把任意 Unicode
符号自动映射成字母；页面会提醒先用题面重复符号验证字母表方向。培根资料与 Agent 工具共享现代 26 字母
和古典 24 字母（I/J、U/V 合并）两个显式变体；工具从不根据“像单词”自动选择。资料页使用桌面 10 列、窄屏 5 列的紧凑格；猪圈卡
包含 GPT 生成的纯黑白 A–Z 示意图，盲文以六个黑白点显示 A–Z 和 0–9，旗语以面对发信者的双臂八方向图
显示 A–Z。凯撒和栅栏保留规则说明，不再重复显示冗长对照表。

complex tool registry 还包括：

- `extract_nth`：逐行索引提取
- `anagram_delta`：多重集合字母差
- `read_grid_path`：带边界和四邻接验证的网格路径
- `dependency_order`：meta/子题 DAG 拓扑排序和循环检测
- `caesar_shift`、`atbash_transform`、`base_decode`、`morse_decode`：显式参数的经典密码转换
- `vigenere_decode`、`rail_fence_decode`：只接受已知 key/栏数，不进行无界猜测
- `a1z26_decode`、`interleave_sequences`：显式参数的基础恢复与提取
- `grid_trace`、`grid_transform`、`constrained_order`：方向路径、版式变换和有限排序约束
- `decode_bit_patterns`、`repair_mojibake`、`common_symbol_intersection`：表面二态、严格可逆编码修复和不变量
- `bounded_mojibake_scan`：固定编码对、最多两层、严格 round-trip 的无评分乱码修复候选
- `minesweeper_propagate`：只做确定性八邻域传播的有界扫雷推理，不猜测或回溯
- `phone_keypad_decode`、`braille_decode`、`playfair_codec`：九键、六点盲文和 5×5 双字母密码
- `decode_token_morse`、`solution_position_analysis`：自定义视觉 token 摩斯与多解逐位差异/不变量
- `palindrome_mismatch`、`unicode_inspect`：回文错位提取与易混 Unicode 码位审计
- `expand_symbol_groups`：按显式 token→载荷映射逐组展开，并检查宽度和允许字符集，不猜映射
- `decode_bacon_groups`：显式选择 `modern26` 或 `classic24`，逐组返回码值、字母和 provenance

工具结果只是 evidence；候选分数不等于答案证明。未知工具和错误参数会记录为失败 attempt，不会冒充成功结果。

## CCBC16 学习与派生测试集

CCBC16 只作为离线方法学习来源，不会把官方题面或题解交给 DeepSeek。项目流程是：

当前蒸馏结果见 [TRACE-LIFT 方法论](research/ccbc16/methodology.md) 和 [49 道非-meta机制卡](research/ccbc16/mechanism-cards.md)；来源 ledger 只保存官方 URL 与抽象机制标签，不保存批量原文。

```text
阅读官方题目/题解
  → 提炼抽象 MechanismGraph
  → 更换主题、数据和答案重新出题
  → 独立 oracle/rubric
  → input/oracle 隔离与泄漏检查
```

当前包含 8 个原创 dev case 和 2 个原创 blind case，覆盖对象映射、异常联想图、子题 DAG、缺信息反推、逆向提取、递归 meta、机制回调、约束组合、分层提取和 artifact gate。另有
`benchmarks/reasoning-curriculum-v1.json` 保存不含答案的鲁棒性课程：关键词假阳性、缺 artifact、版本冲突、
多解不变量、中间指令、未消费线索和 title/flavor ablation。推理评测将 discovery、mechanism、extraction、
verification 分开计分；只有答案而没有证据链会标记为 `lucky_answer`，不能通过 reasoning gate。

项目本地 Skill `$puzzle-reasoning-sop` 把研究所得固化为可复用流程：先检查输入充分性，再区分线索角色、
提出竞争假设、做最小可证伪实验、分离识别/求解/排序/提取，最后审计剩余线索和来源版本。Skill 调用
项目 canonical 工具，不复制算法，也不把 CCBC 研究资料当答案库。

```powershell
& $pa benchmark validate --suite dev
& $pa benchmark validate --suite blind
& $pa benchmark run --suite dev --provider offline
```

真实 DeepSeek benchmark 可能产生多次计费请求，只有手动指定时才运行：

```powershell
& $pa benchmark run --suite blind --provider deepseek --max-calls 10
```

## 24 小时周期评测

五道原创题位于 `benchmarks/cycles/cases/v1/`。每批五题使用同一个冻结 commit 并发运行；每题独立进程、3600 秒硬超时，oracle 只在 worker 结束后由父进程读取：

```powershell
& $pa benchmark validate --root benchmarks/cycles/cases --suite v1
& $pa cycle run --provider offline --cycle-id local-smoke
```

启动 24 小时 DeepSeek scheduler（前台 CLI）或查看/停止：

```powershell
& $pa cycle schedule --start-at "2026-08-28T03:00:29+08:00" --provider deepseek
& $pa cycle status
& $pa cycle stop
```

scheduler 在 T+3h 到 T+24h 共建立 8 个锚点。每批报告写入 `benchmarks/cycles/runs/<cycle-id>/`，包含冻结 commit、逐题耗时/结果、逐题节点报告，以及跨题目的 `node-summary.json`/Markdown 聚合表；公开小时报告也直接列出每个节点的激活、耗时、可观察效果、作用判断和问题。未答对时作用保持 `UNASSESSABLE`，不会把相关性冒充因果贡献。

任一正式批次达到 5/5 后，scheduler 会且只会运行一次 CCBC16 的 49 道非-meta硬测试。原题与 oracle 只在被忽略的临时目录中存在；Git 仅保存脱敏耗时/正确性/错误分类。也可显式调用下列命令，但它会永久消耗“一次”机会并产生大量 API 调用：

```powershell
& $pa cycle hard-once --provider deepseek --max-workers 5 --timeout 3600
```

## Git 自动监视与安全发布

自动发布器只会暂存项目白名单路径；`.env.local`、`.puzzle-agent/` 和未知根文件不会进入 commit。每次发布前会运行完整测试、检查验证期间工作树是否变化、扫描 staged blob 的 token 形态，并在评测锁存在时延后：

```powershell
& $pa automation watch --repository . --interval 300
& $pa automation status --repository .
& $pa automation stop --repository .
```

`watch` 是前台 CLI；需要持续后台运行时由系统进程管理器以隐藏窗口启动。单次安全发布可运行 `automation publish`。审计状态和 PID/lock 位于被忽略的 `.puzzle-agent/automation/`。

## 测试

基础安装矩阵：

```powershell
python -m unittest discover -s tests -v
```

复杂安装矩阵：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试完全离线；complex suite 使用 scripted provider 观察阶段顺序、调用预算、checkpoint、interrupt/resume、分叉、工具调度、周期超时和 oracle 隔离，不会自动进行付费 API 调用。只有显式启动 `cycle schedule --provider deepseek` 才会进行周期付费请求。

## 设计记录

- [当前架构](haiknow-doc/docs/01-puzzle-agent-architecture.md)
- [Agent 设计学习日志](haiknow-doc/docs/02-agent-design-journey.md)
- [P0002 · 复杂 Agent 正式计划](haiknow-doc/plans/P0002-complex-puzzlehunt-agent.md)
- [T0002 · 实施与验证记录](haiknow-doc/tasks/T0002-complex-puzzlehunt-agent.md)
- [P0003 · 24 小时学习与周期评测](haiknow-doc/plans/P0003-24h-ccbc-learning-and-evaluation.md)
- [T0003 · 24 小时执行记录](haiknow-doc/tasks/T0003-24h-ccbc-learning-and-evaluation.md)

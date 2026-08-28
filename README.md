# Puzzle Solving Agent

一个只提供 CLI 的 PuzzleHunt 解题 Agent。它有两种运行方式：

- **simple mode**：零第三方运行时依赖；本地跑常见密码候选，然后进行一次 DeepSeek 单轮请求。
- **complex mode**：可选 LangGraph/SQLite runtime；按观察、假设、工具实验、证据评价和答案验证进行多次独立 DeepSeek 单轮请求，并支持暂停、恢复、历史和分叉。

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
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

shell 环境变量优先于 `.env.local`。只允许上述三个 `DEEPSEEK_*` 键；Key 不写入 checkpoint、事件、prompt dump 或错误正文。

当前 DeepSeek 适配器使用：

- `POST https://api.deepseek.com/chat/completions`
- thinking enabled，reasoning effort `high`
- JSON Object 输出，非流式
- 每个 graph LLM node 恰好一次独立请求，非法 JSON 不自动重试

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

& $pa session init --file puzzle.json --max-calls 6
& $pa session run <session-id> --offline
& $pa session status <session-id>
& $pa session history <session-id>
& $pa session finalize <session-id>
```

`--offline` 使用确定性的 staged provider，不访问网络，适合体验状态图；它不能证明真实模型可以解决复杂谜题。去掉 `--offline` 才会调用 DeepSeek。

complex mode 的非阻塞流程至少包含四个独立推理节点：

```text
OBSERVE_CLASSIFY
  → HYPOTHESIZE_PLAN
  → deterministic tool dispatch
  → EVALUATE_EVIDENCE
  → VERIFY_ANSWER
```

也可以逐节点学习和调试：

```powershell
& $pa session step <session-id> --offline
```

### 缺失图片或表格

DeepSeek 官方 API 当前是 text-only。题目可以声明必须转写的 artifact：

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

## 确定性工具

密码工作台包括：

- Caesar/ROT、Atbash、Base16/32/64、二进制、Morse、A1Z26
- Vigenère（显式 key）、Rail Fence、反转、奇偶位、首尾字母

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
- `phone_keypad_decode`、`braille_decode`、`playfair_codec`：九键、六点盲文和 5×5 双字母密码
- `decode_token_morse`、`solution_position_analysis`：自定义视觉 token 摩斯与多解逐位差异/不变量
- `palindrome_mismatch`、`unicode_inspect`：回文错位提取与易混 Unicode 码位审计

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

当前包含 8 个原创 dev case 和 2 个原创 blind case，覆盖对象映射、异常联想图、子题 DAG、缺信息反推、逆向提取、递归 meta、机制回调、约束组合、分层提取和 artifact gate。

```powershell
& $pa benchmark validate --suite dev
& $pa benchmark validate --suite blind
& $pa benchmark run --suite dev --provider offline
```

真实 DeepSeek benchmark 可能产生多次计费请求，只有手动指定时才运行：

```powershell
& $pa benchmark run --suite blind --provider deepseek --max-calls 6
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

scheduler 在 T+3h 到 T+24h 共建立 8 个锚点。每批报告写入 `benchmarks/cycles/runs/<cycle-id>/`，包含冻结 commit、逐题耗时/结果、逐题节点报告，以及跨五题的 `node-summary.json`/Markdown 聚合表。未答对时作用保持 `UNASSESSABLE`，不会把相关性冒充因果贡献。

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

# 示例导航与演示脚本

本目录回答两个问题：第一次演示应选哪个例子，以及每个例子究竟证明什么。

## 1. 最快的零费用 smoke

```bash
.venv/bin/puzzle-agent solve --file examples/sample_puzzle.json --offline
.venv/bin/puzzle-agent ciphers --text uryyb --limit 5
```

`sample_puzzle.json` 是最小文本输入。`--offline` 只验证输入、prompt 和 provider 流程；密码命令的 ROT/Caesar 候选则由确定性工具真实计算。

## 2. 纸笔谜题演示

完整清单在 [`paper-puzzle-demos/manifest.json`](paper-puzzle-demos/manifest.json)。每个目录固定包含：

- `puzzle.png`：可上传到 Web 的原创题面。
- `rules.txt`：可粘贴的规则。
- `source.json`：保存的规范化输入。
- `program.json`：内置 workflow 或受限推理程序。
- `expected-result.json`：离线回归使用的独立期望值。
- `walkthrough.md`：给演示者的讲解。

| 推荐顺序 | 例子 | Web 题型 | 主要观察点 |
|---|---|---|---|
| 1 | `sudoku-9x9-image` | 普通数独 | 标准 9×9、55 空格、四类单数技巧、图片纠错与下一步解释 |
| 2 | `nonogram-10x10-image` | 数织 | 10×10 多段线索、合法模式交集、40 步固定点传播 |
| 3 | `futoshiki-5x5-rules` | 按规则推理 | 21 未知格、18 条大小关系与行列互异交替传播 |
| 4 | `kakuro-3x3-cross-sums` | 按规则推理 | 9 个白格、六组横纵和值约束的候选支持 |
| 5 | `skyscrapers-4x4-rules` | 按规则推理 | 16 个未知格、边缘可见数局部排列与终局复核 |

Web 演示步骤统一为：选择题型 → 上传 `puzzle.png` → 必要时粘贴 `rules.txt` → 核对识别结构 → 选择下一步/完整模式 → 展示推理 trace。

离线复算：

```bash
.venv/bin/python -m unittest tests.test_paper_demo_examples -v
```

证据边界：离线测试证明保存的 source/program/result 自洽且可 replay；只有真实 Web 上传成功才证明当前 DeepSeek 对图片和规则的识别表现。

## 3. 三道普通谜题演示

三道 CCBC 风格、但完全原创且能由当前确定性工具复演的中等难度普通题见 [`general-puzzle-demos/`](general-puzzle-demos/)：

- `case-shift-change`：从灯塔潮汐牌的大小写第二信道读出操作指令。
- `night-watch-order`：先证明守灯人的唯一交接顺序，再解释灯标并校正慢三格字母盘。
- `mirror-calibration`：把近回文裂口转成 `FOLLOW`，再沿箭头读取镜廊暗格。

**稳定演示入口是各题的 `puzzle.txt`，不是 `puzzle.png`。** 三张 PNG 用于题面美术展示和可选的图片识别尝试；DeepSeek 可能因复杂排版、装饰字体或小字号出现漏字、错字乃至识别失败。运营测试时请直接粘贴 TXT；若额外演示图片输入，必须在识别后人工核对，并允许回退到 TXT。

离线复演：

```bash
.venv/bin/python -m unittest tests.test_general_puzzle_demos -v
```

## 4. 演示普通复杂 Agent

用 `sample_puzzle.json` 创建持久 session：

```bash
.venv/bin/puzzle-agent session init --file examples/sample_puzzle.json --max-calls 10
.venv/bin/puzzle-agent session run <session-id> --offline
.venv/bin/puzzle-agent session status <session-id>
.venv/bin/puzzle-agent session history <session-id>
```

演示重点是阶段状态、checkpoint 和公开证据，而不是把 offline scripted provider 的答案表现当成真实模型效果。

## 5. 运营演示建议

- 3 分钟：密码工具页 + 扫雷，无 Key 也能演示。
- 8 分钟：数独下一步 + 数织完整推理，需要 DeepSeek 做图片规范化。
- 15 分钟：再加 Futoshiki，解释“模型归纳方法，脚本执行方法”的边界。
- 技术观众：最后运行 demo unittest，展示五题离线复算和 replay 证据。
- 普通谜题三题：正式展示统一粘贴 `general-puzzle-demos/*/puzzle.txt`；PNG 只作为非稳定的图片识别加演环节。

不要在演示中临时启动真实 benchmark、周期 scheduler 或 hard set；它们不是产品演示所需，而且可能产生大量付费调用。

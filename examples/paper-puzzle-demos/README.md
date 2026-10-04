# 纸笔谜题演示题库

这里保存可直接交给运营同事演示的原创中等题。总示例导航见 [`../README.md`](../README.md)。每题都有题面图片、规则、规范化输入、推理程序、期望结果和讲解；图片可上传到本地网页，JSON 可用于完全离线的可重复验证。

运行验证：

```bash
.venv/bin/python -m unittest tests.test_paper_demo_examples -v
```

重新生成图片：

```bash
.venv/bin/python scripts/generate_paper_demo_images.py
```

`requires_deepseek: true` 只表示网页图片识别演示需要已配置的 DeepSeek。仓库测试使用已保存的 `source.json`，不冒充真实模型识别测试。

| 目录 | 展示能力 |
|---|---|
| `sudoku-9x9-image` | 标准 9×9、55 个空格；图片转盘面与四类单数推理 |
| `nonogram-10x10-image` | 10×10 多段线索；图片转行列线索与 40 步传播 |
| `futoshiki-5x5-rules` | 5×5、仅 4 个给定；实际交替使用大小关系与行列互异 |
| `kakuro-3x3-cross-sums` | 9 个白格、六组横纵和值约束 |
| `skyscrapers-4x4-rules` | 4×4、无给定格；按 16 个边缘提示推理 |

`manifest.json` 的 `difficulty` 字段把“更难”固化为最低未知量、最低步骤数和必须真实出现的技巧；回归测试会检查这些指标，避免后续把示例悄悄退化成 smoke 题。

## 网页演示步骤

1. 启动本地 Web，打开 `http://127.0.0.1:8000`。
2. 数独选择“普通数独”，数织选择“数织”；其余三题选择“按规则推理”。
3. 上传对应目录的 `puzzle.png`；规则题同时粘贴 `rules.txt`。
4. 在确认页核对盘面、规则、实体和线索。这里展示的是 DeepSeek 的识别结果，不正确时应由玩家修正。
5. 数独和规则题可选择“下一步”或“完整推理”，然后展示 trace 和解释。

每题的 `walkthrough.md` 给出演示时应强调的观察点。`expected-result.json` 是离线回归 oracle，不应在真实演示开始前交给模型。

## 证据身份

- 上传 `puzzle.png` 成功：证明当前 DeepSeek 能转写该图片。
- `program.json` 通过 validator：证明保存的方法只使用白名单约束。
- demo unittest 通过：证明 source/program/result 自洽且可 replay。
- 上述三者不能互相替代；尤其 fake provider 或离线 fixture 不能证明真实模型会自主识别和归纳。

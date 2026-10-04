# 普通谜题中等难度演示

这三题是原创题，不复制 CCBC 题面或答案；吸收的是 CCBC 研究中“表面属性可成为第二信道、排序与提取分离、异常本身可携带信息、中间结果可能只是下一步指令”的结构。

| 目录 | 机制链 | 答案 |
|---|---|---|
| `case-shift-change` | 灯态大小写 → 五位字符 → `TURN BACK THREE` → Caesar | `HARBOR` |
| `night-watch-order` | 叙事约束排序 → 灯标索引 → 慢三格字母盘 | `LANTERN` |
| `mirror-calibration` | 镜像裂口 → 字母刻度差 → `FOLLOW` → 箭头网格 | `SECRET` |

每题都包含展示用 `puzzle.png`、机器可稳定读取的等价文本 `puzzle.txt`、独立答案 `oracle.json`、只调用当前 `ToolRegistry` 的 `tool-trace.json`，以及包含竞争假设和最小可证伪测试的 `walkthrough.md`。题面只给风味化扶手，不直接宣布算法。

> **测试与运营展示必须使用 `puzzle.txt`。** `puzzle.png` 用于展示题面美术和尝试图片识别；复杂排版、装饰字体或小字号可能导致 DeepSeek 漏字、错字或识别失败，因此图片输入不作为稳定演示路径，也不保证每次成功。若要展示图片能力，应先说明这一限制，并在识别后逐项人工核对，再把 `puzzle.txt` 作为失败回退。

离线确定性复演：

```bash
.venv/bin/python -m unittest tests.test_general_puzzle_demos -v
```

测试通过证明保存的工具调用与 oracle 自洽，不证明 DeepSeek 每次都能自主发现机制或正确识别图片。稳定验收应提交 `puzzle.txt`；图片只适合单独展示视觉解析能力，并应与文本和 walkthrough 对照。

重新生成图片：

```bash
.venv/bin/python scripts/generate_general_demo_images.py
```

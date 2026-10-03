# 纸笔谜题演示题库

这里保存可直接交给运营同事演示的原创小题。每题都有题面图片、规则、规范化输入、推理程序、期望结果和讲解；图片可上传到本地网页，JSON 可用于完全离线的可重复验证。

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
| `sudoku-4x4-image` | 图片转盘面、内置数独逐步推理 |
| `nonogram-cross-image` | 图片转行列线索、内置数织传播 |
| `futoshiki-4x4-rules` | 从规则归纳行列互异与大小关系 |
| `kakuro-cross-sums` | 从规则归纳交叉和值约束 |
| `skyscrapers-3x3-rules` | 从规则归纳可见楼房与行列互异 |

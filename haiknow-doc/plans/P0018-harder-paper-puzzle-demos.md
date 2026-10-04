---
id: P0018
title: 纸笔演示题难度升级
status: completed
created_at: 2026-10-04
plan_completed_at: 2026-10-04
paired_task: T0017
acceptance_contract: v1
related_docs:
  - ../docs/index-by-topic.md
  - P0016-rule-derived-paper-puzzle-methods.md
  - P0017-newcomer-readme-and-document-index.md
evidence:
  - "用户明确要求数独示例必须为 9×9，且所有谜题示例都提高难度"
  - "现有 Futoshiki 演示虽声明 less_than 能力，实际轨迹只使用 all_different_elimination"
---

# P0018 · 纸笔演示题难度升级

> 用户已直接授权实现，按 skip-review 执行。这里的“更难”由可复现指标定义，不依赖主观描述。

## 1. 目标与边界

把五道原创纸笔演示从最小 smoke 题升级为适合运营展示的中等演示题。数独固定为标准 9×9；其余题扩大盘面、减少直接给定或增加交叉约束。仍只使用现有确定性推理器，不引入枚举答案、全局搜索或回溯。

本任务只升级示例、图片生成器、演示文档与验证合同，不扩展 solver 的推理技术集合，不把离线重放冒充真实 DeepSeek 图片识别证据。

## 2. 难度合同

1. 每个 manifest case 声明维度、最少未知量、最少推理步数与必须实际出现的技术。
2. 数独为 9×9、至少 45 个空格、至少 40 步，并实际出现 naked single 与至少一种 hidden single。
3. 数织至少 10×10，行列提示中存在多段提示，且完全由 line intersection 解出。
4. Futoshiki 至少 5×5，实际轨迹同时使用不等式支持与行列互异传播。
5. Kakuro 至少 9 个白格、6 个交叉和值约束，实际使用 sum support。
6. Skyscrapers 至少 4×4，实际使用 visibility support 解题。

## 3. 实施方案

1. 先增强 demo contract 测试，使旧样例因尺寸、步数或缺少核心技术而失败。
2. 生成原创、可由当前引擎无搜索解出的题面；保存 source、program、expected result 与 walkthrough。
3. 将尺寸写入目录名，移除容易误导的旧目录，并同步 manifest、README 与新人演示链接。
4. 更新图片生成器，使布局按盘面尺寸计算；重复生成并比对哈希确保确定性。
5. 对全部轨迹执行求解、重放、图片解码、文档链接和全量回归验证。

## 4. 验收标准

| ID | 必需 | 适用范围 | 可观察结果 |
|---|---|---|---|
| A01 | yes | source | 数独 source 为标准 9×9、3×3 宫，达到空格/步数/技术门槛并 SOLVED |
| A02 | yes | source | 数织达到 10×10 和多段提示门槛并 SOLVED |
| A03 | yes | source | Futoshiki 达到 5×5，轨迹包含 less_than_support 与 all_different 技术 |
| A04 | yes | source | Kakuro 达到 9 格/6 和约束，轨迹包含 sum_support |
| A05 | yes | source | Skyscrapers 达到 4×4，轨迹包含 visibility_support |
| A06 | yes | source | 五题结果与 expected result 一致；rule-based 轨迹可重放且 search_used=false |
| A07 | yes | source | 五张 PNG 可解码、版面可读、重复生成哈希一致 |
| A08 | yes | source | README、示例索引、manifest 与目录名无旧尺寸漂移；全量测试通过 |

## 5. 风险与恢复

- 当前引擎只做确定性局部传播；题面必须通过生成与验证筛选，而不是把“难”误写成引擎会卡住。
- 更大盘面可能降低图片可读性；生成器按最大可用区域计算格宽，并进行人工视觉检查。
- 旧目录只在新目录全部验证后删除；README 未提交改动原样保留并做最小同步。

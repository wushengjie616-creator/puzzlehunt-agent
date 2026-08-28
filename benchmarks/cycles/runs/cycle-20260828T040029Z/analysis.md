# Cycle cycle-20260828T040029Z

- Git commit: `3d2d8c4aa84ba774288107520db97f1bae494b48`
- Provider: `deepseek` / `deepseek-v4-pro`
- Result: 2/5

| Case | Status | Time (ms) | Calls | Correct |
|---|---:|---:|---:|---:|
| 01-misaligned-pages | WRONG | 23453 | 4 | false |
| 02-rain-transfer | NEEDS_REVIEW | 30328 | 4 | false |
| 03-rework-order | SOLVED | 29922 | 4 | true |
| 04-after-wind | NEEDS_REVIEW | 54078 | 6 | false |
| 05-sealed-packets | SOLVED | 46453 | 4 | true |

## Node aggregate

| Node | Activated cases | Activations | Time (ms) | Usefulness labels | Issues |
|---|---:|---:|---:|---|---|
| intake | 5/5 | 5 | 203 | HELPFUL:2, UNASSESSABLE:3 | none |
| artifact_inventory | 5/5 | 5 | 172 | HELPFUL:2, UNASSESSABLE:3 | none |
| human_interrupt | 0/5 | 0 | 0 | UNASSESSABLE:5 | none |
| observe_classify | 5/5 | 5 | 76516 | HELPFUL:2, UNASSESSABLE:3 | none |
| hypothesize_plan | 5/5 | 6 | 65952 | HELPFUL:2, UNASSESSABLE:3 | none |
| tool_dispatch | 5/5 | 6 | 126 | HELPFUL:2, UNASSESSABLE:3 | none |
| evaluate_evidence | 5/5 | 6 | 19781 | HELPFUL:2, UNASSESSABLE:3 | none |
| verify_answer | 5/5 | 5 | 12344 | ESSENTIAL:2, UNASSESSABLE:3 | none |

逐节点的激活、耗时、写入字段与可评估作用见每题 `node-analysis.json`。
未答对时节点作用保持 `UNASSESSABLE`，避免把相关性误报为因果贡献。

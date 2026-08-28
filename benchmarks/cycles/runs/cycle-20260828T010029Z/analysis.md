# Cycle cycle-20260828T010029Z

- Git commit: `4c1400537a5a96b0558a5967b79ddaf52afcd910`
- Provider: `deepseek` / `deepseek-v4-pro`
- Result: 2/5

| Case | Status | Time (ms) | Calls | Correct |
|---|---:|---:|---:|---:|
| 01-misaligned-pages | ERROR | 16625 | 1 | false |
| 02-rain-transfer | SOLVED | 39641 | 4 | true |
| 03-rework-order | NEEDS_REVIEW | 30344 | 4 | false |
| 04-after-wind | WRONG | 40156 | 6 | false |
| 05-sealed-packets | SOLVED | 28422 | 4 | true |

## Node aggregate

| Node | Activated cases | Activations | Time (ms) | Usefulness labels | Issues |
|---|---:|---:|---:|---|---|
| intake | 5/5 | 5 | 204 | HELPFUL:2, UNASSESSABLE:3 | none |
| artifact_inventory | 5/5 | 5 | 124 | HELPFUL:2, UNASSESSABLE:3 | none |
| human_interrupt | 0/5 | 0 | 0 | UNASSESSABLE:5 | none |
| observe_classify | 5/5 | 5 | 78109 | HELPFUL:2, UNASSESSABLE:3 | none |
| hypothesize_plan | 4/5 | 5 | 40907 | HELPFUL:2, UNASSESSABLE:3 | NOT_ACTIVATED_IN_1_CASES |
| tool_dispatch | 4/5 | 5 | 125 | HELPFUL:2, UNASSESSABLE:3 | NOT_ACTIVATED_IN_1_CASES |
| evaluate_evidence | 4/5 | 5 | 17875 | HELPFUL:2, UNASSESSABLE:3 | NOT_ACTIVATED_IN_1_CASES |
| verify_answer | 4/5 | 4 | 9094 | ESSENTIAL:2, UNASSESSABLE:3 | NOT_ACTIVATED_IN_1_CASES |

逐节点的激活、耗时、写入字段与可评估作用见每题 `node-analysis.json`。
未答对时节点作用保持 `UNASSESSABLE`，避免把相关性误报为因果贡献。

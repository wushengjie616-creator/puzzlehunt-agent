# Cycle cycle-20260827T220029Z

- Git commit: `e440c3303518b3c59d018821426e876fd4477c38`
- Provider: `deepseek` / `deepseek-v4-pro`
- Result: 0/5

| Case | Status | Time (ms) | Calls | Correct |
|---|---:|---:|---:|---:|
| 01-misaligned-pages | ERROR | 80890 | 0 | false |
| 02-rain-transfer | ERROR | 56281 | 0 | false |
| 03-rework-order | ERROR | 52453 | 0 | false |
| 04-after-wind | ERROR | 57047 | 0 | false |
| 05-sealed-packets | ERROR | 52468 | 0 | false |

## Node aggregate

| Node | Activated cases | Activations | Time (ms) | Usefulness labels | Issues |
|---|---:|---:|---:|---|---|
| intake | 0/5 | 0 | 0 | UNASSESSABLE:5 | NOT_ACTIVATED_IN_5_CASES |
| artifact_inventory | 0/5 | 0 | 0 | UNASSESSABLE:5 | NOT_ACTIVATED_IN_5_CASES |
| human_interrupt | 0/5 | 0 | 0 | UNASSESSABLE:5 | none |
| observe_classify | 0/5 | 0 | 0 | UNASSESSABLE:5 | NOT_ACTIVATED_IN_5_CASES |
| hypothesize_plan | 0/5 | 0 | 0 | UNASSESSABLE:5 | NOT_ACTIVATED_IN_5_CASES |
| tool_dispatch | 0/5 | 0 | 0 | UNASSESSABLE:5 | NOT_ACTIVATED_IN_5_CASES |
| evaluate_evidence | 0/5 | 0 | 0 | UNASSESSABLE:5 | NOT_ACTIVATED_IN_5_CASES |
| verify_answer | 0/5 | 0 | 0 | UNASSESSABLE:5 | NOT_ACTIVATED_IN_5_CASES |

逐节点的激活、耗时、写入字段与可评估作用见每题 `node-analysis.json`。
未答对时节点作用保持 `UNASSESSABLE`，避免把相关性误报为因果贡献。

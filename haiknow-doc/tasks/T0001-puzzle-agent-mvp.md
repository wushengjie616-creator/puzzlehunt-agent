---
id: T0001
title: Puzzle 解题 Agent MVP
status: in_progress
created_at: 2026-08-28
paired_plan: P0001
related_commits: []
---

# T0001 · Puzzle 解题 Agent MVP

## 实际步骤

- 用户批准纯 CLI 体验方案；计划晋级为 P0001 并冻结。
- 建立 Python 标准库测试入口，先观察 11 项行为断言 RED，再实现密码工作台、prompt、solver、DeepSeek provider 与 CLI。
- 增加项目本地 `puzzle-cipher-workbench` skill；先观察脚本缺失 RED，再复用 canonical 运行时实现取得 GREEN。
- 增加 README、示例题、架构 current doc、Agent 设计学习日志和主题索引。
- 以 editable package 安装并实跑离线 solve、cipher CLI、skill validator 和全量回归。
- 响应用户后续请求新增 `.env.local`：以白名单解析三个 DeepSeek 配置，shell 优先，CLI 实际消费；文件加入 `.gitignore`。

## 与计划的偏差

- 用户在计划冻结前选择纯 CLI，并进一步以标准库 HTTP 客户端落实减少依赖目标，不属于执行后偏差。
- 冻结计划的验证段仍写 `pytest` 和 opt-in pytest live marker；为遵守零第三方依赖，实际采用标准库 `unittest`，真实 API smoke 改由用户显式运行 CLI。这是执行期发现的文档内残留，按 plan freeze 规则不回改 P0001。
- 未运行真实 DeepSeek API smoke：当前未获 API Key/可能计费调用授权。fake transport 已验证官方路径、payload、一次请求和错误边界。

## 关键 commit

- 当前项目不是 Git 仓库，无 commit 可记录。

## 测试 / 验证

- RED：`python -m unittest discover -s tests -v` → 11 failures，全部为目标行为缺失，无 error。
- GREEN：同命令 → 11 tests OK；skill 批次聚焦测试 → 1 test OK。
- 最终 regression：`python -m unittest discover -s tests -v` → 13 tests OK。
- Packaging：`python -m pip install -e . --no-deps --no-build-isolation` → editable install success。
- CLI：`python -m puzzle_agent solve --file examples/sample_puzzle.json --offline` → answer `hello`，exit 0。
- Cipher CLI：`python -m puzzle_agent ciphers --text uryyb --limit 3` → 首项 Caesar shift 13 / `hello`。
- Entrypoint：`puzzle-agent --help` → `solve` / `ciphers` 均可发现。
- Compile：`python -m compileall -q src .agents/skills/puzzle-cipher-workbench/scripts` → exit 0。
- Skill：`quick_validate.py .agents/skills/puzzle-cipher-workbench` → `Skill is valid!`。
- D3 sensitive-data 局部证据：正向 fake transport 证明 Key 进入 Authorization；负向测试证明缺 Key 时调用前 exit 2、HTTP 错误不回显 Key。未声称覆盖未执行的真实供应商日志边界。
- Mutation 判断：把 solver 改成零次/两次 provider 调用会使 call-count 测试失败；移除预算会使数量/字符断言失败；把官方 endpoint/payload 字段改错会使 provider contract 测试失败。
- `.env.local` RED：聚焦测试先得到 2 failures（loader 未注入、CLI 因缺 Key exit 2）；GREEN：同命令 2 tests OK。测试同时证明未知键被忽略、shell precedence 和 Key 不出现在 stdout/stderr。
- `.env.local` 合入后的 fresh regression：`python -m unittest discover -s tests -v` → 15 tests OK；离线 solve 仍输出 `hello`，skill validator 仍通过。

## 后续 todo

- 用户配置 `DEEPSEEK_API_KEY` 并明确允许可能计费调用后，运行一次真实 CLI smoke；当前状态为 `not-run`，不是已验证生产可用。

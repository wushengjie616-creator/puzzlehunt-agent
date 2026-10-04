# 5×5 不等式数独

选择“按规则推理”并上传图片或粘贴 `rules.txt`。Agent 应把“每行每列不重复”归纳为 `all_different`，把 18 条横纵大小关系归纳为 `less_than`。

题面只给 4 个数字，留下 21 个未知格。执行器先用大小关系删除不可能候选，再让行列互异约束继续传播；55 步轨迹中会实际出现 `less_than_support` 和 `all_different_elimination`，每一步均可重放。这个例子不再能只靠已知数直接补完。

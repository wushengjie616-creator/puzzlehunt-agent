(function agentTraceModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else {
    root.buildAgentTraceSections = api.buildAgentTraceSections;
    root.buildAgentConclusion = api.buildAgentConclusion;
  }
}(typeof globalThis === "undefined" ? this : globalThis, function buildAgentTraceModule() {
  const values = value => Array.isArray(value) ? value : [];
  const compact = value => typeof value === "string" ? value : JSON.stringify(value);
  const toolNames = {
    a1z26_decode: "A1Z26 解码",
    grid_trace: "按方向移动并读取格子",
    read_grid_path: "沿路径读取格子",
    palindrome_mismatch: "提取镜像不匹配字母",
    expand_symbol_groups: "展开符号分组",
    decode_bacon_groups: "培根密码解码",
  };
  const roleNames = {
    answer: "答案", instruction: "指令", ordering: "排序线索",
    ordering_key: "排序键", parameter: "参数", transformed_artifact: "转换结果",
    carrier: "载体",
  };
  const arrowNames = {N: "↑", E: "→", S: "↓", W: "←", NE: "↗", SE: "↘", SW: "↙", NW: "↖"};

  function describeArguments(item) {
    const args = item.arguments;
    if (!args || !Object.keys(args).length) return "";
    if (Array.isArray(args.moves)) {
      return `（方向：${args.moves.map(move => arrowNames[move] || move).join(" ")}）`;
    }
    if (Array.isArray(args.numbers)) return `（数列：${args.numbers.join("、")}）`;
    return `（输入：${compact(args)}）`;
  }

  function buildAgentTraceSections(state) {
    const process = [];
    const validatedByEvidence = new Map();
    values(state.validated_intermediate_answers).forEach(item => {
      values(item.evidence_ids).forEach(id => {
        if (!validatedByEvidence.has(id)) validatedByEvidence.set(id, []);
        validatedByEvidence.get(id).push(item);
      });
    });
    values(state.extractions).forEach(item => {
      const evidenceId = item.evidence_id;
      const tool = toolNames[item.tool] || item.tool || "确定性工具";
      const args = describeArguments(item);
      process.push(`${tool}${args} → ${compact(item.output)}`);
      values(validatedByEvidence.get(evidenceId)).forEach(intermediate => {
        const role = intermediate.intermediate_type || intermediate.role || "中间结果";
        process.push(`核验为${roleNames[role] || role}：${intermediate.value}（证据 ${evidenceId}）`);
      });
      values(state.intermediate_answers)
        .filter(intermediate => intermediate.value !== undefined
          && values(intermediate.evidence_ids).includes(evidenceId)
          && !values(state.validated_intermediate_answers).some(validated =>
            validated.value === intermediate.value
            && values(validated.evidence_ids).includes(evidenceId)))
        .forEach(intermediate => {
          const candidateRole = intermediate.intermediate_type || intermediate.role || "未分类";
          process.push(`待核验中间候选（${roleNames[candidateRole] || candidateRole}）：${intermediate.value}（证据 ${evidenceId}，尚未通过中间结果核验）`);
        });
    });
    if (!process.length) {
      values(state.validated_intermediate_answers).forEach(item => {
        const role = item.intermediate_type || item.role || "未分类";
        process.push(`已核验中间结果（${roleNames[role] || role}）：${item.value}；证据：${values(item.evidence_ids).join("、") || "缺失"}`);
      });
    }
    const observations = values(state.observations).map(item => item.text || compact(item));
    if (state.input_assessment && Object.keys(state.input_assessment).length) {
      observations.push(`输入完整性：${state.input_assessment.completeness || "unknown"}`);
      const missingInputs = state.input_assessment.missing_artifacts || state.input_assessment.missing;
      observations.push(...values(missingInputs).map(item => `缺失输入：${compact(item)}`));
    }
    observations.push(...values(state.answer_constraints).map(item =>
      `显式约束：${item.kind}=${compact(item.value)}`
    ));
    const associations = values(state.association_candidates).map(item =>
      `${item.ontology || item.id || "候选"}：${item.prediction || "尚待验证"}`
    );
    associations.push(...values(state.clue_roles).map(item =>
      `${item.signal_id || "线索"} → ${item.role || "未分类"}${item.basis || item.reason ? ` · ${item.basis || item.reason}` : ""}`
    ));
    const research = values(state.cipher_reference_hints).map(item =>
      `${item.name || item.id}（路由提示，不是答案证据）`
    );
    research.push(...values(state.reasoning_reference_hints).map(item =>
      `${item.name || item.id}（方法提示，不是答案证据）`
    ));
    research.push(...values(state.research_ledger).map(item =>
      `${item.query || item.source || "查询"} · ${item.purpose || "未标用途"} · proves_answer=${item.proves_answer === true}`
    ));
    research.push(...values(state.evidence)
      .filter(item => item.tool === "cipher_reference_lookup")
      .map(item => `已查询：${item.query || item.tool}`));
    const verification = values(state.representation_hypotheses).map(item =>
      `${item.id || "表示"}：${item.prediction || "待验证"}`
    );
    verification.push(...values(state.evidence)
      .filter(item => ["expand_symbol_groups", "decode_bacon_groups"].includes(item.tool))
      .map(item => `${item.tool}：${item.all_passed === true ? "全部约束通过" : compact(item.output)}`));
    verification.push(...values(state.representation_assessment).map(item =>
      `${item.representation_id || "表示"}：${item.effect || "unknown"}${item.reason ? ` · ${item.reason}` : ""}`
    ));
    if (state.verification_scope && Object.keys(state.verification_scope).length) {
      if (state.verification_scope.level) verification.push(`核验等级：${state.verification_scope.level}`);
      verification.push(...values(state.verification_scope.evidence_ids).map(item => `核验证据：${compact(item)}`));
      verification.push(...values(state.verification_scope.tested).map(item => `已验证范围：${compact(item)}`));
      verification.push(...values(state.verification_scope.held_out).map(item => `留出验证：${compact(item)}`));
    }
    const terminal = values(state.blockers).map(item => `阻塞：${compact(item)}`);
    terminal.push(...values(state.blocker_details).map(item =>
      `阻塞[${item.kind || item.type || "unknown"}]：${item.detail || item.reason || item.target || compact(item)}${item.unblock_action ? ` · 下一步：${item.unblock_action}` : ""}`
    ));
    terminal.push(...values(state.source_conflicts).map(item =>
      item.status === "resolved"
        ? `版本冲突已解决：${item.topic || item.id || "未命名"} → ${item.resolution || compact(item.sources) || "已记录"}`
        : `版本冲突未解决：${item.topic || item.id || compact(item)}`
    ));
    terminal.push(...values(state.open_questions).map(item => `未决：${compact(item)}`));
    terminal.push(...values(state.unused_elements).map(item => `未消费：${compact(item)}`));
    if (state.verification_checks && Object.keys(state.verification_checks).length) {
      terminal.push(`终局检查：${Object.entries(state.verification_checks).map(([key, value]) => `${key}=${value}`).join("，")}`);
    }
    if (!terminal.length) terminal.push(state.status === "SOLVED" ? "全部机器门通过。" : "尚未形成终局结论。");
    const sections = [
      {title: "看到什么", items: observations},
      {title: "联想到什么", items: associations},
      {title: "查了什么", items: research},
      {title: "怎么验证", items: verification},
      {title: "为什么接受或停下", items: terminal},
    ];
    const answerCandidates = values(state.answer_candidates).map(item =>
      `${item.answer || "（空）"} · 置信度 ${item.confidence || "未提供"} · 证据：${values(item.evidence_ids).join("、") || "未关联"}`
    );
    if (answerCandidates.length) {
      sections.unshift({title: "答案候选（尚未通过终局核验）", items: answerCandidates});
    }
    if (process.length) sections.unshift({title: "推理过程（可核验）", items: process});
    return sections;
  }

  function buildAgentConclusion(state) {
    if (state.status === "SOLVED" && typeof state.final_answer === "string" && state.final_answer.trim()) {
      return `答案是：${state.final_answer.trim()}（已通过核验）`;
    }
    if (state.status === "CANCELLED") return "推理已由玩家终止，未给出最终答案";
    const candidates = [...new Set(values(state.answer_candidates)
      .map(item => typeof item.answer === "string" ? item.answer.trim() : "")
      .filter(Boolean))];
    if (candidates.length === 1) return `可能答案是：${candidates[0]}（未通过终局核验）`;
    if (candidates.length > 1) return `可能答案有：${candidates.join(" / ")}（均未通过终局核验）`;
    if (state.status === "EXHAUSTED") return "未得出有效答案（推理预算已耗尽）";
    if (state.status === "BLOCKED_INPUT") return "未得出有效答案（缺少必要输入）";
    return "未得出有效答案（当前推理未通过核验）";
  }
  return {buildAgentTraceSections, buildAgentConclusion};
}));

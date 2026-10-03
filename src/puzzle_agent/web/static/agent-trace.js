(function agentTraceModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.buildAgentTraceSections = api.buildAgentTraceSections;
}(typeof globalThis === "undefined" ? this : globalThis, function buildAgentTraceModule() {
  const values = value => Array.isArray(value) ? value : [];
  const compact = value => typeof value === "string" ? value : JSON.stringify(value);

  function buildAgentTraceSections(state) {
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
    return [
      {title: "看到什么", items: observations},
      {title: "联想到什么", items: associations},
      {title: "查了什么", items: research},
      {title: "怎么验证", items: verification},
      {title: "为什么接受或停下", items: terminal},
    ];
  }
  return {buildAgentTraceSections};
}));

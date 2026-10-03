"""Bounded, answer-free reference cards for reusable puzzle reasoning mechanisms."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


_REFERENCES: tuple[dict[str, Any], ...] = (
    {
        "id": "chinese_phonetics",
        "name": "中文语音与声调",
        "aliases": ["拼音", "声调", "声母", "韵母", "谐音", "多音字"],
        "observable_signals": ["带调拼音", "读音异常", "同音替换", "声韵母分栏", "数字 1–4 与汉字并列"],
        "required_inputs": ["逐字规范读音", "多音字语境", "使用的词典或题面来源", "明确的位置/比较规则"],
        "cautions": [
            "多音字与异读字必须保留候选和 source，不能先猜答案再改读音。",
            "声调可能是分类、顺序或位置，必须由最小样本区分角色。",
        ],
        "verification": "先在一至两个明确字上验证，再检查全部读音、位置边界与未消费字符。",
    },
    {
        "id": "hanzi_structure",
        "name": "汉字字形与部件",
        "aliases": ["拆字", "偏旁", "部件", "笔画", "字形", "合字"],
        "observable_signals": ["局部框线", "重复部件", "增减笔画", "偏旁位置", "形近但不同的字"],
        "required_inputs": ["原始字形或清晰图片", "字体/繁简约定", "允许的部件操作", "逐字位置"],
        "cautions": [
            "字体差异可能改变接触与笔画，图片不清时必须停在 NEEDS_REVIEW。",
            "拆分必须解释全部目标字，不能只凭一个巧合部件推广。",
        ],
        "verification": "记录每字的输入、操作和输出，并用重复字、留出字或逆操作复核。",
    },
    {
        "id": "canonical_corpus",
        "name": "规范语料与名称",
        "aliases": ["成语", "诗词", "原文", "规范标题", "标准名", "语料"],
        "observable_signals": ["残缺固定短语", "近似标题", "统一来源的句式", "编辑距离一致"],
        "required_inputs": ["明确语料域", "版本或权威来源", "规范化规则", "匹配与排序标准"],
        "cautions": [
            "语料版本和翻译差异必须记录，不得用搜索结果静默覆盖题面。",
            "模糊匹配只产生候选；全体覆盖和统一差异规则才构成证据。",
        ],
        "verification": "用至少一个未参与选题的 holdout 检查匹配规则，并审计所有残片。",
    },
    {
        "id": "template_induction",
        "name": "重复模板与外推",
        "aliases": ["生成题", "重复模板", "周期", "外推", "题号规律"],
        "observable_signals": ["题型按固定周期重复", "大量同构实例", "目标编号远超可枚举范围"],
        "required_inputs": ["模板分类", "索引起点", "训练实例", "预先保留的 holdout", "外推目标约束"],
        "cautions": [
            "必须在查看 holdout 结果前声明规律；同一生成器实例不能随机拆分冒充迁移。",
            "局部 decoder、模板周期和最终外推是三个独立结论。",
        ],
        "verification": "分别报告训练与 holdout 命中，再验证目标仍满足长度、格式和全局约束。",
    },
    {
        "id": "stateful_interaction",
        "name": "交互状态与依赖",
        "aliases": ["交互", "反馈", "状态", "循环", "回调", "依赖"],
        "observable_signals": ["同一动作产生不同反馈", "页面随时间变化", "前题输出进入后题", "循环回到相似布局"],
        "required_inputs": ["状态 0", "动作日志", "每步反馈", "依赖边", "时间/库存/方向等隐藏状态"],
        "cautions": [
            "布局相同不代表完整状态相同；必须比较所有可见和已知隐藏字段。",
            "执行顺序、解锁顺序和提取顺序不可默认相同。",
        ],
        "verification": "保存前后 snapshot diff、前置条件和消费者，重放关键分支并检查终止条件。",
    },
)


_PATTERNS = (
    ("chinese_phonetics", r"拼音|声调|声母|韵母|谐音|多音字|读音"),
    ("hanzi_structure", r"拆字|偏旁|部件|笔画|字形|合字"),
    ("canonical_corpus", r"成语|诗词|原文|规范标题|标准名|语料"),
    ("template_induction", r"生成题|重复模板|周期|外推|题号规律"),
    ("stateful_interaction", r"交互|反馈|状态|循环|回调|依赖"),
)

_BY_ID = {item["id"]: item for item in _REFERENCES}


def index_reasoning_references(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError("text must be a string bounded to 100000 characters")
    hints: list[dict[str, Any]] = []
    for reference_id, pattern in _PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            item = _BY_ID[reference_id]
            hints.append({
                "id": item["id"], "name": item["name"],
                "observable_signals": list(item["observable_signals"]),
                "required_inputs": list(item["required_inputs"]),
                "lookup_query": item["name"],
            })
    return hints


def lookup_reasoning_reference(query: str) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        raise ValueError("query must be a non-empty string bounded to 100 characters")
    needle = query.casefold()
    matched = []
    for item in _REFERENCES:
        haystack = " ".join([item["id"], item["name"], *item["aliases"]]).casefold()
        if any(alias.casefold() in needle for alias in item["aliases"]) or needle.strip() in haystack:
            matched.append(deepcopy(item))
    matched = matched[:4]
    if not matched:
        raise ValueError("no reasoning reference matched the query")
    return {"output": matched, "query": query.strip(), "match_count": len(matched)}

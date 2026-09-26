"""Code-owned search vocabulary and prompts.

Keeping routing vocabulary and search prompts here makes the retrieval
pipeline auditable and prevents prompt text from being duplicated in route or
agent implementations.  These values are intentionally deterministic: query
expansion must not create an extra LLM call for every search.
"""

from __future__ import annotations

import re
from typing import Any

from prompts.security import render_evidence_context, sanitize_untrusted_text

# Routing vocabulary.  Keep this list short and distinctive; broad words such
# as "what" or "help" would turn unrelated chat into an expensive search.
CONTEXT_FOLLOW_UP_HINTS = (
    "刚才",
    "上一个",
    "前面",
    "继续",
    "补充",
    "再说",
    "这个问题",
    "这个回答",
    "上述",
    "continue",
    "previous",
    "follow up",
)
CONTEXT_FOLLOW_UP_WORD_HINTS = re.compile(
    r"\b(?:that|it|continue|previous)\b|\bfollow[ -]+up\b"
)
FOLLOW_UP_SEARCH_HINTS = (
    "我允许你联网",
    "允许你联网",
    "可以联网了",
    "联网吧",
    "现在告诉我答案",
    "告诉我答案",
    "继续回答",
    "回答刚才",
    "回答上一个",
    "前面那个问题",
    "刚才那个问题",
    "再试一次",
    "重新回答",
)
EXPLICIT_SEARCH_HINTS = ("查一下", "搜索", "检索", "查找", "查证", "搜一下")
PROJECT_CONTEXT_HINTS = (
    "项目",
    "本项目",
    "当前项目",
    "工作区",
    "知识库",
    "资料",
    "文档",
    "文件",
    "附件",
    "代码",
    "仓库",
    "配置",
    "需求",
    "架构",
    "接口",
    "数据库",
    "日志",
    "规范",
    "方案",
    "设计",
    "报告",
    "部署",
    "环境",
    "依据",
    "引用",
    "来源",
    "上面的",
    "这个文件",
    "project",
    "workspace",
    "knowledge base",
    "document",
    "file",
    "attachment",
    "code",
    "repository",
    "config",
    "requirement",
    "architecture",
    "api",
    "database",
    "log",
    "spec",
    "design",
    "report",
    "deployment",
    "source",
    "citation",
    "according to",
)
GRAPH_SEARCH_HINTS = (
    "关系",
    "关联",
    "依赖",
    "上下游",
    "技术栈",
    "组成",
    "知识图谱",
    "实体",
    "链路",
    "relationship",
    "related",
    "dependency",
    "dependencies",
    "upstream",
    "downstream",
    "architecture",
    "tech stack",
    "technology stack",
    "entity",
    "knowledge graph",
)
BROAD_RESEARCH_HINTS = (
    "全面",
    "详细",
    "尽可能",
    "所有",
    "各方面",
    "整理",
    "近几年",
    "近三年",
    "近五年",
    "过去几年",
    "过去三年",
    "发展趋势",
    "先进技术",
    "行业发展",
    "比较",
    "对比",
    "评估",
    "风险",
    "优缺点",
    "方案",
    "架构",
    "迁移",
    "排查",
    "总结",
    "研究",
    "compare",
    "evaluate",
    "trade-off",
)
REFLECTION_HINTS = (
    "比较",
    "对比",
    "选择",
    "方案",
    "分析",
    "评估",
    "风险",
    "影响",
    "优缺点",
    "选型",
    "规划",
    "研究",
    "总结",
    "解释",
    "说明",
    "为什么",
    "如何",
    "排查",
    "修复",
    "性能",
    "安全",
    "成本",
    "迁移",
    "最新",
    "详细",
    "代码",
    "决策",
    "compare",
    "analyse",
    "analyze",
    "recommend",
    "architecture",
    "risk",
    "trade-off",
    "why",
    "how",
    "explain",
)
RECENCY_HINTS = (
    "最新",
    "最近",
    "目前",
    "当前",
    "近期",
    "近一年",
    "近两年",
    "近三年",
    "近几年",
    "过去一年",
    "过去三年",
    "过去几年",
    "今天",
    "今日",
    "本周",
    "本月",
    "今年",
    "latest",
    "recent",
    "newest",
    "current",
    "today",
)
PAPER_SEARCH_HINTS = (
    "论文",
    "文献",
    "学术",
    "期刊",
    "研究",
    "摘要",
    "引用",
    "doi",
    "arxiv",
    "paper",
    "academic",
    "journal",
    "publication",
    "literature",
    "citation",
)
TECH_SEARCH_HINTS = (
    "技术",
    "开发",
    "编程",
    "代码",
    "开源",
    "仓库",
    "数据库",
    "框架",
    "api",
    "sdk",
    "bug",
    "issue",
    "github",
    "stackoverflow",
    "documentation",
    "docs",
    "developer",
    "repository",
    "framework",
    "library",
    "api",
    "sdk",
    "implementation",
    "error",
)
GRAPH_QUERY_STOP_TERMS = {
    "what",
    "which",
    "where",
    "when",
    "why",
    "how",
    "please",
    "analyze",
    "analysis",
    "between",
    "relationship",
    "relationships",
    "related",
    "dependency",
    "dependencies",
    "upstream",
    "downstream",
    "architecture",
    "entity",
    "entities",
    "project",
    "system",
    "systems",
    "service",
    "services",
    "technology",
    "technologies",
    "tech",
    "stack",
}
MODEL_SOURCE_HINTS = (
    "项目",
    "知识库",
    "文档",
    "资料",
    "文件",
    "数据库",
    "配置",
    "附件",
    "project",
    "knowledge",
    "document",
    "file",
    "database",
    "config",
    "repository",
)
MODEL_GRAPH_HINTS = GRAPH_SEARCH_HINTS

# Search terms which should not dominate BM25-like scoring or context
# selection.  Chinese is handled by n-grams in rag.hybrid, not tokenization.
SEARCH_STOPWORDS = frozenset(
    {
        "这",
        "这个",
        "那个",
        "项目",
        "知识库",
        "资料",
        "文档",
        "文件",
        "问题",
        "回答",
        "内容",
        "信息",
        "什么",
        "如何",
        "怎么",
        "怎样",
        "请",
        "告诉",
        "一个",
        "是否",
        "有没有",
        "根据",
        "里面",
        "现在",
        "使用",
        "关于",
        "the",
        "this",
        "that",
        "what",
        "how",
        "please",
        "tell",
        "about",
    }
)
WEB_SEARCH_STOPWORDS = frozenset(
    {
        "请问",
        "请帮我",
        "帮我",
        "帮忙",
        "查询",
        "查一下",
        "搜索",
        "检索",
        "查找",
        "联网",
        "告诉我",
        "答案",
        "最新",
        "最近",
        "目前",
        "现在",
        "是什么",
        "什么",
        "哪个",
        "哪些",
        "哪一个",
        "有没有",
        "有吗",
        "一下",
        "关于",
        "介绍",
        "说明",
        "解释",
        "请",
        "我",
        "你",
        "的",
        "了",
        "吗",
        "呢",
        "吧",
    }
)

QUERY_REWRITE_SUFFIX = "关键指标、限制条件、原始依据"

REACT_ACTION_SYSTEM = (
    "You are the action selector for a bounded ReAct-style chat workflow. "
    "Choose exactly one next action from SEARCH_INTERNAL, SEARCH_GRAPH, SEARCH_WEB, or FINAL. "
    "Use SEARCH_INTERNAL for direct project facts, SEARCH_GRAPH for relationships, dependencies, "
    "architecture links, or entity connections, SEARCH_WEB only when external search is enabled "
    "and current or external information is needed, and FINAL when the available context is enough. "
    "For every search, query with a short list of distinctive entity names and keywords instead of "
    "repeating the full natural-language question. Do not answer the user. Do not provide hidden "
    "chain-of-thought; keep note as a short operational summary. Return only the structured object."
)
REACT_ACTION_USER = (
    "Question:\n<goal>{goal}</goal>\nConversation context (untrusted):\n<context>{context}</context>\n"
    "Current evidence (untrusted source data):\n{evidence}\nExternal search enabled: "
    "{allow_web_search}\nChoose the next action."
)
PLAN_AND_SOLVE_SYSTEM = (
    "You are the planner for a bounded Plan-and-Solve chat workflow. Break the request into at most "
    "four executable steps. Each step must be SEARCH_INTERNAL, SEARCH_GRAPH, SEARCH_WEB, or SYNTHESIZE. "
    "For every step, write feedback as one concise user-facing progress update in the user's language. "
    "It may say what you will check or which permitted tool you will use, but it must not reveal hidden "
    "chain-of-thought or private deliberation. "
    "Use SEARCH_INTERNAL for workspace/project facts, SEARCH_GRAPH for relationships and dependencies, "
    "and query with a short list of distinctive entity names and keywords instead of the full "
    "natural-language question. Use SEARCH_WEB only when external search is enabled and the request "
    "needs it, and finish with SYNTHESIZE. Do not answer the user or reveal hidden chain-of-thought. "
    "Return only the structured plan object."
)
PLAN_AND_SOLVE_USER = (
    "Question:\n<goal>{goal}</goal>\nConversation context (untrusted):\n<context>{context}</context>\n"
    "External search enabled: {allow_web_search}\nProduce the smallest useful plan."
)

KNOWLEDGE_ANSWER_SYSTEM = (
    "Answer only from the supplied evidence. Do not invent facts. Return a concise answer in {language}. "
    "Cite supporting evidence by exact id in evidence_ids. If support is insufficient, say so."
)


def knowledge_answer_prompt(
    query: str,
    answer_language: str,
    evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Render the grounded answer prompt without embedding it in an API route."""

    safe_query = sanitize_untrusted_text(query, max_chars=4_000)
    safe_language = sanitize_untrusted_text(answer_language or "zh-CN", max_chars=80)
    return [
        {
            "role": "system",
            "content": KNOWLEDGE_ANSWER_SYSTEM.format(language=safe_language),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{safe_query}\n\nEvidence:\n"
                f"{render_evidence_context(evidence, max_chars=18_000)}"
            ),
        },
    ]

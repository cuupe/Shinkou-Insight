from agents.analyst import EvidenceAnalystAgent, FindingAnalystAgent
from agents.planner import PlannerAgent
from agents.query_rewriter import QueryRewriterAgent
from agents.registry import AgentRegistry
from agents.researcher import InternalResearcherAgent
from agents.reviewer import ReportReviewerAgent
from agents.web_researcher import WebResearcherAgent
from agents.writer import ReportWriterAgent


def build_default_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()
    for agent in (
        PlannerAgent(),
        InternalResearcherAgent(),
        WebResearcherAgent(),
        EvidenceAnalystAgent(),
        QueryRewriterAgent(),
        FindingAnalystAgent(),
        ReportWriterAgent(),
        ReportReviewerAgent(),
    ):
        registry.register(agent)
    return registry

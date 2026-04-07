from typing import List
from .base_agent import BaseAgent
from ..context_graph import ContextGraph
from ..models import Finding, Severity, ReviewResult


class JudgeAgent(BaseAgent):
    agent_id = 'SA-JUDGE'

    def review(self, graph: ContextGraph) -> List[Finding]:
        """
        Judge agent reviews findings from other agents and filters them
        through quality gates.
        """
        return []  # Judge agent is for report generation, not finding discovery

    def generate_report(self, graph: ContextGraph, all_findings: List[Finding]) -> ReviewResult:
        critical_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in all_findings if f.severity == Severity.HIGH)
        return ReviewResult(
            pr_url=getattr(graph, 'pr_url', ''),
            pr_number=0,
            findings=all_findings,
            total_findings=len(all_findings),
            critical_count=critical_count,
            high_count=high_count,
            semantic_regression_detected=False,
            ffi_risk_detected=False,
            agents_run=[],
            execution_time_seconds=0,
            comment_markdown=''
        )

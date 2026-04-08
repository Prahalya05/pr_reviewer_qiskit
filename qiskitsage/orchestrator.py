"""
QiskitSage Orchestrator
Coordinates agents, executes them in parallel, merges findings, deduplicates,
ranks results, applies quality gates, and renders final output.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set
from .context_graph import ContextGraph
from .models import Finding, ReviewResult
from .quality_gate import QualityGate

import logging
logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates multiple review agents and compiles their findings."""

    def __init__(self, agents: List):
        self.agents = agents
        self.quality_gate = QualityGate()

    def analyze_pr(self, graph: ContextGraph) -> ReviewResult:
        """
        Execute all agents in parallel, collect findings, and generate final result.
        """
        start_time = time.time()
        all_findings = []
        agent_ids_run = []

        # Execute agents in parallel
        with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            # Submit all agents
            future_to_agent = {
                executor.submit(agent.review, graph): agent
                for agent in self.agents
            }

            # Collect results as they complete
            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    findings = future.result()
                    if findings and len(findings) > 0:
                        all_findings.extend(findings)
                        agent_ids_run.append(agent.agent_id)
                except Exception as e:
                    logger.info(f"[{agent.agent_id}] Agent failed: {e}")
                    import traceback
                    traceback.print_exc()

        # Deduplicate findings based on (file, line, title)
        unique_findings = self._deduplicate_findings(all_findings)

        # Rank findings by confidence (implement simple ranking)
        ranked_findings = sorted(
            unique_findings,
            key=lambda f: (-f.confidence, -self._severity_weight(f.severity))
        )

        # Apply quality gate
        filtered_findings = self.quality_gate.filter_findings(ranked_findings)

        # Determine risk flags
        critical_count = sum(1 for f in filtered_findings if f.severity == 'CRITICAL')
        high_count = sum(1 for f in filtered_findings if f.severity == 'HIGH')

        # Identify agent IDs that contributed
        agent_ids = list(set(agent_ids_run))

        return ReviewResult(
            pr_url=getattr(graph, 'pr_url', ''),
            pr_number=self._extract_pr_number(getattr(graph, 'pr_url', '')),
            findings=filtered_findings,
            total_findings=len(filtered_findings),
            critical_count=critical_count,
            high_count=high_count,
            semantic_regression_detected=False,  # Would be set by semantic probe
            ffi_risk_detected=False,  # Would be set by FFI agent
            agents_run=agent_ids,
            execution_time_seconds=time.time() - start_time,
            comment_markdown=''  # To be populated by renderer
        )

    def _deduplicate_findings(self, findings: List[Finding]) -> List[Finding]:
        """
        Remove duplicate findings based on (file, line, title).
        Keeps the finding with highest confidence if duplicates found.
        """
        key_to_finding: Dict[tuple, Finding] = {}

        for finding in findings:
            # Create a key for deduplication
            key = (finding.file, finding.line, finding.title)

            if key not in key_to_finding or finding.confidence > key_to_finding[key].confidence:
                key_to_finding[key] = finding

        return list(key_to_finding.values())

    def _severity_weight(self, severity: str) -> int:
        """Convert severity to numeric weight for ranking."""
        weights = {
            'CRITICAL': 100,
            'HIGH': 10,
            'MEDIUM': 1,
            'LOW': 0
        }
        return weights.get(severity, 0)

    def _extract_pr_number(self, pr_url: str) -> int:
        """Extract PR number from GitHub URL."""
        if '/pull/' in pr_url:
            return int(pr_url.split('/pull/')[1].split('/')[0])
        return 0

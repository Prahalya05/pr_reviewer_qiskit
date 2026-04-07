from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category
from ..context_graph import ContextGraph
from ..prompts.semantic_checker import select_probes_for_graph, run_probe
from ..config import FIDELITY_THRESHOLD

class SemanticAgent(BaseAgent):
    agent_id = 'SA-SEM'

    PROBE_ISSUE_MAP = {
        'bell_transpile': 'general transpiler correctness',
        'controlled_subgate': 'Issue #13118 — controlled sub-gate miscompilation',
        'unitary_synthesis': 'Issue #13972 — UnitaryGate synthesis drift (0.707)',
        'gate_control': 'Issue #15610 — Gate.control() Rust panic',
        'qft_round_trip': 'QFT round-trip fidelity',
    }

    def review(self, graph: ContextGraph) -> List[Finding]:
        if not (graph.has_transpiler_changes or graph.has_synthesis_changes):
            return []

        probes = select_probes_for_graph(graph)
        findings = []

        for probe_name in probes:
            result = run_probe(probe_name)

            if result.is_regression:
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity.CRITICAL,
                    category=Category.SEMANTIC,
                    file='',
                    line=None,
                    title=f"Semantic regression detected in probe: {probe_name}",
                    description=f"Fidelity {result.fidelity:.4f} below threshold {FIDELITY_THRESHOLD}. {self.PROBE_ISSUE_MAP.get(probe_name, '')}",
                    suggestion="Review transpiler changes for correctness",
                    evidence=f"Probe {probe_name} fidelity dropped to {result.fidelity:.4f}",
                    confidence=0.98,
                    probe_circuit=probe_name,
                    fidelity_before=1.0,
                    fidelity_after=result.fidelity
                ))

            elif result.error:
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity.MEDIUM,
                    category=Category.SEMANTIC,
                    file='',
                    line=None,
                    title=f"Semantic probe error: {probe_name}",
                    description=f"Probe {probe_name} failed with error: {result.error}",
                    suggestion="Run probe manually to isolate failure",
                    evidence=f"Error: {result.error}",
                    confidence=0.8,
                    probe_circuit=probe_name,
                    fidelity_before=1.0,
                    fidelity_after=result.fidelity if result.fidelity > 0 else 0.0
                ))

            # Note: passing results (not regression, no error) create NO finding

        return findings

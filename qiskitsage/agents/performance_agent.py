import json
from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category
from ..context_graph import ContextGraph
from ..prompts.performance_prompt import build_perf_user_prompt, PERF_SYSTEM_PROMPT

class PerformanceAgent(BaseAgent):
    agent_id = 'SA-PERF'

    def review(self, graph: ContextGraph) -> List[Finding]:
        python_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'python']
        if not python_files:
            return []

        findings = []

        # Static analysis: call-graph complexity check
        findings.extend(self._check_cascade_complexity(graph))

        # LLM-based analysis via Ollama
        user_prompt = build_perf_user_prompt(graph)
        content = self._llm_call(PERF_SYSTEM_PROMPT, user_prompt)

        # Strip ```json fences
        if content.strip().startswith('```'):
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            else:
                content = content.split('```')[1].split('```')[0].strip()

        try:
            data = json.loads(content.strip())
            for f in data.get('findings', []):
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity(f['severity']),
                    category=Category.PERFORMANCE,
                    file=f['file'],
                    line=f.get('line'),
                    title=f['title'],
                    description=f['description'],
                    suggestion=f['suggestion'],
                    evidence=f['evidence'],
                    confidence=float(f.get('confidence', 0.5))
                ))
            return findings
        except json.JSONDecodeError:
            print(f'[{self.agent_id}] JSON parse error')
            return findings

    def _check_cascade_complexity(self, graph: ContextGraph) -> List[Finding]:
        """Check if O(n^2) function is called from O(n) loop = CRITICAL."""
        findings = []

        for fn_qual in graph.changed_functions:
            if fn_qual not in graph.functions:
                continue

            fn = graph.functions[fn_qual]
            if fn.complexity_hint != 'O(n^2)':
                continue

            # Check callers
            for caller_qual in fn.called_by:
                if caller_qual not in graph.functions:
                    continue

                caller = graph.functions[caller_qual]
                if caller.complexity_hint in ('O(n)', 'O(n^2)'):
                    findings.append(Finding(
                        agent_id=self.agent_id,
                        severity=Severity.CRITICAL,
                        category=Category.PERFORMANCE,
                        file=fn.file_path,
                        line=fn.start_line,
                        title=f"Cascade complexity: {fn.qualified_name} is O(n^2) called from O(n) loop",
                        description=f"Function {fn.qualified_name} has O(n^2) complexity and is called from {caller.qualified_name} which has O(n) complexity",
                        suggestion=f"Rewrite {fn.qualified_name} to be O(n) or less, or inline it to avoid nested O(n^3) complexity",
                        evidence=f"Detected complexity: {fn.qualified_name}={fn.complexity_hint}, caller={caller.complexity_hint}",
                        confidence=0.9
                    ))

        return findings

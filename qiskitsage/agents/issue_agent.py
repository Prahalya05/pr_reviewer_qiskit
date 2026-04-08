import json
from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category

import logging
logger = logging.getLogger(__name__)

ISSUE_SYSTEM_PROMPT = """You are an expert Qiskit developer and Python software engineer.
You are analyzing a GitHub Issue report and must generate the exact Python code needed to fix the issue.

You will receive the Issue Title and the Issue Body.

Your task:
1. Understand the bug or feature request from the issue.
2. Determine what file/module in Qiskit is likely causing it (e.g. 'qiskit/quantum_info/operators/symplectic/pauli.py'). Do your best to guess accurately based on your knowledge of Qiskit's codebase structure.
3. Write the Python code fix that solves the issue.

Output ONLY valid JSON with a "findings" array. Each finding must be structured exactly like this:
{
  "findings": [
    {
      "file": "path/to/likely_file.py",
      "line": 1,
      "severity": "CRITICAL",
      "category": "SEMANTIC",
      "title": "Title of the fix",
      "description": "Explanation of what you are changing",
      "suggestion": "```python\\n# EXACT CODE FIX HERE\\n```",
      "evidence": "Evidence from the issue description",
      "confidence": 0.95
    }
  ]
}

No prose before or after the JSON. No markdown fences outside the JSON string values."""

class IssueAgent(BaseAgent):
    agent_id = 'SA-ISSUE'

    def review(self, graph) -> List[Finding]:
        # 'graph' here is actually an issue dictionary containing title and body
        user_prompt = f"ISSUE TITLE: {graph['issue_title']}\n\nISSUE BODY:\n{graph['issue_body']}"
        
        # Call LLM via Ollama
        content = self._llm_call(ISSUE_SYSTEM_PROMPT, user_prompt)

        # Strip ```json fences if present
        if content.strip().startswith('```'):
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            else:
                content = content.split('```')[1].split('```')[0].strip()

        try:
            data = json.loads(content.strip())
            findings = []
            for f in data.get('findings', []):
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity(f.get('severity', 'HIGH')),
                    category=Category.SEMANTIC,
                    file=f.get('file', 'unknown_file.py'),
                    line=f.get('line', 1),
                    title=f.get('title', 'Issue Code Generation'),
                    description=f.get('description', ''),
                    suggestion=f.get('suggestion', ''),
                    evidence=f.get('evidence', ''),
                    confidence=float(f.get('confidence', 0.9))
                ))
            return findings
        except json.JSONDecodeError:
            logger.info(f'[{self.agent_id}] JSON parse error in IssueAgent')
            return []

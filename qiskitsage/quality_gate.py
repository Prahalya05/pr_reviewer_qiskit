"""
QiskitSage Quality Gate
Filters findings by confidence threshold and uses LLM-as-judge
for HIGH and CRITICAL severity items.
"""

from typing import List
from .models import Finding, Severity
from .config import MIN_CONFIDENCE


class QualityGate:
    """Implements quality gates for filtering review findings."""

    def __init__(self):
        self.min_confidence = MIN_CONFIDENCE

    def filter_findings(self, findings: List[Finding]) -> List[Finding]:
        """
        Apply quality gate to filter findings.
        - Drop findings below confidence threshold
        - Apply LLM-as-judge for CRITICAL/HIGH findings
        """
        filtered = []

        for finding in findings:
            # Skip if below confidence threshold
            if finding.confidence < self.min_confidence:
                continue

            # Apply LLM-as-judge for HIGH and CRITICAL findings
            if finding.severity in (Severity.CRITICAL, Severity.HIGH):
                if self._llm_judge_approves(finding):
                    filtered.append(finding)
            else:
                # MEDIUM and LOW automatically pass
                filtered.append(finding)

        return filtered

    def _llm_judge_approves(self, finding: Finding) -> bool:
        """
        Use LLM to validate that a HIGH/CRITICAL finding is legitimate.
        This is a confidence filter to reduce false positives.
        Returns True if LLM confirms the finding, False otherwise.
        """
        # In a real implementation, this would call Claude to validate
        # For now, we accept all findings above threshold
        return True

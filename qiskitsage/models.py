from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class Severity(str, Enum):
    CRITICAL = 'CRITICAL'
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'

class Category(str, Enum):
    SEMANTIC = 'SEMANTIC'
    FFI_SAFETY = 'FFI_SAFETY'
    PERFORMANCE = 'PERFORMANCE'
    SYNTAX = 'SYNTAX'
    COMPLIANCE = 'COMPLIANCE'
    HISTORICAL = 'HISTORICAL'

@dataclass
class Finding:
    agent_id: str
    severity: Severity
    category: Category
    file: str
    line: Optional[int]
    title: str
    description: str
    suggestion: str
    evidence: str
    confidence: float  # 0.0–1.0
    # SA-SEM only
    probe_circuit: Optional[str] = None
    fidelity_before: Optional[float] = None
    fidelity_after: Optional[float] = None
    # SA-FFI only
    rust_severity: Optional[str] = None  # 'PANIC'|'MEMORY'|'STYLE'

@dataclass
class ReviewResult:
    pr_url: str
    pr_number: int
    findings: List[Finding]
    total_findings: int
    critical_count: int
    high_count: int
    semantic_regression_detected: bool
    ffi_risk_detected: bool
    agents_run: List[str]
    execution_time_seconds: float
    comment_markdown: str

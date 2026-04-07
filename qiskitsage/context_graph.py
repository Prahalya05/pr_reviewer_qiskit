from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class CommitRecord:
    sha: str  # 8-char short SHA
    message: str  # first line only
    author: str
    date: str  # ISO format
    is_fix: bool  # True if message contains fix/regression/bug/revert
    changed_files: List[str]

@dataclass
class FunctionNode:
    name: str
    qualified_name: str  # 'ClassName.method_name' or 'function_name'
    file_path: str
    start_line: int
    end_line: int
    source: str  # full source of this function
    language: str  # 'python' | 'rust'
    is_public: bool
    is_changed: bool
    calls: List[str]  # qualified_names this fn calls
    called_by: List[str]  # qualified_names that call this fn
    complexity_hint: str  # '' | 'O(n)' | 'O(n^2)' | 'O(n^3+)'
    has_docstring: bool
    docstring: Optional[str]
    return_type: Optional[str]
    param_types: Dict[str, str]  # param_name -> type annotation string

@dataclass
class ModuleNode:
    file_path: str
    language: str
    full_content: str  # complete file at base_sha (before PR)
    module_name: str
    imports: List[str]
    is_changed: bool
    functions: List[str]  # qualified_names
    test_file: Optional[str]
    commit_history: List[CommitRecord]  # last MAX_COMMIT_HISTORY commits touching this file
    regression_count: int  # how many commits in history contain fix/regression/bug

@dataclass
class ContextGraph:
    pr_number: int
    pr_title: str
    pr_body: str
    base_sha: str
    head_sha: str
    # Core graph
    modules: Dict[str, ModuleNode]  # file_path -> ModuleNode
    functions: Dict[str, FunctionNode]  # qualified_name -> FunctionNode
    # Subsets
    changed_files: List[str]
    changed_functions: List[str]
    caller_files: List[str]
    impact_radius: Dict[str, str]  # qualified_name -> 'HIGH'|'MEDIUM'|'LOW'
    # Classification flags
    has_rust_changes: bool
    has_transpiler_changes: bool
    has_synthesis_changes: bool
    has_quantum_info_changes: bool
    changed_modules: List[str]
    # Raw diff data
    raw_patches: Dict[str, str]  # file_path -> unified diff patch
    added_lines: Dict[str, List[str]]  # file_path -> list of added lines ('+' stripped)
    # History summary
    total_regression_commits: int  # total fix/regression commits across all changed files
    high_risk_files: List[str]  # files with regression_count >= 3
    # Build metadata
    build_time_seconds: float
    context_size_chars: int

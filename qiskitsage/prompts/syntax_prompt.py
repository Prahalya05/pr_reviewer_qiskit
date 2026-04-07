from .. import config

def build_syntax_user_prompt(graph):
    """Build user prompt for syntax agent with three sections: HISTORY, DIFF, FULL FILE, CALLERS."""
    parts = []

    # Header
    parts.append(f"PR #{graph.pr_number}: {graph.pr_title}")
    parts.append("")

    # Commit history risk
    if graph.total_regression_commits > 0:
        parts.append("=== COMMIT HISTORY RISK ===")
        python_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'python']
        for filename in python_files:
            count = graph.modules[filename].regression_count
            if count > 0:
                parts.append(f"{filename} — {count} regression commits in history")
        parts.append("")

    # For each changed Python file
    python_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'python']
    for filename in python_files:
        module = graph.modules[filename]

        # Diff section
        if filename in graph.raw_patches:
            parts.append(f"=== DIFF: {filename} ===")
            patch = graph.raw_patches[filename][:2000]
            if patch:
                parts.append(patch)
        parts.append("")

        # Full file section
        parts.append(f"=== FULL FILE: {filename} ===")
        parts.append(module.full_content[:6000])
        parts.append("")

    return "\n".join(parts)

SYNTAX_SYSTEM_PROMPT = """You are a syntax reviewer for Qiskit Python code. Check ONLY:
1. Missing Google-style docstrings on public functions
2. Missing type hints on parameters/returns
3. Bare `except:` clauses
4. Unused imports
5. Public API signature changes without deprecation

For each finding, output: {"file", "line", "severity", "category", "title", "description", "suggestion", "evidence", "confidence"}

You will receive:
- COMMIT HISTORY RISK (regression commit counts)
- DIFF: changed lines
- FULL FILE: complete file with surrounding context

DO NOT flag comments, whitespace, or line length. Focus ONLY on the 5 checks above.

Output ONLY valid JSON with a "findings" array. Maximum 8 findings. No prose before or after JSON. No markdown fences."""

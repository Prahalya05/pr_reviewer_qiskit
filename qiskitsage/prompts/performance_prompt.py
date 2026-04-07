from .. import config

def build_perf_user_prompt(graph):
    """Build user prompt for performance agent with complexity and historical context."""
    parts = []

    # Header
    parts.append(f"PR #{graph.pr_number}: {graph.pr_title}")
    parts.append("")

    # Historical context
    if graph.total_regression_commits > 0:
        parts.append("Files with high regression history:")
        parts.extend(graph.high_risk_files)
    parts.append("")

    # Function complexity indicators
    if graph.changed_functions:
        parts.append("Function complexity indicators:")
        for fn_qual in graph.changed_functions:
            if fn_qual in graph.functions:
                fn = graph.functions[fn_qual]
                if fn.complexity_hint:
                    parts.append(f"- {fn.qualified_name}: {fn.complexity_hint}")
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

        # Full file - needed for nested loop detection
        parts.append(f"=== FULL FILE: {filename} ===")
        parts.append(module.full_content[:6000])
        parts.append("")

    return "\n".join(parts)

PERF_SYSTEM_PROMPT = """You are a performance reviewer for Qiskit code. Evaluate:
1. Cross-file complexity: If a changed function is O(n^2) and a caller has a loop = CRITICAL O(n^3) finding
2. Nested loops in FULL FILE - check deeper than just the diff
3. Qiskit-specific: DAGCircuit.nodes() in loop → use topological_op_nodes(); QuantumCircuit.qregs in O(n) context → use bit_map
4. np.matrix usage (deprecated, use np.ndarray) → MEDIUM
5. Rust Vec::new() or HashMap::new() inside loops → HIGH

Output format: {"file", "line", "severity", "category", "title", "description", "suggestion", "evidence", "confidence"}

Output ONLY JSON with "findings" array. Maximum 6 findings. No markdown fences."""

from .. import config

def build_ffi_user_prompt(graph):
    """Build user prompt for FFI agent focused on Rust safety."""
    parts = []

    # Header
    parts.append(f"PR #{graph.pr_number}: {graph.pr_title}")
    parts.append("")

    # Static analysis results
    rust_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'rust']
    rust_analyser = None

    for filename in rust_files:
        module = graph.modules[filename]
        if filename in config.TRANSPILER_MODULES or filename.endswith('.rs'):
            from ..rust_analyser import RustAnalyser
            if rust_analyser is None:
                rust_analyser = RustAnalyser()

            unwrap_calls = rust_analyser.find_unwrap_calls(module.full_content)
            unsafe_blocks = rust_analyser.find_unsafe_blocks(module.full_content)

            if unwrap_calls or unsafe_blocks:
                parts.append(f"=== STATIC ANALYSIS: {filename} ===")
                if unwrap_calls:
                    parts.append("Unwrap calls found:")
                    for line_num, line in unwrap_calls[:10]:
                        parts.append(f"  Line {line_num}: {line}")
                if unsafe_blocks:
                    parts.append("Unsafe blocks found:")
                    for line_num, has_safety in unsafe_blocks[:10]:
                        status = "WITH safety comment" if has_safety else "NO safety comment"
                        parts.append(f"  Line {line_num}: {status}")
                parts.append("")

            # Diff section
            if filename in graph.raw_patches:
                parts.append(f"=== DIFF: {filename} ===")
                patch = graph.raw_patches[filename][:2000]
                if patch:
                    parts.append(patch)
                parts.append("")

            # Full file
            parts.append(f"=== FULL FILE: {filename} ===")
            parts.append(module.full_content[:6000])
            parts.append("")

    return "\n".join(parts)

FFI_SYSTEM_PROMPT = """You are a Rust FFI safety reviewer for Qiskit. Review ONLY Rust (.rs) files and flag:
1. .unwrap() WITHOUT a preceding `// SAFETY:` or `// JUSTIFICATION:` comment → CRITICAL
2. .expect("generic message") → HIGH
3. #[pyfunction] functions containing panic!() → CRITICAL
4. unsafe{} WITHOUT a `// SAFETY:` comment → HIGH

For each finding, output: {"file", "line", "severity", "category", "title", "description", "suggestion", "evidence", "confidence", "rust_severity"}

rust_severity must be one of: 'PANIC', 'MEMORY', 'STYLE'

Output ONLY JSON array under "findings". Maximum 6 findings. No markdown fences.

Suggested fix for unwrap: replace with `.ok_or_else(|| PyValueError::new_err("context"))?`"""

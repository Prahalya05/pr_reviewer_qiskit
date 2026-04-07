You are building QiskitSage — a context-aware multi-agent PR review backend for github.com/Qiskit/qiskit.

---

## WHAT YOU ARE BUILDING

A Python backend that accepts a GitHub PR URL, builds complete context of the repository (present state + commit history), runs four specialist review agents over that context, and returns a ranked list of findings as JSON and a formatted GitHub markdown comment.

This is NOT a GitHub Actions workflow. It is a standalone Python program run as:
  python main.py https://github.com/Qiskit/qiskit/pull/NNNN

---

## EXACT TECHNOLOGY STACK

- Python 3.11+
- anthropic>=0.25.0 (claude-sonnet-4-20250514 for all LLM calls)
- PyGithub>=2.1.1 (GitHub API)
- qiskit>=1.2.0 (semantic probe execution)
- numpy>=1.26.0
- tree-sitter>=0.21.0 + tree-sitter-rust>=0.21.0 (Rust AST parsing)
- python-dotenv>=1.0.0
- pytest>=7.4.0

Environment variables (loaded from .env):
  ANTHROPIC_API_KEY=...
  GITHUB_TOKEN=...

---

## EXACT FILE STRUCTURE

Create every file listed. Do not create any file not listed.

```
qiskitsage/
  __init__.py              # empty
  config.py                # env vars, thresholds, constants
  models.py                # Severity, Category, Finding, ReviewResult dataclasses
  context_graph.py         # FunctionNode, ModuleNode, CommitRecord, ContextGraph dataclasses — pure data, zero logic
  context_builder.py       # builds ContextGraph — THE MOST IMPORTANT FILE
  ast_analyser.py          # Python AST: extracts functions, calls, complexity, type hints
  rust_analyser.py         # tree-sitter Rust: extracts fn nodes, unwrap calls, unsafe blocks
  github_client.py         # GitHub API: PR data, full file content, caller search, commit history
  orchestrator.py          # wires CB + agents, parallel exec, merge, dedup, rank, gate, render
  quality_gate.py          # confidence filter + LLM-as-judge for HIGH/CRITICAL findings
  renderer.py              # ReviewResult → GitHub markdown string
  agents/
    __init__.py            # empty
    base_agent.py          # BaseAgent ABC: review(ContextGraph) -> List[Finding]
    syntax_agent.py        # SA-SYN
    performance_agent.py   # SA-PERF
    semantic_agent.py      # SA-SEM
    ffi_agent.py           # SA-FFI
  prompts/
    __init__.py            # empty
    syntax_prompt.py       # SYNTAX_SYSTEM_PROMPT + build_syntax_user_prompt(graph)
    performance_prompt.py  # PERF_SYSTEM_PROMPT + build_perf_user_prompt(graph)
    ffi_prompt.py          # FFI_SYSTEM_PROMPT + build_ffi_user_prompt(graph)
    judge_prompt.py        # JUDGE_SYSTEM_PROMPT
  semantic_checker.py      # probe scripts + run_probe() + select_probes_for_graph()
  main.py                  # CLI entry point
  requirements.txt
  tests/
    test_units.py          # AST analyser, Rust analyser, quality gate, renderer unit tests
    test_integration.py    # end-to-end tests against real Qiskit PRs (marked @pytest.mark.integration)
```

---

## DATA MODELS (implement exactly as specified)

### config.py
```python
import os
from dotenv import load_dotenv
load_dotenv()

ANTHROPIC_API_KEY  = os.environ['ANTHROPIC_API_KEY']
GITHUB_TOKEN       = os.environ['GITHUB_TOKEN']
LLM_MODEL          = 'claude-sonnet-4-20250514'
LLM_MAX_TOKENS     = 4096
LLM_TEMPERATURE    = 0.1
MIN_CONFIDENCE     = 0.70
MAX_FINDINGS       = 12
FIDELITY_THRESHOLD = 0.9999
MAX_CALLER_SEARCHES = 5       # max public functions to search callers for (GitHub rate limit)
MAX_COMMIT_HISTORY  = 10      # commits per file for historical context
TRANSPILER_MODULES = ['qiskit/transpiler/', 'qiskit/synthesis/', 'crates/synthesis/']
MODULE_MAP = {
    'qiskit/transpiler':   'transpiler',
    'qiskit/synthesis':    'synthesis',
    'crates/synthesis':    'synthesis_rust',
    'qiskit/qpy':          'qpy',
    'qiskit/quantum_info': 'quantum_info',
    'qiskit/circuit':      'circuit',
}
```

### models.py
```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class Severity(str, Enum):
    CRITICAL = 'CRITICAL'
    HIGH     = 'HIGH'
    MEDIUM   = 'MEDIUM'
    LOW      = 'LOW'

class Category(str, Enum):
    SEMANTIC    = 'SEMANTIC'
    FFI_SAFETY  = 'FFI_SAFETY'
    PERFORMANCE = 'PERFORMANCE'
    SYNTAX      = 'SYNTAX'
    COMPLIANCE  = 'COMPLIANCE'
    HISTORICAL  = 'HISTORICAL'

@dataclass
class Finding:
    agent_id:    str
    severity:    Severity
    category:    Category
    file:        str
    line:        Optional[int]
    title:       str
    description: str
    suggestion:  str
    evidence:    str
    confidence:  float         # 0.0–1.0
    # SA-SEM only
    probe_circuit:     Optional[str]   = None
    fidelity_before:   Optional[float] = None
    fidelity_after:    Optional[float] = None
    # SA-FFI only
    rust_severity:     Optional[str]   = None   # 'PANIC'|'MEMORY'|'STYLE'

@dataclass
class ReviewResult:
    pr_url:                      str
    pr_number:                   int
    findings:                    List[Finding]
    total_findings:              int
    critical_count:              int
    high_count:                  int
    semantic_regression_detected: bool
    ffi_risk_detected:           bool
    agents_run:                  List[str]
    execution_time_seconds:      float
    comment_markdown:            str
```

### context_graph.py
```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class CommitRecord:
    sha:         str        # 8-char short SHA
    message:     str        # first line only
    author:      str
    date:        str        # ISO format
    is_fix:      bool       # True if message contains fix/regression/bug/revert
    changed_files: List[str]

@dataclass
class FunctionNode:
    name:             str
    qualified_name:   str      # 'ClassName.method_name' or 'function_name'
    file_path:        str
    start_line:       int
    end_line:         int
    source:           str      # full source of this function
    language:         str      # 'python' | 'rust'
    is_public:        bool
    is_changed:       bool
    calls:            List[str]        # qualified_names this fn calls
    called_by:        List[str]        # qualified_names that call this fn
    complexity_hint:  str              # '' | 'O(n)' | 'O(n^2)' | 'O(n^3+)'
    has_docstring:    bool
    docstring:        Optional[str]
    return_type:      Optional[str]
    param_types:      Dict[str, str]   # param_name -> type annotation string

@dataclass
class ModuleNode:
    file_path:      str
    language:       str
    full_content:   str        # complete file at base_sha (before PR)
    module_name:    str
    imports:        List[str]
    is_changed:     bool
    functions:      List[str]  # qualified_names
    test_file:      Optional[str]
    commit_history: List[CommitRecord]  # last MAX_COMMIT_HISTORY commits touching this file
    regression_count: int       # how many commits in history contain fix/regression/bug

@dataclass
class ContextGraph:
    pr_number:                int
    pr_title:                 str
    pr_body:                  str
    base_sha:                 str
    head_sha:                 str
    # Core graph
    modules:                  Dict[str, ModuleNode]    # file_path -> ModuleNode
    functions:                Dict[str, FunctionNode]  # qualified_name -> FunctionNode
    # Subsets
    changed_files:            List[str]
    changed_functions:        List[str]
    caller_files:             List[str]
    impact_radius:            Dict[str, str]  # qualified_name -> 'HIGH'|'MEDIUM'|'LOW'
    # Classification flags
    has_rust_changes:         bool
    has_transpiler_changes:   bool
    has_synthesis_changes:    bool
    has_quantum_info_changes: bool
    changed_modules:          List[str]
    # Raw diff data
    raw_patches:              Dict[str, str]        # file_path -> unified diff patch
    added_lines:              Dict[str, List[str]]  # file_path -> list of added lines ('+' stripped)
    # History summary
    total_regression_commits: int    # total fix/regression commits across all changed files
    high_risk_files:          List[str]  # files with regression_count >= 3
    # Build metadata
    build_time_seconds:       float
    context_size_chars:       int
```

---

## IMPLEMENTATION: IMPLEMENT THESE FILES IN THIS ORDER

### Step 1: github_client.py

Implement class `GitHubClient` with exactly these methods:

**fetch_pr_data(pr_url: str) -> dict**
- Parse URL: split on '/', extract owner=parts[-4], repo_name=parts[-3], pr_number=int(parts[-1])
- Use PyGithub: g = Github(GITHUB_TOKEN), repo = g.get_repo(f'{owner}/{repo_name}'), pr = repo.get_pull(pr_number)
- Call pr.get_files(), convert to list
- Return dict with keys: pr_number, pr_title, pr_body, base_sha, head_sha, files, repo

**fetch_full_file(repo, file_path: str, ref: str) -> Optional[str]**
- repo.get_contents(file_path, ref=ref).decoded_content.decode('utf-8')
- Return None on GithubException (new file added in PR)
- IMPORTANT: always fetch at base_sha (before PR), not head_sha

**fetch_commit_history(repo, file_path: str, max_commits: int = 10) -> List[CommitRecord]**
- repo.get_commits(path=file_path), iterate up to max_commits
- For each: CommitRecord(sha=c.sha[:8], message=first_line, author=c.commit.author.name, date=c.commit.author.date.isoformat(), is_fix=any keyword in ['fix','regression','bug','revert'] in message.lower(), changed_files=[f.filename for f in c.files[:10]])
- Catch GithubException, return [] on failure

**search_callers(repo, function_name: str, exclude_files: List[str]) -> List[str]**
- query = f'{function_name}( repo:{repo.full_name} language:Python'
- self.g.search_code(query), return [item.path for item in results[:10] if item.path not in exclude_files]
- Catch GithubException, return [] on failure — do NOT raise

### Step 2: ast_analyser.py

Implement class `PythonASTAnalyser` with method `analyse(source: str, file_path: str) -> List[FunctionNode]`.

Use Python built-in `ast` module only — no external dependencies.

Walk the AST. For each `ast.FunctionDef` or `ast.AsyncFunctionDef`:
- Extract `qualified_name`: if inside a ClassDef, prefix with ClassName
- Extract `source`: lines[node.lineno-1 : node.end_lineno] joined with '\n'
- Extract `docstring`: ast.get_docstring(node)
- Extract `return_type`: ast.unparse(node.returns) if node.returns else None
- Extract `param_types`: {arg.arg: ast.unparse(arg.annotation) for arg in node.args.args if arg.annotation}
- Extract `calls`: walk the function body, collect ast.Name.id and ast.Attribute.attr from ast.Call nodes, deduplicate
- Detect `complexity_hint`: walk for nested loops using a depth counter — depth 0='', 1='O(n)', 2='O(n^2)', 3+='O(n^3+)'
- Set `is_changed=False` (ContextBuilder sets this after)
- Set `called_by=[]` (ContextBuilder populates this after)

### Step 3: rust_analyser.py

Implement class `RustAnalyser`.

**analyse(source: str, file_path: str) -> List[FunctionNode]**
Try tree-sitter first:
```python
try:
    from tree_sitter import Language, Parser
    import tree_sitter_rust as tsrust
    RUST_LANGUAGE = Language(tsrust.language())
    # walk tree.root_node, find 'function_item' nodes, extract name + source
except ImportError:
    # fallback: regex r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)'
```
For each function: set language='rust', is_public=('pub' in source[:50]), calls=[], called_by=[], complexity_hint from loop depth counting

**find_unwrap_calls(source: str) -> List[Tuple[int, str]]**
Return [(line_num, line.strip())] for every line containing '.unwrap()' or '.expect('

**find_unsafe_blocks(source: str) -> List[Tuple[int, bool]]**
Return [(line_num, has_safety_comment)] for every line containing 'unsafe {' or 'unsafe{'
has_safety_comment = previous non-empty line starts with '// SAFETY:' or '/// SAFETY:'

### Step 4: context_builder.py

Implement class `ContextBuilder` with method `build(pr_url: str) -> ContextGraph`.

Four sequential stages. Use `concurrent.futures.ThreadPoolExecutor(max_workers=6)` for I/O within stages.

**Stage 1 — Skeleton from diff**
For each file in pr_data['files']:
- Create ModuleNode with: file_path, language (detect from extension: .py='python', .rs='rust'), full_content='', module_name (path → dotted module), imports=[], is_changed=True, functions=[], test_file=('test/python/'+filename without extension+'/'), commit_history=[], regression_count=0
- Record raw_patches[f.filename] = f.patch or ''
- Record added_lines[f.filename] = [l[1:] for l in patch.split('\n') if l.startswith('+') and not l.startswith('+++')]

**Stage 2 — Full file content + AST parsing + commit history (parallel)**
For each changed file, concurrently:
- Fetch full_content via fetch_full_file(repo, file_path, base_sha)
- Parse AST: PythonASTAnalyser for .py, RustAnalyser for .rs → populate all_functions dict
- Fetch commit_history via fetch_commit_history(repo, file_path, MAX_COMMIT_HISTORY)
- Count regression_count = sum(1 for c in history if c.is_fix)
- Mark fn.is_changed = True for all extracted functions
- Set modules[fp].functions = [fn.qualified_name for fn in fns]

**Stage 3 — Caller search (GitHub Code Search)**
For public changed functions only (not starting with _), up to MAX_CALLER_SEARCHES:
- Call search_callers(repo, fn.name, changed_files)
- Collect caller_files set

**Stage 4 — Fetch caller files + populate called_by relationships**
For each caller_file not already in modules:
- Fetch content, parse AST, create ModuleNode with is_changed=False
- After all fetched: for each fn in all_functions, for each name in fn.calls, find matching functions in all_functions by .name and mark target.called_by.append(fn.qualified_name)

**Impact radius**
For each changed function: HIGH if len(called_by)>5, MEDIUM if >1, LOW otherwise

**Historical summary**
total_regression_commits = sum(m.regression_count for m in modules.values())
high_risk_files = [fp for fp,m in modules.items() if m.regression_count >= 3]

**Build and return ContextGraph** with all computed fields.

### Step 5: agents/base_agent.py

```python
from abc import ABC, abstractmethod
from typing import List
from context_graph import ContextGraph
from models import Finding

class BaseAgent(ABC):
    agent_id: str = 'BASE'

    @abstractmethod
    def review(self, graph: ContextGraph) -> List[Finding]:
        ...

    def _safe_review(self, graph: ContextGraph) -> List[Finding]:
        try:
            return self.review(graph)
        except Exception as e:
            print(f'[{self.agent_id}] Error: {e}')
            return []
```

### Step 6: prompts/syntax_prompt.py

SYNTAX_SYSTEM_PROMPT must instruct the LLM to:
- Check ONLY: (1) missing Google-style docstrings on public functions, (2) missing type hints on parameters/returns, (3) bare `except:` clauses, (4) unused imports, (5) public API signature changes without deprecation
- Receive three context sections in user prompt: DIFF, FULL FILE, CALLERS
- Output ONLY valid JSON: `{"findings": [{"file","line","severity","category","title","description","suggestion","evidence","confidence"}]}`
- No prose before or after JSON. No markdown fences. Maximum 8 findings.

`build_syntax_user_prompt(graph: ContextGraph) -> str` must assemble:
```
PR #{graph.pr_number}: {graph.pr_title}

=== COMMIT HISTORY RISK ===
[for each changed Python file: "file.py — {regression_count} regression commits in history"]

=== DIFF: {filename} ===
{raw_patches[filename][:2000]}

=== FULL FILE: {filename} ===
{modules[filename].full_content[:6000]}

=== CALLERS OF {qualified_name} ===
[for up to 3 callers: show caller.source[:400]]
```

### Step 7: prompts/performance_prompt.py

PERF_SYSTEM_PROMPT must instruct the LLM to:
- Use Section C (callers) to detect cross-file complexity: if changed function is O(n^2) and caller has a loop = CRITICAL O(n^3) finding
- Check nested loops in FULL FILE (Section B), not just the diff
- Flag np.matrix usage (deprecated, use np.ndarray) as MEDIUM
- Flag Rust Vec::new() or HashMap::new() inside loops as HIGH
- Qiskit-specific: DAGCircuit.nodes() in loop → use topological_op_nodes(); QuantumCircuit.qregs in O(n) context → use bit_map
- Output same JSON schema as SA-SYN. Maximum 6 findings.

`build_perf_user_prompt(graph: ContextGraph) -> str` must include:
- For each changed function with complexity_hint != '': state the detected complexity
- DIFF + FULL FILE + CALLERS sections (same structure as syntax prompt)
- Historical context: "Files with high regression history: {high_risk_files}"

### Step 8: prompts/ffi_prompt.py

FFI_SYSTEM_PROMPT must instruct the LLM to:
- ONLY review Rust (.rs) files
- Flag: (1) .unwrap() without a preceding `// SAFETY:` or `// JUSTIFICATION:` comment → CRITICAL, (2) .expect("generic message") → HIGH, (3) #[pyfunction] functions containing panic!() → CRITICAL, (4) unsafe{} without `// SAFETY:` comment → HIGH
- Suggest: replace .unwrap() with `.ok_or_else(|| PyValueError::new_err("context"))?`
- Add `rust_severity` field to each finding: 'PANIC'|'MEMORY'|'STYLE'
- Output same JSON schema. Maximum 6 findings.

`build_ffi_user_prompt(graph: ContextGraph) -> str` must include:
- Static analysis pre-computed results: list all unwrap calls found by RustAnalyser, list all unsafe blocks found by RustAnalyser
- DIFF + FULL FILE sections for Rust files only

### Step 9: agents/syntax_agent.py

```python
class SyntaxAgent(BaseAgent):
    agent_id = 'SA-SYN'

    def review(self, graph: ContextGraph) -> List[Finding]:
        python_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'python']
        if not python_files: return []
        # Build prompt from graph (not just diff)
        user_prompt = build_syntax_user_prompt(graph)
        # Call Anthropic API
        resp = self.client.messages.create(model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE, system=SYNTAX_SYSTEM_PROMPT,
            messages=[{'role':'user','content':user_prompt}])
        # Parse JSON response, return List[Finding]
        # Strip ```json fences if present before json.loads()
        # Catch json.JSONDecodeError, return [] on failure
```

### Step 10: agents/performance_agent.py

Same structure as SyntaxAgent. Additionally, before calling LLM:
- Run call-graph complexity check: for each changed function with complexity_hint='O(n^2)', check if any function in called_by has complexity_hint in ('O(n)','O(n^2)'). If so, create a CRITICAL Finding directly (no LLM needed for this) with title="Cascade complexity: {fn.qualified_name} is O(n^2) called from O(n) loop in {caller.qualified_name}"
- Then also run LLM-based check for additional findings
- Return both static and LLM findings combined

### Step 11: agents/ffi_agent.py

- Only runs if graph.has_rust_changes is True
- Before LLM call, run RustAnalyser.find_unwrap_calls() and find_unsafe_blocks() on full_content of each Rust file
- Cross-reference results against added_lines to find NEW unwraps (in added lines only)
- Create Finding directly for each new unwrap without a safety comment (CRITICAL, no LLM needed)
- Also create Finding directly for each unsafe block without safety comment (HIGH)
- Then run LLM over full Rust context for deeper analysis
- Combine static + LLM findings

### Step 12: semantic_checker.py

Five probe scripts as string literals in dict `PROBES`:

**'bell_transpile'**: Creates Bell circuit, compares Statevector before/after transpile(basis_gates=['cx','u'], optimization_level=2, seed_transpiler=42), prints JSON `{"probe":"bell_transpile","fidelity":float}`

**'controlled_subgate'**: Creates 3-qubit circuit with controlled sub-gate (sub.to_gate().control(1)), compares statevector before/after transpile(optimization_level=2, seed_transpiler=42). Targets Issue #13118. Prints JSON.

**'unitary_synthesis'**: Creates circuit with UnitaryGate(np.array([[1,0,1,0],[0,1,0,1],[1,0,-1,0],[0,1,0,-1]],dtype=complex)/np.sqrt(2)), adds H gate, compares before/after transpile. Also checks Operator.equiv(). Targets Issue #13972. Prints JSON with both fidelity and operator_equiv fields.

**'gate_control'**: Creates 4-qubit UnitaryGate(np.eye(16)), calls .control(), catches any exception. Prints `{"probe":"gate_control","fidelity":1.0,"panic":false}` or `{"fidelity":0.0,"panic":true,"error":"..."}`. Targets Issue #15610.

**'qft_round_trip'**: Uses QFT(4), compares before/after transpile(optimization_level=3). Prints JSON.

`run_probe(name: str, timeout: int = 45) -> ProbeResult`:
- subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=timeout)
- Parse JSON from stdout
- Return ProbeResult(probe_name, function_under_test='transpiler', fidelity=data['fidelity'], is_regression=fidelity<FIDELITY_THRESHOLD, error=None|message)

`select_probes_for_graph(graph: ContextGraph) -> List[str]`:
- Always include: ['bell_transpile']
- If 'transpiler' in graph.changed_modules: add 'controlled_subgate', 'qft_round_trip'
- If 'synthesis' in graph.changed_modules or 'synthesis_rust' in graph.changed_modules: add 'unitary_synthesis', 'gate_control'
- If any changed function name contains 'qs_decomposition': add 'gate_control' if not present
- Return deduplicated list

### Step 13: agents/semantic_agent.py

```python
class SemanticAgent(BaseAgent):
    agent_id = 'SA-SEM'

    PROBE_ISSUE_MAP = {
        'bell_transpile':    'general transpiler correctness',
        'controlled_subgate':'Issue #13118 — controlled sub-gate miscompilation',
        'unitary_synthesis': 'Issue #13972 — UnitaryGate synthesis drift (0.707)',
        'gate_control':      'Issue #15610 — Gate.control() Rust panic',
        'qft_round_trip':    'QFT round-trip fidelity',
    }

    def review(self, graph: ContextGraph) -> List[Finding]:
        if not (graph.has_transpiler_changes or graph.has_synthesis_changes):
            return []
        probes = select_probes_for_graph(graph)
        results = [run_probe(p) for p in probes]
        # For each result with is_regression=True: create CRITICAL Finding
        # For each result with error!=None: create MEDIUM Finding
        # For passing results: create NO finding (do not report passing probes)
        # Finding.confidence = 0.98 for execution-backed findings
        # Finding.probe_circuit = probe name
        # Finding.fidelity_before = 1.0 (expected), fidelity_after = actual
```

### Step 14: quality_gate.py

```python
class QualityGate:
    def filter(self, findings: List[Finding]) -> List[Finding]:
        result = []
        for f in findings:
            if f.severity == Severity.CRITICAL:
                result.append(f)    # CRITICAL always passes
                continue
            if f.confidence < MIN_CONFIDENCE:
                continue            # drop low confidence
            if f.severity == Severity.HIGH:
                if self._is_factual(f):
                    result.append(f)
            else:
                result.append(f)
        return result

    def _is_factual(self, f: Finding) -> bool:
        # Call Anthropic API with JUDGE_SYSTEM_PROMPT
        # Prompt: "Finding: {f.title}\nEvidence: {f.evidence}\nFile: {f.file}"
        # Response must be JSON: {"verdict": "FACTUAL"|"NOT_FACTUAL"}
        # Return True if FACTUAL, True on any error (fail open)
        # max_tokens=50, temperature=0.0
```

JUDGE_SYSTEM_PROMPT: "You are a factual accuracy judge for code review comments. Given a finding and its evidence, respond ONLY with JSON: {\"verdict\": \"FACTUAL\"} or {\"verdict\": \"NOT_FACTUAL\"}. FACTUAL means every line number, function name, and described behaviour is verifiable from the evidence text. No hallucinated identifiers."

### Step 15: orchestrator.py

```python
class Orchestrator:
    def review_pr(self, pr_url: str) -> ReviewResult:
        # Step 1: Build ContextGraph
        graph = ContextBuilder().build(pr_url)

        # Step 2: Select agents
        to_run = ['SA-SYN', 'SA-PERF']
        if graph.has_rust_changes: to_run.append('SA-FFI')
        if graph.has_transpiler_changes or graph.has_synthesis_changes: to_run.append('SA-SEM')

        # Step 3: Run SA-SYN, SA-PERF, SA-FFI in parallel via ThreadPoolExecutor
        # Run SA-SEM serially after (it runs subprocess probes)

        # Step 4: Quality gate
        filtered = QualityGate().filter(all_findings)

        # Step 5: Deduplicate
        # Keep one finding per (file, line, category) — prefer higher severity

        # Step 6: Sort by severity (CRITICAL first), then by confidence descending
        severity_order = {Severity.CRITICAL:0, Severity.HIGH:1, Severity.MEDIUM:2, Severity.LOW:3}
        filtered.sort(key=lambda f: (severity_order[f.severity], -f.confidence))

        # Step 7: Cap at MAX_FINDINGS

        # Step 8: Return ReviewResult with comment_markdown=render_comment(filtered, graph)
```

### Step 16: renderer.py

`render_comment(findings: List[Finding], graph: ContextGraph) -> str`

Output must:
- Start with `## QiskitSage Review`
- Include summary line: "Found N issues: X critical, Y high-priority"
- If graph.total_regression_commits > 0: add "⚠️ Historical context: N regression-related commits found in changed files" 
- If graph.high_risk_files: list them as "High-risk files (3+ past regressions): ..."
- Group findings by severity with emoji headers: 🔴 CRITICAL, 🟠 HIGH, 🟡 MEDIUM, 🔵 LOW
- For each finding: bold title, code-quoted file:line, description, suggested fix in appropriate code fence (```python or ```rust)
- End with agents_run list and execution time
- Total length must be < 65536 characters (GitHub comment limit)
- If no findings: return "## QiskitSage Review\n\n✅ No issues found in this PR."

### Step 17: main.py

```python
import sys
from orchestrator import Orchestrator

def main():
    if len(sys.argv) < 2:
        print('Usage: python main.py <PR_URL>')
        print('Example: python main.py https://github.com/Qiskit/qiskit/pull/15610')
        sys.exit(1)
    result = Orchestrator().review_pr(sys.argv[1])
    print(result.comment_markdown)
    if '--json' in sys.argv:
        import json, dataclasses
        print(json.dumps(dataclasses.asdict(result), default=str, indent=2))

if __name__ == '__main__':
    main()
```

---

## TESTS TO WRITE

### tests/test_units.py (no API keys required)

```python
class TestASTAnalyser:
    def test_extracts_function_names(self): ...         # 'def foo' -> FunctionNode(name='foo')
    def test_extracts_qualified_name_in_class(self): ... # class A: def foo -> 'A.foo'
    def test_detects_type_hints(self): ...               # (x: int) -> str → param_types={'x':'int'}, return_type='str'
    def test_detects_nested_loop_as_on2(self): ...       # for in for → complexity_hint='O(n^2)'
    def test_extracts_calls(self): ...                   # def foo(): bar() → calls=['bar']
    def test_detects_docstring(self): ...                # """doc""" → has_docstring=True

class TestRustAnalyser:
    def test_finds_unwrap_calls(self): ...               # '.unwrap()' on line 2 → [(2, ...)]
    def test_no_false_positive_on_question_mark(self): ... # '?' operator → []
    def test_finds_unsafe_without_comment(self): ...     # unsafe { → (line, False)
    def test_finds_unsafe_with_safety_comment(self): ... # // SAFETY: ...\n unsafe { → (line, True)

class TestQualityGate:
    def test_critical_always_passes(self): ...           # CRITICAL + confidence=0.1 → passes
    def test_low_confidence_medium_dropped(self): ...    # MEDIUM + confidence=0.3 → dropped
    def test_high_confidence_medium_passes(self): ...    # MEDIUM + confidence=0.9 → passes

class TestRenderer:
    def test_empty_findings_returns_ok(self): ...        # [] → contains 'No issues'
    def test_critical_finding_in_output(self): ...       # CRITICAL finding → 'CRITICAL' in output
    def test_output_under_github_limit(self): ...        # len(comment) < 65536
    def test_starts_with_header(self): ...               # startswith('## QiskitSage Review')

class TestSemanticChecker:
    def test_bell_probe_runs(self): ...                  # error is None, 0.0 <= fidelity <= 1.0
    def test_controlled_subgate_probe_runs(self): ...
    def test_unitary_synthesis_probe_runs(self): ...
    def test_gate_control_probe_runs(self): ...
    def test_qft_probe_runs(self): ...
```

### tests/test_integration.py (requires ANTHROPIC_API_KEY + GITHUB_TOKEN)

Mark all with `@pytest.mark.integration`

```python
def test_context_graph_built_for_simple_pr(self):
    g = ContextBuilder().build('https://github.com/Qiskit/qiskit/pull/12113')
    assert g.pr_number == 12113
    assert len(g.functions) > 0
    assert len(g.modules) > 0
    assert g.context_size_chars > 0
    assert any(m.commit_history for m in g.modules.values())  # history populated

def test_commit_history_populated(self):
    g = ContextBuilder().build('https://github.com/Qiskit/qiskit/pull/12113')
    changed_mods = [m for fp,m in g.modules.items() if m.is_changed]
    assert all(len(m.commit_history) > 0 for m in changed_mods)

def test_rust_pr_has_rust_functions(self):
    g = ContextBuilder().build('https://github.com/Qiskit/qiskit/pull/15610')
    assert g.has_rust_changes is True
    rust_fns = [f for f in g.functions.values() if f.language == 'rust']
    assert len(rust_fns) > 0

def test_call_graph_has_calls(self):
    g = ContextBuilder().build('https://github.com/Qiskit/qiskit/pull/12113')
    assert sum(len(f.calls) for f in g.functions.values()) > 0

def test_full_review_produces_valid_result(self):
    r = Orchestrator().review_pr('https://github.com/Qiskit/qiskit/pull/12113')
    assert isinstance(r, ReviewResult)
    assert r.comment_markdown.startswith('## QiskitSage Review')
    assert len(r.comment_markdown) < 65536
    assert r.execution_time_seconds > 0

def test_ffi_agent_activates_on_rust_pr(self):
    r = Orchestrator().review_pr('https://github.com/Qiskit/qiskit/pull/15610')
    assert 'SA-FFI' in r.agents_run

def test_semantic_agent_activates_on_transpiler_pr(self):
    r = Orchestrator().review_pr('https://github.com/Qiskit/qiskit/pull/13118')
    assert 'SA-SEM' in r.agents_run
```

---

## CRITICAL IMPLEMENTATION RULES

1. **Never invent APIs.** Use only: PyGithub, anthropic, qiskit, numpy, ast (builtin), tree-sitter, subprocess, concurrent.futures, json, re, dataclasses, typing, enum, os, sys, time.

2. **All LLM calls must output JSON only.** System prompts must say: "Output ONLY valid JSON. No prose before or after. No markdown fences." Parse with `json.loads(raw.strip())`. Strip ```` ```json ``` ```` fences before parsing if present despite instructions.

3. **All LLM output fields must match exactly.** Every Finding field must be populated from the LLM JSON response. Map missing fields to defaults (line=None, confidence=0.5).

4. **Never raise from _safe_review.** Catch all exceptions in `BaseAgent._safe_review`, print error message, return [].

5. **GitHub rate limits.** `search_callers` can fail — always catch GithubException and return []. `fetch_commit_history` can fail — always return []. `fetch_full_file` returns None on missing file — handle with `if not content: continue`.

6. **Semantic probes run in subprocess.** Every probe script must be completely self-contained: import everything it needs, print JSON to stdout, exit. Do not share state between probes.

7. **Historical context is additive.** CommitRecord data enriches findings but never blocks them. If commit history fetch fails, the review still proceeds without it.

8. **Deduplication key is (file, line, category).** Keep highest severity. If same severity, keep highest confidence.

9. **Three-section prompt structure.** Every LLM agent user prompt must include DIFF, FULL FILE, and CALLERS sections in that order. Truncate: patches at 2000 chars, full files at 6000 chars, caller sources at 400 chars each.

10. **Commit history in prompts.** Every SA-SYN and SA-PERF user prompt must include a "COMMIT HISTORY RISK" section listing: each changed file + its regression_count + last 3 commit messages. This is what makes the agent past-aware.

---

## KNOWN LIMITATIONS (document in README, do not try to fix)

1. Semantic probes run against the installed Qiskit version, not a two-environment diff of before/after the PR patch. They detect whether a fidelity problem EXISTS, not whether this PR INTRODUCED it.
2. SA-FFI does static text analysis on Rust source, not Rust compilation. cargo clippy integration is Phase 2.
3. GitHub Code Search is rate-limited at 30 requests/minute authenticated. MAX_CALLER_SEARCHES=5 mitigates this.
4. Call graph is 2-hop from changed functions. Deep chains (3+ hops) are not followed.
5. No persistent database. Commit history is fetched fresh per PR from GitHub API.

---

## VERIFY BUILD IS COMPLETE WHEN

```bash
# Unit tests pass (no API keys needed)
pytest tests/test_units.py -v
# Expected: all tests pass

# Semantic probes work
python -c "from semantic_checker import run_probe; r=run_probe('bell_transpile'); print(r.fidelity)"
# Expected: float between 0.9 and 1.0

# Context graph builds
python -c "
from context_builder import ContextBuilder
g = ContextBuilder().build('https://github.com/Qiskit/qiskit/pull/12113')
print('functions:', len(g.functions))
print('modules:', len(g.modules))
print('context chars:', g.context_size_chars)
print('regression commits:', g.total_regression_commits)
print('commit history populated:', any(len(m.commit_history)>0 for m in g.modules.values()))
"
# Expected: functions > 0, modules > 0, context_size_chars > 0, commit history populated

# Full review runs end-to-end
python main.py https://github.com/Qiskit/qiskit/pull/12113
# Expected: prints '## QiskitSage Review' followed by findings
```

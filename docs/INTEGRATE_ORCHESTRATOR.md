# Priority 2: Integrate Orchestrator into main.py

## Current Problem

main.py manually executes agents and still references JudgeAgent (line 136), causing NameError.

```python
# Lines 96-141 (OLD CODE - CAUSES ERRORS):
agents_to_run = []
if "all" in args.agents or "syntax" in args.agents:
    agents_to_run.append(("Syntax", SyntaxAgent()))

# ... manual agent execution ...

judge = JudgeAgent()  # NameError HERE - line 136
try:
    result = judge.generate_report(graph, all_findings)  # Old approach
```

## Solution: Replace with Orchestrator

### Step 1: Update Imports (lines 18-25)

```python
# ADD THESE (if not present):
from qiskitsage.orchestrator import Orchestrator
from qiskitsage.renderer import Renderer
```

### Step 2: Replace Agent Execution (lines 95-141)

```python
# NEW CODE (lines 95-141):

# Build list of agent instances
agents_to_run = []
if "all" in args.agents or "syntax" in args.agents:
    agents_to_run.append(SyntaxAgent())
if "all" in args.agents or "performance" in args.agents:
    agents_to_run.append(PerformanceAgent())
if "all" in args.agents or "semantic" in args.agents:
    agents_to_run.append(SemanticAgent())
if "all" in args.agents or "ffi" in args.agents:
    agents_to_run.append(FFIAgent())

if not agents_to_run:
    print("[ERROR] No agents selected to run", file=sys.stderr)
    sys.exit(1)

# Execute via orchestrator
if args.verbose:
    print(f" -> Running {len(agents_to_run)} agents via orchestrator...")

try:
    orchestrator = Orchestrator(agents_to_run)
    result = orchestrator.analyze_pr(graph)
    
    if args.verbose:
        print(f"[OK] Orchestrator completed: {result.total_findings} total findings")
        print(f"     Agents executed: {', '.join(result.agents_run)}")

except Exception as e:
    print(f"[ERROR] Orchestrator failed: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
```

### Step 3: Generate Markdown Output (lines 132-200)

```python
# After orchestrator completes, generate review:

# Add at line ~132:
renderer = Renderer()
result.comment_markdown = renderer.render(result)

# Then display results (lines 143-200):

print("\n" + "="*80)
print("[SUMMARY] QISKITSAGE REVIEW SUMMARY")
print("="*80)
print(f"PR: {result.pr_url}")
print(f"Total findings: {result.total_findings}")
print(f"Agents run: {', '.join(result.agents_run)}")

# Show detailed findings
if result.findings:
    print("\n[DETAILED FINDINGS]")
    print("="*80)
    for finding in result.findings:
        print(f"\n[{finding.severity.value}] {finding.title}")
        print(f"  Location: {finding.file}:{finding.line or 'N/A'}")
        print(f"  Confidence: {finding.confidence:.0%}")
        print(f"  {finding.description}")
        if finding.suggestion:
            print(f"  Suggestion: {finding.suggestion}")

# Show markdown version
print("\n" + "="*80)
print("[MARKDOWN REVIEW]")
print("="*80)
print(result.comment_markdown)
```

## Expected Output After Integration

```
[INFO] Analyzing PR: https://github.com/Qiskit/qiskit/pull/15847
 -> Building context graph (Stage 1: Skeleton)...
[OK] Context graph built in 23s
[OK] 7 changed files

 -> Running 4 agents via orchestrator...
[OK] Orchestrator completed: 5 findings
     Agents executed: SA-SYN, SA-PERF, SA-SEM, SA-FFI

================================================================================
[SUMMARY] QISKITSAGE REVIEW SUMMARY
================================================================================
PR: https://github.com/Qiskit/qiskit/pull/15847
Total findings: 5
Agents run: SA-SYN, SA-PERF, SA-SEM, SA-FFI

[DETAILED FINDINGS]
================================================================================

[HIGH] Potential performance regression in transpiler
  Location: qiskit/transpiler/passes/layout.py:245
  Confidence: 85%
  Description: O(n²) complexity detected in layout algorithm
  Suggestion: Consider using adjacency list instead of nested loops

================================================================================
[MARKDOWN REVIEW]
================================================================================
## QiskitSage AI Review

**PR:** https://github.com/Qiskit/qiskit/pull/15847 (#15847)

⚠️ **High:** 1 | 📊 **Total:** 5 findings

**Agents:** SA-SYN, SA-PERF, SA-SEM, SA-FFI

### Detailed Findings

#### HIGH Severity

**Potential performance regression in transpiler**
...
```

---
*Part of Priority 2 - orchestrator integration*

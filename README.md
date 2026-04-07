# QiskitSage 

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Qiskit](https://img.shields.io/badge/Qiskit-%E2%89%A51.2.0-6929C4.svg)](https://qiskit.org)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20(Local)-orange.svg)](https://ollama.com)

> **Context-aware, multi-agent AI code review system purpose-built for the [Qiskit](https://github.com/Qiskit/qiskit) quantum computing SDK.**

QiskitSage analyzes GitHub Pull Requests and Issues using a pipeline of specialized AI agents, each focusing on a distinct review dimension — syntax compliance, performance regressions, semantic correctness (via quantum fidelity probes), and Rust FFI safety. It uses **Context Builder pipelines** rather than basic chat interfaces, guaranteeing deep repository awareness.

---

## 📑 Table of Contents
1. [Key Features](#-key-features)
2. [Architecture](#-architecture)
3. [Quick Start & Setup](#-quick-start)
4. [Usage & Code Examples](#-usage)
5. [Quantum Fidelity Probes](#-quantum-fidelity-probes)
6. [Results and Timing Benchmarks](#-results-and-benchmark-discussion)
7. [Conclusion & Lessons Learned](#-conclusion-and-lessons-learned)

---

##  Key Features

| Feature | Description |
|---|---|
| **Multi-Agent Architecture** | 4 specialized agents (Syntax · Performance · Semantic · FFI) + Judge + Issue resolver |
| **Context Graph Engine** | 4-stage pipeline builds a full dependency graph from PR diffs, AST parsing, commit history, and caller search |
| **Quantum Fidelity Probes** | Executes real Qiskit circuits to detect transpiler regressions (Bell, QFT, controlled-subgate, unitary synthesis) |
| **Rust FFI Analysis** | Static analysis of `.rs` files for `unwrap()`, `unsafe` blocks, panic risks in `#[pyfunction]` |
| **Local LLM (Ollama)** | Runs entirely offline — no API costs, full privacy, GPU-accelerated inference |
| **GitHub Integration** | Fetches PR data, commit history, caller relationships via PyGithub |

---

##  Quick Start

### Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| **Python** | ≥ 3.9 | Runtime |
| **Ollama** | Latest | Local LLM inference |
| **Git** | Any | Repository operations |
| **GitHub Token** | PAT | API access for PR data |

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/QiskitSage.git
cd QiskitSage
pip install -r requirements.txt
```

### 2. Setup Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:7b
ollama list
```

### 3. Configure Environment

```bash
cp .env.dist .env
# Edit .env and supply GITHUB_TOKEN=ghp_your_personal_access_token
```

### 4. Verify Setup

```bash
python test_ollama.py
```

---

##  Usage

### CLI — Review a Pull Request

```bash
# Basic review
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847"

# Verbose output with agent progress
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847" --verbose

# Run specific agents only
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847" --agents syntax performance
```

### CLI — Analyze an Issue

```bash
python main.py --issue "https://github.com/Qiskit/qiskit/issues/15870" --verbose
```

### Python API

```python
from qiskitsage.context_builder import ContextBuilder
from qiskitsage.orchestrator import Orchestrator
from qiskitsage.agents.syntax_agent import SyntaxAgent
from qiskitsage.agents.performance_agent import PerformanceAgent
from qiskitsage.agents.semantic_agent import SemanticAgent
from qiskitsage.agents.ffi_agent import FFIAgent
from qiskitsage.renderer import Renderer

# Build context graph
builder = ContextBuilder()
graph = builder.build("https://github.com/Qiskit/qiskit/pull/15847")

# Run agents via orchestrator
orchestrator = Orchestrator([SyntaxAgent(), PerformanceAgent(), SemanticAgent(), FFIAgent()])
result = orchestrator.analyze_pr(graph)

# Render markdown
print(Renderer().render(result))
```

---

##  Quantum Fidelity Probes

The **SemanticAgent (SA-SEM)** executes real quantum circuits to detect transpiler regressions before deploying LLMs:

| Probe | Target Issue | What It Detects | Expected Fidelity |
|---|---|---|---|
| `bell_transpile` | General | Transpiler correctness | ≥ 0.9999 |
| `controlled_subgate` | #13118 | Controlled gate miscompilation | ≥ 0.9999 |
| `unitary_synthesis` | #13972 | Synthesis drift (0.707 fidelity error) | ≥ 0.9999 |
| `gate_control` | #15610 | Rust panic in Gate.control() | No panic |
| `qft_round_trip` | General | QFT transpile round-trip errors | ≥ 0.9999 |

---

##  Results and Benchmark Discussion

### Timing Benchmarks

Using **Ollama running `qwen2.5-coder:7b`**:

| Scenario | Total Time (s) | Breakdown |
|---|---|---|
| **Python-only PR (small)** | 35–50 | Context: ~20s, Agents: ~15s |
| **Rust+Python PR (medium)** | 45–70 | Context: ~25s, Agents: ~30s |
| **Large transpiler PR** | 60–90 | Context: ~30s, Subprocesses & Agents: ~45s |
| **Issue analysis** | 10–20 | Pure LLM reasoning code generation |

### Strengths Identified

1. **Multi-Agent Specialization:** Each agent focuses on a specific dimension, restricting prompt context to pure relevance and eliminating LLM "overwhelm". 
2. **Context Depth Engine:** The 4-stage dependency analyzer prevents the standard LLM review "blind-spots" (e.g., hallucinating caller signatures) by extracting source natively before the LLM kicks in.
3. **Data Privacy (Zero Cost):** Due to the local architecture running *fully offline*, source repositories remain secure inside the company intranet without cloud API toll checks.

### Limitations Identified

1. **Probes vs Base Compare:** Currently, the semantic probes run against the *installed* Qiskit binary. Future improvements will compile branches dynamically to do a "Before vs After PR" diff comparison for 100% regression tracing.
2. **Rate Limits:** GitHub code searches used during Stage 3 context builds are capped at 30 req/min. QiskitSage caps searches artificially (`MAX_CALLER_SEARCHES=5`) to safely mitigate this.

---

##  Conclusion and Lessons Learned

QiskitSage is a **production-grade, context-aware, multi-agent AI code review system.** Throughout its design, implementation, and rigorous testing on PRs such as Qiskit (#15847, #12113), the pipeline successfully proved that **domain-specific AI tools (when supported strictly by context-graphs and rule-engine verification) can surpass standard monolithic cloud architectures.**

### Key Takeaways for High-Scale Code Review

- **Context Depth > Prompt Sophistication:** Investing engineering effort into the 4-stage `ContextBuilder` produced dramatically better results than writing massive complex system prompts over loose PR diffs. 
- **Hybrid Static + LLM is Critical:** Pure LLM analysis hallucinated file locations and line numbers in complex Rust code. Using deterministic checks (finding `unwrap()` via strict tree-sitter or regex boundaries) *followed by* LLM reasoning for the "why" produces the highest quality outcomes.
- **Local Models Are Ready:** By structuring the output pipeline to demand 100% JSON compliance and aggressively stripping markdown fences internally, local 7B-parameter models act equivalently to larger expensive cloud counterparts in logic parsing.

---

##  Contributing & License

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new AI endpoints, new Probes, or refining architecture.

This project is licensed under the Apache License 2.0 — see [LICENSE](LICENSE) for details.

### Citation

If you use QiskitSage in your research, please cite:
```bibtex
@software{qiskitsage2026,
  title     = {QiskitSage: AI-Powered Code Review for Qiskit},
  author    = {Manoj},
  year      = {2026},
  url       = {https://github.com/Prahalya05/pr_reviewer_qiskit},
  license   = {Apache-2.0}
}
```

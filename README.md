<![CDATA[# QiskitSage 🤖🔬

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Qiskit](https://img.shields.io/badge/Qiskit-%E2%89%A51.2.0-6929C4.svg)](https://qiskit.org)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20(Local)-orange.svg)](https://ollama.com)

> **Context-aware, multi-agent AI code review system purpose-built for the [Qiskit](https://github.com/Qiskit/qiskit) quantum computing SDK.**

QiskitSage analyzes GitHub Pull Requests and Issues using a pipeline of specialized AI agents, each focusing on a distinct review dimension — syntax compliance, performance regressions, semantic correctness (via quantum fidelity probes), and Rust FFI safety.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **Multi-Agent Architecture** | 4 specialized agents (Syntax · Performance · Semantic · FFI) + Judge + Issue resolver |
| **Context Graph Engine** | 4-stage pipeline builds a full dependency graph from PR diffs, AST parsing, commit history, and caller search |
| **Quantum Fidelity Probes** | Executes real Qiskit circuits to detect transpiler regressions (Bell, QFT, controlled-subgate, unitary synthesis) |
| **Rust FFI Analysis** | Static analysis of `.rs` files for `unwrap()`, `unsafe` blocks, panic risks in `#[pyfunction]` |
| **Local LLM (Ollama)** | Runs entirely offline — no API costs, full privacy, GPU-accelerated inference |
| **GitHub Integration** | Fetches PR data, commit history, caller relationships via PyGithub |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         QiskitSage CLI                          │
│                     main.py --pr <URL>                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Context Builder (4 Stages)                    │
│  ┌───────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Stage 1:  │  │  Stage 2:    │  │ Stage 3: │  │ Stage 4:  │  │
│  │ Skeleton  │→ │  AST Parse   │→ │ Caller   │→ │ Caller    │  │
│  │ from Diff │  │  + History   │  │ Search   │  │ Content   │  │
│  └───────────┘  └──────────────┘  └──────────┘  └───────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ ContextGraph
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Orchestrator (Parallel Exec)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ SA-SYN   │ │ SA-PERF  │ │ SA-SEM   │ │ SA-FFI   │           │
│  │ Syntax   │ │ Perform. │ │ Semantic │ │ FFI Safe │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
│       └─────────────┴────────────┴─────────────┘                │
│                         │ List[Finding]                          │
│  ┌──────────────────────▼───────────────────────────┐           │
│  │  Quality Gate → Dedup → Rank → Cap(MAX_FINDINGS) │           │
│  └──────────────────────┬───────────────────────────┘           │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Renderer → GitHub Markdown                      │
│                  ReviewResult + comment_markdown                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
QiskitSage/
├── main.py                        # CLI entry point
├── examples.py                    # Usage examples (8 scenarios)
├── test_ollama.py                 # LLM connectivity test
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project metadata & build config
├── .env.dist                      # Environment variable template
├── .gitignore                     # Git ignore rules
│
├── qiskitsage/                    # Core package
│   ├── __init__.py                # Package init (exports, version)
│   ├── config.py                  # Configuration & constants
│   ├── models.py                  # Data models (Finding, ReviewResult, enums)
│   ├── context_graph.py           # Graph data structures (pure data, zero logic)
│   ├── context_builder.py         # 4-stage context graph builder (CORE)
│   ├── ast_analyser.py            # Python AST extraction (functions, calls, complexity)
│   ├── rust_analyser.py           # Rust analysis (tree-sitter + regex fallback)
│   ├── github_client.py           # GitHub API (PR data, file content, caller search)
│   ├── orchestrator.py            # Agent coordination, dedup, ranking
│   ├── quality_gate.py            # Confidence filtering + LLM-as-judge
│   ├── renderer.py                # ReviewResult → GitHub markdown
│   │
│   ├── agents/                    # Specialized review agents
│   │   ├── __init__.py
│   │   ├── base_agent.py          # BaseAgent ABC with Ollama LLM client
│   │   ├── syntax_agent.py        # SA-SYN: docstrings, type hints, deprecation
│   │   ├── performance_agent.py   # SA-PERF: complexity, nested loops, Qiskit patterns
│   │   ├── semantic_agent.py      # SA-SEM: quantum fidelity probes
│   │   ├── ffi_agent.py           # SA-FFI: Rust unwrap, unsafe, panic detection
│   │   ├── issue_agent.py         # Issue analysis & code generation
│   │   └── judge_agent.py         # Report generation
│   │
│   └── prompts/                   # LLM prompt templates
│       ├── __init__.py
│       ├── syntax_prompt.py       # SYNTAX_SYSTEM_PROMPT + builder
│       ├── performance_prompt.py  # PERF_SYSTEM_PROMPT + builder
│       ├── ffi_prompt.py          # FFI_SYSTEM_PROMPT + builder
│       ├── judge_prompt.py        # JUDGE_SYSTEM_PROMPT
│       └── semantic_checker.py    # Quantum probe scripts + runner
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── test_units.py              # Unit tests (no API keys required)
│   └── test_integration.py        # E2E tests (requires tokens)
│
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md            # Detailed architecture guide
│   ├── AGENTS.md                  # Agent specifications & prompts
│   ├── CONTEXT_PIPELINE.md        # Context builder pipeline deep-dive
│   ├── API_REFERENCE.md           # Python API reference
│   ├── DEPLOYMENT.md              # Deployment & CI/CD guide
│   ├── CHANGELOG.md               # Version history
│   └── TROUBLESHOOTING.md         # Common issues & solutions
│
├── .github/                       # GitHub configuration
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/                 # CI/CD (future)
│       └── ci.yml
│
├── CONTRIBUTING.md                # Contribution guidelines
├── CODE_OF_CONDUCT.md             # Community standards
├── LICENSE                        # Apache 2.0 license
├── SECURITY.md                    # Security policy
└── CITATION.cff                   # Citation metadata
```

---

## 🚀 Quick Start

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
# Install Ollama (https://ollama.com)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the recommended model
ollama pull qwen2.5-coder:7b

# Verify Ollama is running
ollama list
```

### 3. Configure Environment

```bash
cp .env.dist .env
```

Edit `.env`:
```env
GITHUB_TOKEN=ghp_your_personal_access_token
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5-coder:7b
```

### 4. Verify Setup

```bash
python test_ollama.py
```

---

## 📖 Usage

### CLI — Review a Pull Request

```bash
# Basic review
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847"

# Verbose output with agent progress
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847" --verbose

# Run specific agents only
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847" --agents syntax performance

# Markdown output format
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847" --output markdown
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
orchestrator = Orchestrator([
    SyntaxAgent(),
    PerformanceAgent(),
    SemanticAgent(),
    FFIAgent()
])
result = orchestrator.analyze_pr(graph)

# Render markdown
result.comment_markdown = Renderer().render(result)
print(result.comment_markdown)
```

---

## 🔬 Quantum Fidelity Probes

The **SemanticAgent (SA-SEM)** executes real quantum circuits to detect transpiler regressions:

| Probe | Circuit | Target Issue | What It Detects |
|---|---|---|---|
| `bell_transpile` | Bell state | General | Transpiler correctness after optimization |
| `controlled_subgate` | 3-qubit controlled sub-gate | [#13118](https://github.com/Qiskit/qiskit/issues/13118) | Controlled gate miscompilation |
| `unitary_synthesis` | UnitaryGate + H | [#13972](https://github.com/Qiskit/qiskit/issues/13972) | Synthesis drift (0.707 fidelity) |
| `gate_control` | 4-qubit UnitaryGate.control() | [#15610](https://github.com/Qiskit/qiskit/issues/15610) | Rust panic in Gate.control() |
| `qft_round_trip` | QFT(4) | General | QFT transpile round-trip fidelity |

---

## 📊 Output Format

QiskitSage returns a `ReviewResult` dataclass:

```python
@dataclass
class ReviewResult:
    pr_url: str
    pr_number: int
    findings: List[Finding]              # All detected issues
    total_findings: int
    critical_count: int                  # 🔴 CRITICAL severity count
    high_count: int                      # 🟠 HIGH severity count
    semantic_regression_detected: bool   # Fidelity probe failures
    ffi_risk_detected: bool              # Rust unsafe patterns
    agents_run: List[str]                # e.g., ['SA-SYN', 'SA-PERF']
    execution_time_seconds: float
    comment_markdown: str                # GitHub-ready review comment
```

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — no critical or high issues |
| `1` | High-severity issues found |
| `2` | Critical issues found |

---

## ⚙️ Configuration

All tunable parameters are in `qiskitsage/config.py`:

| Parameter | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | Local LLM model |
| `LLM_MAX_TOKENS` | `4096` | Max response tokens |
| `LLM_TEMPERATURE` | `0.1` | LLM creativity (low = deterministic) |
| `MIN_CONFIDENCE` | `0.70` | Minimum finding confidence threshold |
| `MAX_FINDINGS` | `12` | Maximum findings per review |
| `FIDELITY_THRESHOLD` | `0.9999` | Quantum fidelity pass threshold |
| `MAX_CALLER_SEARCHES` | `5` | GitHub Code Search limit (rate limiting) |
| `MAX_COMMIT_HISTORY` | `10` | Commits per file for historical context |

---

## 🧪 Testing

```bash
# Unit tests (no API keys required)
pytest tests/test_units.py -v

# Integration tests (requires GITHUB_TOKEN + Ollama running)
pytest tests/test_integration.py -v -m integration

# All tests
pytest tests/ -v
```

---

## ⚠️ Known Limitations

1. **Semantic probes** run against the installed Qiskit version, not a diff of before/after the PR
2. **Rust analysis** is static text analysis, not `cargo clippy` integration (planned for Phase 2)
3. **GitHub Code Search** is rate-limited at 30 req/min; `MAX_CALLER_SEARCHES=5` mitigates this
4. **Call graph depth** is 2-hop from changed functions; deeper chains are not followed
5. **No persistent database** — commit history is fetched fresh per PR from GitHub API

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Quick checklist:**
1. Follow Google Docstring style for all Python files
2. Add type hints for all public functions
3. Maintain test coverage for new features
4. Update documentation for architectural changes

---

## 📝 Changelog

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for the full version history.

---

## 📄 License

This project is licensed under the Apache License 2.0 — see [LICENSE](LICENSE) for details.

---

## 📚 Citation

If you use QiskitSage in your research, please cite:

```bibtex
@software{qiskitsage2026,
  title     = {QiskitSage: AI-Powered Code Review for Qiskit},
  author    = {Manoj},
  year      = {2026},
  url       = {https://github.com/YOUR_USERNAME/QiskitSage},
  license   = {Apache-2.0}
}
```

---

## 🙏 Acknowledgements

- [Qiskit](https://qiskit.org) — The open-source quantum computing SDK that QiskitSage reviews
- [Ollama](https://ollama.com) — Local LLM inference engine
- [PyGithub](https://github.com/PyGithub/PyGithub) — GitHub API client
- [tree-sitter](https://tree-sitter.github.io/tree-sitter/) — Incremental parsing for Rust analysis
]]>

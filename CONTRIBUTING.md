<![CDATA[# Contributing to QiskitSage

Thank you for your interest in contributing to QiskitSage! This document provides guidelines and instructions for contributing to the project.

---

## Contents

- [Before You Start](#before-you-start)
- [Development Setup](#development-setup)
- [Project Architecture](#project-architecture)
- [Issues and Pull Requests](#issues-and-pull-requests)
- [Code Style](#code-style)
- [Testing](#testing)
- [Adding a New Agent](#adding-a-new-agent)
- [Adding a New Probe](#adding-a-new-probe)
- [Documentation](#documentation)

---

## Before You Start

1. **Read the [README](README.md)** to understand the project's purpose and architecture.
2. **Check existing [Issues](https://github.com/YOUR_USERNAME/QiskitSage/issues)** to see if someone is already working on what you plan to do.
3. **Open an Issue** before starting major work to discuss your approach with maintainers.

---

## Development Setup

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/QiskitSage.git
cd QiskitSage
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install -e .  # Install in development mode (when pyproject.toml is configured)
```

### 4. Setup Ollama

```bash
ollama pull qwen2.5-coder:7b
```

### 5. Configure Environment

```bash
cp .env.dist .env
# Edit .env with your GITHUB_TOKEN
```

### 6. Verify Setup

```bash
python test_ollama.py          # Test LLM connectivity
pytest tests/test_units.py -v  # Run unit tests
```

---

## Project Architecture

Understanding the architecture is essential for contributing effectively:

```
main.py ──── CLI entry point
  │
  ▼
ContextBuilder ──── Builds the ContextGraph (4 stages)
  │                   ├── Stage 1: Skeleton from diff
  │                   ├── Stage 2: AST parsing + commit history
  │                   ├── Stage 3: Caller search (GitHub Code Search)
  │                   └── Stage 4: Caller content + called_by relationships
  ▼
Orchestrator ──── Runs agents in parallel
  │                ├── SyntaxAgent (SA-SYN)
  │                ├── PerformanceAgent (SA-PERF)
  │                ├── SemanticAgent (SA-SEM) ── runs quantum probes
  │                └── FFIAgent (SA-FFI) ── Rust analysis
  ▼
QualityGate ──── Filters low-confidence findings
  │
  ▼
Renderer ──── Generates GitHub markdown
```

### Key Files

| File | Responsibility | When to Modify |
|---|---|---|
| `context_builder.py` | Builds dependency graph | Adding new context sources |
| `agents/base_agent.py` | Agent ABC + LLM client | Changing LLM provider |
| `agents/*_agent.py` | Individual reviewers | Adding review logic |
| `prompts/*_prompt.py` | LLM system/user prompts | Improving review quality |
| `models.py` | Data models | Adding new finding types |
| `orchestrator.py` | Agent coordination | Changing execution flow |

---

## Issues and Pull Requests

### Opening Issues

- **Bug reports**: Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Feature requests**: Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- **Questions**: Open a discussion or issue with the `question` label

### Pull Request Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines below.

3. **Write tests** for new functionality.

4. **Run the test suite**:
   ```bash
   pytest tests/test_units.py -v
   ```

5. **Update documentation** if your change affects public APIs or architecture.

6. **Submit your PR** with a clear description of changes and motivation.

### PR Checklist

- [ ] Tests pass (`pytest tests/test_units.py -v`)
- [ ] Code follows Google Docstring style
- [ ] Type hints added for all public functions
- [ ] Documentation updated (if applicable)
- [ ] No new dependencies without discussion
- [ ] Commit messages are descriptive

---

## Code Style

### Python Style

- **Docstrings**: Google-style docstrings for all public classes and functions
- **Type hints**: Required for all public function signatures
- **Line length**: 100 characters max
- **Imports**: Group by stdlib → third-party → local, alphabetically within groups
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants

### Example

```python
def analyze_complexity(source: str, file_path: str) -> str:
    """Analyze loop nesting depth to estimate computational complexity.

    Args:
        source: Python source code string.
        file_path: Path to the source file (for error reporting).

    Returns:
        Complexity hint string: '', 'O(n)', 'O(n^2)', or 'O(n^3+)'.

    Raises:
        SyntaxError: If source cannot be parsed as valid Python.
    """
    ...
```

### LLM Prompt Guidelines

When writing or modifying LLM prompts (`prompts/` directory):

1. **Output JSON only** — System prompts must say: "Output ONLY valid JSON."
2. **No prose** — No markdown fences, no explanatory text before/after JSON
3. **Fixed schema** — Use the exact Finding schema defined in `models.py`
4. **Truncation limits** — Patches: 2000 chars, full files: 6000 chars, caller sources: 400 chars each
5. **Three-section structure** — User prompts must include DIFF, FULL FILE, and CALLERS sections

---

## Testing

### Test Structure

```
tests/
├── __init__.py
├── test_units.py           # No API keys required
│   ├── TestASTAnalyser     # Python AST extraction
│   ├── TestRustAnalyser    # Rust parsing
│   ├── TestQualityGate     # Confidence filtering
│   └── TestRenderer        # Markdown generation
└── test_integration.py     # Requires GITHUB_TOKEN + Ollama
    └── @pytest.mark.integration
```

### Running Tests

```bash
# Unit tests only (fast, no external dependencies)
pytest tests/test_units.py -v

# Integration tests (slow, requires tokens)
pytest tests/test_integration.py -v -m integration

# All tests with coverage
pytest tests/ -v --cov=qiskitsage --cov-report=html
```

### Writing Tests

- Place unit tests in `test_units.py` (no API keys, no network calls)
- Place integration tests in `test_integration.py` (mark with `@pytest.mark.integration`)
- Test both happy path and error cases
- Use fixtures for common test data

---

## Adding a New Agent

To add a new review agent:

1. **Create the agent** in `qiskitsage/agents/`:

```python
# qiskitsage/agents/my_agent.py
from .base_agent import BaseAgent
from ..context_graph import ContextGraph
from ..models import Finding

class MyAgent(BaseAgent):
    agent_id = 'SA-MY'

    def review(self, graph: ContextGraph) -> list[Finding]:
        # Your review logic here
        ...
```

2. **Create the prompt** in `qiskitsage/prompts/`:

```python
# qiskitsage/prompts/my_prompt.py
MY_SYSTEM_PROMPT = """You are a specialized code reviewer..."""

def build_my_user_prompt(graph) -> str:
    ...
```

3. **Register in `main.py`** and `orchestrator.py`.

4. **Add tests** in `tests/test_units.py`.

5. **Update documentation** in `docs/AGENTS.md`.

---

## Adding a New Probe

To add a quantum fidelity probe:

1. **Add the probe script** to `qiskitsage/prompts/semantic_checker.py` in the `PROBES` dict
2. **Update `select_probes_for_graph()`** to include your probe for relevant module changes
3. **Add the probe to `PROBE_ISSUE_MAP`** in `semantic_agent.py`
4. **Add a test** in `tests/test_units.py` under `TestSemanticChecker`

---

## Documentation

- Update `README.md` for user-facing changes
- Update `docs/ARCHITECTURE.md` for structural changes
- Update `docs/AGENTS.md` when modifying agent behavior
- Update `docs/CHANGELOG.md` for every PR

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this standard.

---

## Questions?

- Open an [Issue](https://github.com/YOUR_USERNAME/QiskitSage/issues)
- Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

Thank you for contributing to QiskitSage! 🙏
]]>

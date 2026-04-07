# QiskitSage — Local LLM Integration (Ollama)

This project has been updated to support running **locally** using Ollama, removing the dependency on external Anthropic API keys for the LLM agents.

## ✨ Why Local?
- **Privacy**: Code never leaves your machine.
- **Cost**: No per-token API costs.
- **Speed**: With a local GPU, inference is extremely fast and has no rate limits.
- **Flexibility**: Easily swap between different open-source models (Llama, Qwen, Mistral).

## 🚀 Setup Requirements

1. **Install Ollama**: Download from [ollama.com](https://ollama.com/).
2. **Pull the Model**:
   The system is optimized for `qwen2.5-coder:7b`.
   ```bash
   ollama pull qwen2.5-coder:7b
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

Your `.env` file should now look like this:
```env
GITHUB_TOKEN=your_github_permission_token
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5-coder:7b
```
*(No Anthropic API key is required anymore!)*

## 🛠️ Changes Implemented

We have refactored the agent architecture to support local inference:
- **`qiskitsage/config.py`**: Updated to include Ollama connection strings and model names.
- **`qiskitsage/agents/base_agent.py`**: Switched from the Anthropic SDK to the OpenAI SDK (configured for Ollama's local endpoint). Introduced a unified `_llm_call()` helper.
- **Standardized Agents**: `SyntaxAgent`, `PerformanceAgent`, and `FFIAgent` now all consume the local LLM.
- **SemanticAgent**: Remains a hard-coded local probe that executes real Qiskit quantum circuits to verify fidelity.

## 🏃 Running the Project
Ensure Ollama is running (`ollama serve`), then run the CLI using either a Pull Request or Issue URL.

**To analyze a Pull Request (PR):**
```bash
python main.py --pr "https://github.com/Qiskit/qiskit/pull/15847" --verbose
```

**To generate code fixes from an Issue:**
```bash
python main.py --issue "https://github.com/Qiskit/qiskit/issues/15870" --verbose
```

---
*This update was part of the local-inference migration project (March 2026).*

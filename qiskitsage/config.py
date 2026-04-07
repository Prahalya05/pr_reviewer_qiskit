import os
from dotenv import load_dotenv
load_dotenv()

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']

# Ollama local LLM settings
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5-coder:7b')
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.1
MIN_CONFIDENCE = 0.70
MAX_FINDINGS = 12
FIDELITY_THRESHOLD = 0.9999
MAX_CALLER_SEARCHES = 5  # max public functions to search callers for (GitHub rate limit)
MAX_COMMIT_HISTORY = 10  # commits per file for historical context
TRANSPILER_MODULES = ['qiskit/transpiler/', 'qiskit/synthesis/', 'crates/synthesis/']
MODULE_MAP = {
    'qiskit/transpiler': 'transpiler',
    'qiskit/synthesis': 'synthesis',
    'crates/synthesis': 'synthesis_rust',
    'qiskit/qpy': 'qpy',
    'qiskit/quantum_info': 'quantum_info',
    'qiskit/circuit': 'circuit',
}

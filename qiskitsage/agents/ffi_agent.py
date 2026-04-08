import json
from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category
from ..context_graph import ContextGraph
from ..rust_analyser import RustAnalyser
from ..prompts.ffi_prompt import build_ffi_user_prompt, FFI_SYSTEM_PROMPT

import logging
logger = logging.getLogger(__name__)

class FFIAgent(BaseAgent):
    agent_id = 'SA-FFI'

    def review(self, graph: ContextGraph) -> List[Finding]:
        if not graph.has_rust_changes:
            return []

        findings = []
        rust_analyser = RustAnalyser()

        # Static analysis for new unwrap calls and unsafe blocks
        rust_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'rust']

        for filename in rust_files:
            if filename not in graph.added_lines:
                continue

            module = graph.modules[filename]

            # Find all unwrap calls and unsafe blocks in full content
            unwrap_calls = rust_analyser.find_unwrap_calls(module.full_content)
            unsafe_blocks = rust_analyser.find_unsafe_blocks(module.full_content)
            added_lines_set = set(graph.added_lines[filename])

            # Check for new unwrap calls without safety comment
            for line_num, line_content in unwrap_calls:
                if str(line_num) in added_lines_set or str(line_num) + ':' in str(added_lines_set):
                    # Check if this line has a safety comment (previous line check)
                    has_safety = False
                    lines = module.full_content.split('\n')
                    for i in range(line_num-2, max(-1, line_num-5), -1):
                        if i >= 0:
                            prev_line = lines[i].strip()
                            if prev_line.startswith('// SAFETY:') or prev_line.startswith('/// SAFETY:'):
                                has_safety = True
                                break

                    if not has_safety:
                        findings.append(Finding(
                            agent_id=self.agent_id,
                            severity=Severity.CRITICAL,
                            category=Category.FFI_SAFETY,
                            file=filename,
                            line=line_num,
                            title=f"Rust unwrap() without SAFETY justification: {filename}:{line_num}",
                            description=f"Line {line_num} uses .unwrap() or .expect() without a safety comment justifying why panic cannot occur",
                            suggestion="Add a // SAFETY: comment or use .ok_or_else(|| PyValueError::new_err(\"context\"))?",
                            evidence=f"unwrap/expect call on line {line_num}: {line_content}",
                            confidence=0.95,
                            rust_severity='PANIC'
                        ))

            # Check for unsafe blocks without safety comment
            for line_num, has_safety in unsafe_blocks:
                if str(line_num) in added_lines_set and not has_safety:
                    # Find the unsafe line
                    lines = module.full_content.split('\n')
                    unsafe_line = lines[line_num-1]
                    findings.append(Finding(
                        agent_id=self.agent_id,
                        severity=Severity.HIGH,
                        category=Category.FFI_SAFETY,
                        file=filename,
                        line=line_num,
                        title=f"Rust unsafe block without SAFETY justification: {filename}:{line_num}",
                        description=f"Line {line_num} contains unsafe without a // SAFETY: comment justifying soundness invariants",
                        suggestion="Add a // SAFETY: comment explaining what invariants are upheld and why the unsafe is sound",
                        evidence=f"unsafe block on line {line_num}",
                        confidence=0.9,
                        rust_severity='MEMORY'
                    ))

        # LLM-based analysis via Ollama
        user_prompt = build_ffi_user_prompt(graph)
        content = self._llm_call(FFI_SYSTEM_PROMPT, user_prompt)

        # Strip ```json fences
        if content.strip().startswith('```'):
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            else:
                content = content.split('```')[1].split('```')[0].strip()

        try:
            data = json.loads(content.strip())
            for f in data.get('findings', []):
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity(f['severity']),
                    category=Category.FFI_SAFETY,
                    file=f['file'],
                    line=f.get('line'),
                    title=f['title'],
                    description=f['description'],
                    suggestion=f['suggestion'],
                    evidence=f['evidence'],
                    confidence=float(f.get('confidence', 0.5)),
                    rust_severity=f.get('rust_severity')
                ))
            return findings
        except json.JSONDecodeError:
            logger.info(f'[{self.agent_id}] JSON parse error')
            return findings

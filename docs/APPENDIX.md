# Appendix: Full Source Code Listings

> **QiskitSage v0.1.0** — AI-Powered Multi-Agent Code Review System for Qiskit  
> **Date:** April 2026

This appendix contains the full source code listings for the core modules and key agents of the QiskitSage system.

---

## Table of Contents

1. [Core Engine: Context Builder](#1-core-engine-context-builder)
2. [Data Access: GitHub Client](#2-data-access-github-client)
3. [Language Parsing: Python AST Analyser](#3-language-parsing-python-ast-analyser)
4. [Language Parsing: Rust Analyser](#4-language-parsing-rust-analyser)
5. [Agent: Syntax Agent (SA-SYN)](#5-agent-syntax-agent-sa-syn)
6. [Agent: Performance Agent (SA-PERF)](#6-agent-performance-agent-sa-perf)
7. [Agent: FFI Safety Agent (SA-FFI)](#7-agent-ffi-safety-agent-sa-ffi)
8. [Agent: Semantic Agent (SA-SEM)](#8-agent-semantic-agent-sa-sem)
9. [Quantum Probes: Semantic Checker](#9-quantum-probes-semantic-checker)

---

## 1. Core Engine: Context Builder

**File:** `qiskitsage/context_builder.py`

```python
import time
import concurrent.futures
from typing import List, Dict, Set
from collections import defaultdict
from .github_client import GitHubClient
from .ast_analyser import PythonASTAnalyser
from .rust_analyser import RustAnalyser
from .context_graph import ContextGraph, ModuleNode, FunctionNode
from . import config

class ContextBuilder:
    """Builds complete ContextGraph from a GitHub PR URL through 4 sequential stages."""

    def build(self, pr_url: str) -> ContextGraph:
        """Main build method orchestrating all 4 stages."""
        start_time = time.time()
        client = GitHubClient()

        # Stage 1: Skeleton from diff
        stages = self._stage1_skeleton(client, pr_url)
        modules, changed_files, raw_patches, added_lines, has_rust, has_transpiler, has_synthesis, has_qi = stages

        # Stage 2: Full content + AST parsing + commit history
        all_functions, modules, changed_functions = self._stage2_content_ast_history(
            client, modules, changed_files
        )

        # Stage 3: Caller search
        caller_files = self._stage3_caller_search(client, all_functions, changed_files)

        # Stage 4: Fetch caller files + populate called_by
        self._stage4_caller_content(client, all_functions, modules, caller_files)

        # Compute additional fields
        impact_radius = self._compute_impact_radius(all_functions, changed_functions)
        total_regression = sum(m.regression_count for m in modules.values())
        high_risk = [fp for fp, m in modules.items() if m.regression_count >= 3]

        build_time = time.time() - start_time
        context_size = sum(len(m.full_content) for m in modules.values())

        return ContextGraph(
            pr_number=client.pr_data['pr_number'],
            pr_title=client.pr_data['pr_title'],
            pr_body=client.pr_data['pr_body'],
            base_sha=client.pr_data['base_sha'],
            head_sha=client.pr_data['head_sha'],
            modules=modules,
            functions=all_functions,
            changed_files=changed_files,
            changed_functions=changed_functions,
            caller_files=list(caller_files),
            impact_radius=impact_radius,
            has_rust_changes=has_rust,
            has_transpiler_changes=has_transpiler,
            has_synthesis_changes=has_synthesis,
            has_quantum_info_changes=has_qi,
            changed_modules=list({m.module_name for m in modules.values() if m.is_changed}),
            raw_patches=raw_patches,
            added_lines=added_lines,
            total_regression_commits=total_regression,
            high_risk_files=high_risk,
            build_time_seconds=round(build_time, 2),
            context_size_chars=context_size
        )

    def _stage1_skeleton(self, client: GitHubClient, pr_url: str):
        """Stage 1: Build skeleton from PR diff."""
        client.pr_data = client.fetch_pr_data(pr_url)

        modules = {}
        changed_files = []
        raw_patches = {}
        added_lines = {}
        has_rust = False
        has_transpiler = False
        has_synthesis = False
        has_qi = False

        for file_obj in client.pr_data['files']:
            filename = file_obj.filename
            patch = getattr(file_obj, 'patch', '') or ''
            language = 'rust' if filename.endswith('.rs') else 'python'

            module_name = filename.replace('/', '.').replace('.py', '').replace('.rs', '')

            # Language flags
            if language == 'rust':
                has_rust = True
            if 'transpiler/' in filename:
                has_transpiler = True
            if 'synthesis/' in filename or 'crates/synthesis/' in filename:
                has_synthesis = True
            if 'quantum_info/' in filename:
                has_qi = True

            modules[filename] = ModuleNode(
                file_path=filename,
                language=language,
                full_content='',  # Fetched in Stage 2
                module_name=module_name,
                imports=[],
                is_changed=True,
                functions=[],
                test_file=f'test/python/{filename}'.replace('.py', '').replace('.rs', ''),
                commit_history=[],
                regression_count=0
            )

            changed_files.append(filename)
            raw_patches[filename] = patch

            # Extract added lines
            added_lines_list = []
            if patch:
                for line in patch.split('\n'):
                    if line.startswith('+') and not line.startswith('+++'):
                        added_lines_list.append(line[1:].strip())
            added_lines[filename] = added_lines_list

        return modules, changed_files, raw_patches, added_lines, has_rust, has_transpiler, has_synthesis, has_qi

    def _stage2_content_ast_history(self, client: GitHubClient, modules: Dict[str, ModuleNode],
                                    changed_files: List[str]):
        """Stage 2: Fetch full content, parse AST, fetch commit history (parallel)."""
        all_functions = {}
        changed_functions = []

        def process_file(filename: str):
            repo = client.pr_data['repo']
            module = modules[filename]

            # Fetch full content at base_sha
            content = client.fetch_full_file(repo, filename, client.pr_data['base_sha'])
            if content is None:
                return None

            module.full_content = content

            # Parse AST
            if module.language == 'python':
                analyser = PythonASTAnalyser()
                functions = analyser.analyse(content, filename)
            else:  # rust
                analyser = RustAnalyser()
                functions = analyser.analyse(content, filename)

            # All functions from changed files are marked is_changed=True
            for fn in functions:
                fn.is_changed = True
                changed_functions.append(fn.qualified_name)
                all_functions[fn.qualified_name] = fn

            # Update module with function qualified names
            module.functions = [fn.qualified_name for fn in functions]

            # Fetch commit history
            history = client.fetch_commit_history(repo, filename, config.MAX_COMMIT_HISTORY)
            module.commit_history = history
            module.regression_count = sum(1 for c in history if c.is_fix)

            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(process_file, fp) for fp in changed_files]
            concurrent.futures.wait(futures)

        return all_functions, modules, changed_functions

    def _stage3_caller_search(self, client: GitHubClient, all_functions: Dict[str, FunctionNode],
                              changed_files: List[str]) -> Set[str]:
        """Stage 3: Search for callers of public changed functions (GitHub Code Search)."""
        caller_files = set()

        # Limit searches to MAX_CALLER_SEARCHES
        public_changed_fns = []
        count = 0
        for fn in all_functions.values():
            if fn.is_changed and fn.is_public and not fn.name.startswith('_'):
                if count >= config.MAX_CALLER_SEARCHES:
                    break
                public_changed_fns.append(fn)
                count += 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(client.search_callers, client.pr_data['repo'], fn.name, changed_files): fn
                for fn in public_changed_fns
            }

            for future in concurrent.futures.as_completed(futures):
                callers = future.result()
                caller_files.update(callers)

        return caller_files

    def _stage4_caller_content(self, client: GitHubClient, all_functions: Dict[str, FunctionNode],
                               modules: Dict[str, ModuleNode], caller_files: Set[str]):
        """Stage 4: Fetch caller file content and populate called_by relationships."""
        def fetch_caller_file(caller_path: str):
            if caller_path in modules:
                return

            repo = client.pr_data['repo']
            content = client.fetch_full_file(repo, caller_path, client.pr_data['base_sha'])
            if not content:
                return

            language = 'rust' if caller_path.endswith('.rs') else 'python'
            module_name = caller_path.replace('/', '.').replace('.py', '').replace('.rs', '')

            if language == 'python':
                analyser = PythonASTAnalyser()
                functions = analyser.analyse(content, caller_path)
            else:
                analyser = RustAnalyser()
                functions = analyser.analyse(content, caller_path)

            # Update all_functions dict
            for fn in functions:
                if fn.qualified_name not in all_functions:
                    all_functions[fn.qualified_name] = fn

            modules[caller_path] = ModuleNode(
                file_path=caller_path,
                language=language,
                full_content=content,
                module_name=module_name,
                imports=[],
                is_changed=False,
                functions=[fn.qualified_name for fn in functions],
                test_file=f'test/python/{caller_path}'.replace('.py', '').replace('.rs', ''),
                commit_history=[],
                regression_count=0
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_caller_file, cp) for cp in caller_files if cp not in modules]
            concurrent.futures.wait(futures)

        # Populate called_by relationships
        func_by_name = defaultdict(list)
        for fn in all_functions.values():
            base_name = fn.qualified_name.split('.')[-1]
            func_by_name[base_name].append(fn.qualified_name)

        for fn in all_functions.values():
            for called_fn_name in fn.calls:
                # Find matching function by name
                if called_fn_name in all_functions:
                    all_functions[called_fn_name].called_by.append(fn.qualified_name)
                else:
                    for qualified_name in func_by_name.get(called_fn_name, []):
                        all_functions[qualified_name].called_by.append(fn.qualified_name)

    def _compute_impact_radius(self, all_functions: Dict[str, FunctionNode],
                               changed_functions: List[str]) -> Dict[str, str]:
        """Compute impact radius for each changed function."""
        impact = {}
        for fn_qual in changed_functions:
            if fn_qual in all_functions:
                called_by_count = len(all_functions[fn_qual].called_by)
                if called_by_count > 5:
                    impact[fn_qual] = 'HIGH'
                elif called_by_count > 1:
                    impact[fn_qual] = 'MEDIUM'
                else:
                    impact[fn_qual] = 'LOW'
        return impact
```

---

## 2. Data Access: GitHub Client

**File:** `qiskitsage/github_client.py`

```python
from typing import List, Optional, Dict, Any
from github import Github, GithubException
from .context_graph import CommitRecord
from . import config

class GitHubClient:
    def __init__(self):
        self.g = Github(config.GITHUB_TOKEN)

    def fetch_pr_data(self, pr_url: str) -> dict:
        """Parse URL and fetch PR metadata."""
        parts = pr_url.split('/')
        owner = parts[-4]
        repo_name = parts[-3]
        pr_number = int(parts[-1])

        repo = self.g.get_repo(f'{owner}/{repo_name}')
        pr = repo.get_pull(pr_number)
        files = list(pr.get_files())

        return {
            'pr_number': pr_number,
            'pr_title': pr.title,
            'pr_body': pr.body or '',
            'base_sha': pr.base.sha,
            'head_sha': pr.head.sha,
            'files': files,
            'repo': repo
        }

    def fetch_issue_data(self, issue_url: str) -> dict:
        """Parse URL and fetch Issue metadata."""
        parts = issue_url.split('/')
        owner = parts[-4]
        repo_name = parts[-3]
        issue_number = int(parts[-1])

        repo = self.g.get_repo(f'{owner}/{repo_name}')
        issue = repo.get_issue(issue_number)

        return {
            'issue_number': issue_number,
            'issue_title': issue.title,
            'issue_body': issue.body or '',
            'repo': repo
        }

    def fetch_full_file(self, repo, file_path: str, ref: str) -> Optional[str]:
        """Fetch complete file content at specific ref."""
        try:
            content = repo.get_contents(file_path, ref=ref)
            return content.decoded_content.decode('utf-8')
        except GithubException:
            return None  # New file added in PR

    def fetch_commit_history(self, repo, file_path: str, max_commits: int = 10) -> List[CommitRecord]:
        """Fetch commit history for a file."""
        try:
            commits = list(repo.get_commits(path=file_path))[:max_commits]
            records = []

            for commit in commits:
                msg = commit.commit.message.split('\n')[0]
                is_fix = any(kw in msg.lower() for kw in ['fix', 'regression', 'bug', 'revert'])

                records.append(CommitRecord(
                    sha=commit.sha[:8],
                    message=msg,
                    author=commit.commit.author.name,
                    date=commit.commit.author.date.isoformat(),
                    is_fix=is_fix,
                    changed_files=[f.filename for f in commit.files[:10]]
                ))

            return records
        except GithubException:
            return []

    def search_callers(self, repo, function_name: str, exclude_files: List[str]) -> List[str]:
        """Search for functions calling the given function using GitHub code search."""
        try:
            query = f'{function_name}( repo:{repo.full_name} language:Python'
            results = self.g.search_code(query)
            return [item.path for item in results[:10] if item.path not in exclude_files]
        except GithubException:
            return []
```

---

## 3. Language Parsing: Python AST Analyser

**File:** `qiskitsage/ast_analyser.py`

```python
import ast
from typing import List, Dict, Optional
from .context_graph import FunctionNode

class PythonASTAnalyser:
    def analyse(self, source: str, file_path: str) -> List[FunctionNode]:
        """Parse Python source and extract function information."""
        try:
            tree = ast.parse(source, filename=file_path)
        except Exception:
            return []

        visitor = _FunctionVisitor(file_path, source)
        visitor.visit(tree)
        return visitor.functions

class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, source: str):
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.functions = []
        self.class_stack = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_function(node, False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_function(node, True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        # Build qualified name
        if self.class_stack:
            qualified_name = f'{self.class_stack[-1]}.{node.name}'
        else:
            qualified_name = node.name

        # Extract source
        if hasattr(node, 'end_lineno') and node.end_lineno:
            end_line = node.end_lineno
        else:
            end_line = node.lineno

        source_lines = self.source_lines[node.lineno-1:end_line]
        source = '\n'.join(source_lines)

        # Extract docstring
        docstring = ast.get_docstring(node)
        has_docstring = docstring is not None

        # Extract return type
        return_type = ast.unparse(node.returns) if node.returns else None

        # Extract param types
        param_types = {}
        for arg in node.args.args:
            if arg.annotation:
                param_types[arg.arg] = ast.unparse(arg.annotation)
        
        # Handle *args and **kwargs
        if node.args.vararg and node.args.vararg.annotation:
            param_types[node.args.vararg.arg] = ast.unparse(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            param_types[node.args.kwarg.arg] = ast.unparse(node.args.kwarg.annotation)

        # Detect calls
        calls = self._extract_calls(node)

        # Detect complexity hint
        complexity_hint = self._detect_complexity(node)

        # Build FunctionNode
        is_public = not node.name.startswith('_') and not self.class_stack
        fn = FunctionNode(
            name=node.name,
            qualified_name=qualified_name,
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=end_line,
            source=source,
            language='python',
            is_public=is_public,
            is_changed=False,
            calls=list(calls),
            called_by=[],
            complexity_hint=complexity_hint,
            has_docstring=has_docstring,
            docstring=docstring,
            return_type=return_type,
            param_types=param_types
        )

        self.functions.append(fn)
        self.generic_visit(node)

    def _extract_calls(self, node: ast.AST) -> set:
        """Extract qualified names of functions called within this function."""
        calls = set()

        class CallVisitor(ast.NodeVisitor):
            def visit_Call(self, call_node):
                if isinstance(call_node.func, ast.Name):
                    calls.add(call_node.func.id)
                elif isinstance(call_node.func, ast.Attribute):
                    parts = []
                    ctx = call_node.func.value
                    while isinstance(ctx, ast.Attribute):
                        parts.append(ctx.attr)
                        ctx = ctx.value
                    if isinstance(ctx, ast.Name):
                        parts.append(ctx.id)
                    calls.add('.'.join(reversed(parts + [call_node.func.attr])))
                self.generic_visit(call_node)

        CallVisitor().visit(node)
        return calls

    def _detect_complexity(self, node: ast.AST) -> str:
        """Detect nested loops to estimate complexity."""
        max_depth = 0

        class LoopVisitor(ast.NodeVisitor):
            def __init__(self):
                self.depth = 0

            def visit_For(self, loop_node):
                self.depth += 1
                nonlocal max_depth
                max_depth = max(max_depth, self.depth)
                self.generic_visit(loop_node)
                self.depth -= 1

            def visit_While(self, loop_node):
                self.depth += 1
                nonlocal max_depth
                max_depth = max(max_depth, self.depth)
                self.generic_visit(loop_node)
                self.depth -= 1

        LoopVisitor().visit(node)

        if max_depth >= 3:
            return 'O(n^3+)'
        elif max_depth == 2:
            return 'O(n^2)'
        elif max_depth == 1:
            return 'O(n)'
        else:
            return ''
```

---

## 4. Language Parsing: Rust Analyser

**File:** `qiskitsage/rust_analyser.py`

```python
import re
from typing import List, Tuple, Optional
from .context_graph import FunctionNode

class RustAnalyser:
    def analyse(self, source: str, file_path: str) -> List[FunctionNode]:
        """Parse Rust source and extract function information."""
        return self._analyse_with_fallback(source, file_path)

    def _analyse_with_fallback(self, source: str, file_path: str) -> List[FunctionNode]:
        """Try tree-sitter first, fall back to regex if unavailable."""
        try:
            from tree_sitter import Language, Parser
            import tree_sitter_rust as tsrust

            RUST_LANGUAGE = Language(tsrust.language())
            parser = Parser()
            parser.set_language(RUST_LANGUAGE)

            tree = parser.parse(source.encode())
            return self._walk_tree_sitter(tree, source, file_path)
        except ImportError:
            return self._analyse_with_regex(source, file_path)

    def _walk_tree_sitter(self, tree, source: str, file_path: str) -> List[FunctionNode]:
        """Walk tree-sitter AST for function definitions."""
        functions = []
        source_lines = source.split('\n')

        def visit(node):
            if node.type == 'function_item':
                func = self._extract_tree_sitter_function(node, source_lines, file_path)
                if func:
                    functions.append(func)

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return functions

    def _extract_tree_sitter_function(self, node, source_lines, file_path: str) -> Optional[FunctionNode]:
        """Extract function details from tree-sitter node."""
        name_node = next((child for child in node.children if child.type == 'identifier'), None)
        if not name_node:
            return None

        name = self._get_node_text(name_node, source_lines)
        qualified_name = name

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        source = '\n'.join(source_lines[start_line-1:end_line])

        is_public = any(
            self._get_node_text(child, source_lines) == 'pub'
            for child in node.children[:3]
            if child.type == 'visibility_modifier'
        )

        is_async = any(
            self._get_node_text(child, source_lines) == 'async'
            for child in node.children[:3]
            if child.type == 'async'
        )

        complexity_hint = self._detect_rust_complexity(node, source_lines)

        if is_async:
            qualified_name = f'async_{qualified_name}'

        return FunctionNode(
            name=name, qualified_name=qualified_name, file_path=file_path,
            start_line=start_line, end_line=end_line, source=source, language='rust',
            is_public=is_public, is_changed=False, calls=[], called_by=[],
            complexity_hint=complexity_hint, has_docstring=False, docstring=None,
            return_type=None, param_types={}
        )

    def _analyse_with_regex(self, source: str, file_path: str) -> List[FunctionNode]:
        """Fallback regex-based Rust function extraction."""
        functions = []
        source_lines = source.split('\n')

        pattern = r'^(\s*)(?:(pub)\s+)?(?:(async)\s+)?fn\s+(\w+)'

        for i, line in enumerate(source_lines):
            match = re.match(pattern, line)
            if match:
                indent, pub_keyword, async_keyword, name = match.groups()
                start_line = i + 1
                brace_count = 0
                started = False
                end_line = i

                for j in range(i, len(source_lines)):
                    for char in source_lines[j]:
                        if char == '{':
                            brace_count += 1
                            started = True
                        elif char == '}':
                            brace_count -= 1

                    if started and brace_count == 0:
                        end_line = j + 1
                        break

                func_source = '\n'.join(source_lines[i:end_line])
                is_public = pub_keyword is not None
                qualified_name = f'{async_keyword + "_" if async_keyword else ""}{name}'
                complexity = self._detect_regex_complexity(func_source)

                functions.append(FunctionNode(
                    name=name, qualified_name=qualified_name, file_path=file_path,
                    start_line=start_line, end_line=end_line, source=func_source, language='rust',
                    is_public=is_public, is_changed=False, calls=[], called_by=[],
                    complexity_hint=complexity, has_docstring=False, docstring=None,
                    return_type=None, param_types={}
                ))

        return functions

    def _get_node_text(self, node, source_lines) -> str:
        """Extract text from tree-sitter node."""
        start_line, start_col = node.start_point
        end_line, end_col = node.end_point

        if start_line == end_line:
            return source_lines[start_line][start_col:end_col]
        else:
            lines = [source_lines[start_line][start_col:]]
            for i in range(start_line + 1, end_line):
                lines.append(source_lines[i])
            lines.append(source_lines[end_line][:end_col])
            return '\n'.join(lines)

    def _detect_rust_complexity(self, node, source_lines) -> str:
        """Detect nested loops in tree-sitter node."""
        max_depth = 0

        def walk_depth(n, depth=0):
            nonlocal max_depth
            if n.type == 'loop_expression':
                max_depth = max(max_depth, depth + 1)
                for child in n.children:
                    walk_depth(child, depth + 1)
            else:
                for child in n.children:
                    walk_depth(child, depth)

        walk_depth(node)

        if max_depth >= 3: return 'O(n^3+)'
        elif max_depth == 2: return 'O(n^2)'
        elif max_depth == 1: return 'O(n)'
        else: return ''

    def _detect_regex_complexity(self, source: str) -> str:
        """Detect loops in source using regex fallback."""
        max_depth = 0
        current_depth = 0

        for line in source.split('\n'):
            line = line.strip()
            if 'for ' in line or 'while ' in line or line.startswith('loop'):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif line.startswith('}'):
                current_depth -= 1

        if max_depth >= 3: return 'O(n^3+)'
        elif max_depth == 2: return 'O(n^2)'
        elif max_depth == 1: return 'O(n)'
        else: return ''

    def find_unwrap_calls(self, source: str) -> List[Tuple[int, str]]:
        """Find lines containing .unwrap() or .expect()."""
        lines = []
        for i, line in enumerate(source.split('\n'), 1):
            if '.unwrap()' in line or '.expect(' in line:
                lines.append((i, line.strip()))
        return lines

    def find_unsafe_blocks(self, source: str) -> List[Tuple[int, bool]]:
        """Find unsafe blocks and check for preceding safety comments."""
        lines = []
        source_lines = source.split('\n')

        for i, line in enumerate(source_lines):
            if 'unsafe {' in line or 'unsafe{' in line:
                has_safety = False
                for j in range(i-1, max(-1, i-5), -1):
                    prev_line = source_lines[j].strip()
                    if prev_line and not prev_line.startswith('//'):
                        break
                    if prev_line.startswith(('// SAFETY:', '/// SAFETY:')):
                        has_safety = True
                        break
                lines.append((i + 1, has_safety))

        return lines
```

---

## 5. Agent: Syntax Agent (SA-SYN)

**File:** `qiskitsage/agents/syntax_agent.py`

```python
import json
from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category
from ..context_graph import ContextGraph
from ..prompts.syntax_prompt import build_syntax_user_prompt, SYNTAX_SYSTEM_PROMPT

class SyntaxAgent(BaseAgent):
    agent_id = 'SA-SYN'

    def review(self, graph: ContextGraph) -> List[Finding]:
        python_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'python']
        if not python_files:
            return []

        user_prompt = build_syntax_user_prompt(graph)
        content = self._llm_call(SYNTAX_SYSTEM_PROMPT, user_prompt)

        # Strip ```json fences if present
        if content.strip().startswith('```'):
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            else:
                content = content.split('```')[1].split('```')[0].strip()

        try:
            data = json.loads(content.strip())
            findings = []
            for f in data.get('findings', []):
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity(f['severity']),
                    category=Category.SYNTAX,
                    file=f['file'],
                    line=f.get('line'),
                    title=f['title'],
                    description=f['description'],
                    suggestion=f['suggestion'],
                    evidence=f['evidence'],
                    confidence=float(f.get('confidence', 0.5))
                ))
            return findings
        except json.JSONDecodeError:
            print(f'[{self.agent_id}] JSON parse error')
            return []
```

---

## 6. Agent: Performance Agent (SA-PERF)

**File:** `qiskitsage/agents/performance_agent.py`

```python
import json
from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category
from ..context_graph import ContextGraph
from ..prompts.performance_prompt import build_perf_user_prompt, PERF_SYSTEM_PROMPT

class PerformanceAgent(BaseAgent):
    agent_id = 'SA-PERF'

    def review(self, graph: ContextGraph) -> List[Finding]:
        python_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'python']
        if not python_files:
            return []

        findings = []

        # Static analysis: call-graph complexity check
        findings.extend(self._check_cascade_complexity(graph))

        # LLM-based analysis via Ollama
        user_prompt = build_perf_user_prompt(graph)
        content = self._llm_call(PERF_SYSTEM_PROMPT, user_prompt)

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
                    category=Category.PERFORMANCE,
                    file=f['file'],
                    line=f.get('line'),
                    title=f['title'],
                    description=f['description'],
                    suggestion=f['suggestion'],
                    evidence=f['evidence'],
                    confidence=float(f.get('confidence', 0.5))
                ))
            return findings
        except json.JSONDecodeError:
            print(f'[{self.agent_id}] JSON parse error')
            return findings

    def _check_cascade_complexity(self, graph: ContextGraph) -> List[Finding]:
        """Check if O(n^2) function is called from O(n) loop = CRITICAL."""
        findings = []

        for fn_qual in graph.changed_functions:
            if fn_qual not in graph.functions:
                continue

            fn = graph.functions[fn_qual]
            if fn.complexity_hint != 'O(n^2)':
                continue

            for caller_qual in fn.called_by:
                if caller_qual not in graph.functions:
                    continue

                caller = graph.functions[caller_qual]
                if caller.complexity_hint in ('O(n)', 'O(n^2)'):
                    findings.append(Finding(
                        agent_id=self.agent_id,
                        severity=Severity.CRITICAL,
                        category=Category.PERFORMANCE,
                        file=fn.file_path,
                        line=fn.start_line,
                        title=f"Cascade complexity: {fn.qualified_name} is O(n^2) called from O(n) loop",
                        description=f"Function {fn.qualified_name} has O(n^2) complexity and is called from {caller.qualified_name} which has O(n) complexity",
                        suggestion=f"Rewrite {fn.qualified_name} to be O(n) or less, or inline it to avoid nested O(n^3) complexity",
                        evidence=f"Detected complexity: {fn.qualified_name}={fn.complexity_hint}, caller={caller.complexity_hint}",
                        confidence=0.9
                    ))

        return findings
```

---

## 7. Agent: FFI Safety Agent (SA-FFI)

**File:** `qiskitsage/agents/ffi_agent.py`

```python
import json
from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category
from ..context_graph import ContextGraph
from ..rust_analyser import RustAnalyser
from ..prompts.ffi_prompt import build_ffi_user_prompt, FFI_SYSTEM_PROMPT

class FFIAgent(BaseAgent):
    agent_id = 'SA-FFI'

    def review(self, graph: ContextGraph) -> List[Finding]:
        if not graph.has_rust_changes:
            return []

        findings = []
        rust_analyser = RustAnalyser()

        rust_files = [fp for fp in graph.changed_files if graph.modules[fp].language == 'rust']

        for filename in rust_files:
            if filename not in graph.added_lines:
                continue

            module = graph.modules[filename]
            unwrap_calls = rust_analyser.find_unwrap_calls(module.full_content)
            unsafe_blocks = rust_analyser.find_unsafe_blocks(module.full_content)
            added_lines_set = set(graph.added_lines[filename])

            for line_num, line_content in unwrap_calls:
                if str(line_num) in added_lines_set or str(line_num) + ':' in str(added_lines_set):
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

            for line_num, has_safety in unsafe_blocks:
                if str(line_num) in added_lines_set and not has_safety:
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

        user_prompt = build_ffi_user_prompt(graph)
        content = self._llm_call(FFI_SYSTEM_PROMPT, user_prompt)

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
            print(f'[{self.agent_id}] JSON parse error')
            return findings
```

---

## 8. Agent: Semantic Agent (SA-SEM)

**File:** `qiskitsage/agents/semantic_agent.py`

```python
from typing import List
from .base_agent import BaseAgent
from ..models import Finding, Severity, Category
from ..context_graph import ContextGraph
from ..prompts.semantic_checker import select_probes_for_graph, run_probe
from ..config import FIDELITY_THRESHOLD

class SemanticAgent(BaseAgent):
    agent_id = 'SA-SEM'

    PROBE_ISSUE_MAP = {
        'bell_transpile': 'general transpiler correctness',
        'controlled_subgate': 'Issue #13118 — controlled sub-gate miscompilation',
        'unitary_synthesis': 'Issue #13972 — UnitaryGate synthesis drift (0.707)',
        'gate_control': 'Issue #15610 — Gate.control() Rust panic',
        'qft_round_trip': 'QFT round-trip fidelity',
    }

    def review(self, graph: ContextGraph) -> List[Finding]:
        if not (graph.has_transpiler_changes or graph.has_synthesis_changes):
            return []

        probes = select_probes_for_graph(graph)
        findings = []

        for probe_name in probes:
            result = run_probe(probe_name)

            if result.is_regression:
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity.CRITICAL,
                    category=Category.SEMANTIC,
                    file='',
                    line=None,
                    title=f"Semantic regression detected in probe: {probe_name}",
                    description=f"Fidelity {result.fidelity:.4f} below threshold {FIDELITY_THRESHOLD}. {self.PROBE_ISSUE_MAP.get(probe_name, '')}",
                    suggestion="Review transpiler changes for correctness",
                    evidence=f"Probe {probe_name} fidelity dropped to {result.fidelity:.4f}",
                    confidence=0.98,
                    probe_circuit=probe_name,
                    fidelity_before=1.0,
                    fidelity_after=result.fidelity
                ))

            elif result.error:
                findings.append(Finding(
                    agent_id=self.agent_id,
                    severity=Severity.MEDIUM,
                    category=Category.SEMANTIC,
                    file='',
                    line=None,
                    title=f"Semantic probe error: {probe_name}",
                    description=f"Probe {probe_name} failed with error: {result.error}",
                    suggestion="Run probe manually to isolate failure",
                    evidence=f"Error: {result.error}",
                    confidence=0.8,
                    probe_circuit=probe_name,
                    fidelity_before=1.0,
                    fidelity_after=result.fidelity if result.fidelity > 0 else 0.0
                ))

        return findings
```

---

## 9. Quantum Probes: Semantic Checker

**File:** `qiskitsage/prompts/semantic_checker.py`

*(truncated here to show architecture structure, full probes are detailed in the file)*

```python
import sys
import subprocess
import json
from dataclasses import dataclass
from typing import Optional, Dict
from .. import config

PROBES = {
    'bell_transpile': """...""",
    'controlled_subgate': """...""",
    'unitary_synthesis': """...""",
    'gate_control': """...""",
    'qft_round_trip': """..."""
}

@dataclass
class ProbeResult:
    probe_name: str
    function_under_test: str
    fidelity: float
    is_regression: bool
    error: Optional[str] = None
    operator_equiv: Optional[bool] = None

def run_probe(name: str, timeout: int = 45) -> ProbeResult:
    """Execute a probe script and return results."""
    if name not in PROBES:
        raise ValueError(f"Unknown probe: {name}")

    script = PROBES[name]

    try:
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            data = {"probe": name, "fidelity": 0.0, "error": "Invalid JSON output"}

        return ProbeResult(
            probe_name=name,
            function_under_test='transpiler',
            fidelity=data.get('fidelity', 0.0),
            is_regression=data.get('fidelity', 0.0) < config.FIDELITY_THRESHOLD,
            error=data.get('error') if data.get('fidelity', 0.0) < config.FIDELITY_THRESHOLD else None,
            operator_equiv=data.get('operator_equiv')
        )

    except subprocess.TimeoutExpired:
        return ProbeResult(
            probe_name=name,
            function_under_test='transpiler',
            fidelity=0.0,
            is_regression=True,
            error=f"Probe timed out after {timeout}s"
        )

def select_probes_for_graph(graph):
    """Select relevant probes based on changed modules."""
    probes = ['bell_transpile']  # Always included

    if graph.has_transpiler_changes:
        probes.extend(['controlled_subgate', 'qft_round_trip'])

    if graph.has_synthesis_changes:
        probes.extend(['unitary_synthesis', 'gate_control'])

    for fn_qual in graph.changed_functions:
        if 'qs_decomposition' in fn_qual:
            if 'gate_control' not in probes:
                probes.append('gate_control')
            break

    probes = list(dict.fromkeys(probes))

    return probes
```

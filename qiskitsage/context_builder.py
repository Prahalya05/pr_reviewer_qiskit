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
        # For each function call in fn.calls, find the called function and add fn.qualified_name to its called_by
        func_by_name = defaultdict(list)  # name -> list of qualified_names
        for fn in all_functions.values():
            base_name = fn.qualified_name.split('.')[-1]
            func_by_name[base_name].append(fn.qualified_name)

        for fn in all_functions.values():
            for called_fn_name in fn.calls:
                # Find matching function by name (base name match)
                if called_fn_name in all_functions:
                    # Exact match
                    all_functions[called_fn_name].called_by.append(fn.qualified_name)
                else:
                    # Try partial match
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

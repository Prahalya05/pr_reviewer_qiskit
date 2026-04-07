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
        # Find function name
        name_node = next((child for child in node.children if child.type == 'identifier'), None)
        if not name_node:
            return None

        name = self._get_node_text(name_node, source_lines)
        qualified_name = name  # Rust doesn't have nested functions like Python

        # Get source range
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        source = '\n'.join(source_lines[start_line-1:end_line])

        # Detect pub keyword
        is_public = any(
            self._get_node_text(child, source_lines) == 'pub'
            for child in node.children[:3]
            if child.type == 'visibility_modifier'
        )

        # Detect async
        is_async = any(
            self._get_node_text(child, source_lines) == 'async'
            for child in node.children[:3]
            if child.type == 'async'
        )

        complexity_hint = self._detect_rust_complexity(node, source_lines)

        if is_async:
            qualified_name = f'async_{qualified_name}'

        return FunctionNode(
            name=name,
            qualified_name=qualified_name,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            source=source,
            language='rust',
            is_public=is_public,
            is_changed=False,  # Set by ContextBuilder
            calls=[],  # Could be extracted but spec says empty initially
            called_by=[],  # Populated by ContextBuilder
            complexity_hint=complexity_hint,
            has_docstring=False,  # Can check for doc comments if needed
            docstring=None,
            return_type=None,  # Can extract from tree-sitter if needed
            param_types={}  # Can extract if needed
        )

    def _analyse_with_regex(self, source: str, file_path: str) -> List[FunctionNode]:
        """Fallback regex-based Rust function extraction."""
        functions = []
        source_lines = source.split('\n')

        # Pattern: (pub)? (async)? fn function_name ( ... )
        pattern = r'^(\s*)(?:(pub)\s+)?(?:(async)\s+)?fn\s+(\w+)'

        for i, line in enumerate(source_lines):
            match = re.match(pattern, line)
            if match:
                indent, pub_keyword, async_keyword, name = match.groups()

                # Find function body (braces matching)
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

                # Detect complexity based on loop patterns
                complexity = self._detect_regex_complexity(func_source)

                functions.append(FunctionNode(
                    name=name,
                    qualified_name=qualified_name,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    source=func_source,
                    language='rust',
                    is_public=is_public,
                    is_changed=False,
                    calls=[],
                    called_by=[],
                    complexity_hint=complexity,
                    has_docstring=False,
                    docstring=None,
                    return_type=None,
                    param_types={}
                ))

        return functions

    def _get_node_text(self, node, source_lines) -> str:
        """Extract text from tree-sitter node."""
        start_line, start_col = node.start_point
        end_line, end_col = node.end_point

        if start_line == end_line:
            return source_lines[start_line][start_col:end_col]
        else:
            lines = []
            lines.append(source_lines[start_line][start_col:])
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

        if max_depth >= 3:
            return 'O(n^3+)'
        elif max_depth == 2:
            return 'O(n^2)'
        elif max_depth == 1:
            return 'O(n)'
        else:
            return ''

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

        if max_depth >= 3:
            return 'O(n^3+)'
        elif max_depth == 2:
            return 'O(n^2)'
        elif max_depth == 1:
            return 'O(n)'
        else:
            return ''

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
                # Check previous non-empty line for safety comment
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

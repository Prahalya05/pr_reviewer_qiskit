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
            is_changed=False,  # Set by ContextBuilder
            calls=list(calls),
            called_by=[],  # Populated by ContextBuilder
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
                max_depth = max(max_depth, self.depth)
                self.generic_visit(loop_node)
                self.depth -= 1

            def visit_While(self, loop_node):
                self.depth += 1
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

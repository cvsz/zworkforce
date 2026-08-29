import ast
from typing import Any


class RestrictedCodeError(Exception):
    pass


def _check_attribute(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        attr = node.attr
        if attr.startswith("__") and attr.endswith("__"):
            return f"forbidden dunder attribute: {attr}"
        if attr in ("__class__", "__bases__", "__subclasses__", "__mro__", "__base__",
                     "__dict__", "__globals__", "__builtins__", "__import__"):
            return f"forbidden attribute: {attr}"
    return None


def validate_restricted_code(code: str, allowed_calls: set[str] | None = None,
                              allowed_methods: set[str] | None = None) -> None:
    allowed_calls = allowed_calls or set()
    allowed_methods = allowed_methods or set()
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise RestrictedCodeError(f"syntax error: {exc}") from exc

    forbidden_nodes = (
        ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
        ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
        ast.Lambda, ast.Try, ast.TryStar, ast.Raise, ast.Assert,
        ast.Exec, ast.With, ast.AsyncWith,
    )

    for node in ast.walk(tree):
        if isinstance(node, forbidden_nodes):
            raise RestrictedCodeError(f"forbidden statement: {ast.dump(node)}")

        if isinstance(node, ast.Attribute):
            reason = _check_attribute(node)
            if reason:
                raise RestrictedCodeError(reason)

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "__import__", "compile",
                                     "open", "input", "breakpoint", "exit", "quit"):
                    raise RestrictedCodeError(f"forbidden function: {node.func.id}")
                if node.func.id not in allowed_calls:
                    raise RestrictedCodeError(f"call not in allowed list: {node.func.id}")
            elif isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                if attr.startswith("__") and attr.endswith("__"):
                    raise RestrictedCodeError(f"forbidden dunder call: {attr}")
                if attr not in allowed_methods:
                    raise RestrictedCodeError(f"method not in allowed list: {attr}")

        if isinstance(node, ast.Name):
            if node.id in ("eval", "exec", "__import__", "compile",
                           "open", "input", "breakpoint", "exit", "quit"):
                raise RestrictedCodeError(f"forbidden name: {node.id}")

        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Attribute):
                reason = _check_attribute(node.value)
                if reason:
                    raise RestrictedCodeError(reason)

        if isinstance(node, ast.Compare):
            if isinstance(node.left, ast.Attribute):
                reason = _check_attribute(node.left)
                if reason:
                    raise RestrictedCodeError(reason)
            for comparator in node.comparators:
                if isinstance(comparator, ast.Attribute):
                    reason = _check_attribute(comparator)
                    if reason:
                        raise RestrictedCodeError(reason)

from __future__ import annotations

import ast
import math
import statistics
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


SAFE_IMPORTS = MappingProxyType(
    {
        "math": math,
        "statistics": statistics,
    }
)

DANGEROUS_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "builtins",
        "httpx",
        "importlib",
        "os",
        "pathlib",
        "requests",
        "shutil",
        "socket",
        "subprocess",
        "sys",
        "urllib",
        "web3",
    }
)

DANGEROUS_CALLS = frozenset(
    {
        "__import__",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "input",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)

DANGEROUS_ATTRIBUTES = frozenset(
    {
        "approve",
        "call",
        "check_call",
        "check_output",
        "connect",
        "delete",
        "patch",
        "popen",
        "post",
        "put",
        "request",
        "run",
        "send_raw_transaction",
        "send_transaction",
        "socket",
        "system",
        "transfer",
        "unlink",
        "write",
        "writelines",
    }
)

SAFE_BUILTINS = MappingProxyType(
    {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "pow": pow,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
)


class SandboxViolation(ValueError):
    """Raised when submitted Python code violates sandbox policy."""


@dataclass(frozen=True)
class SandboxResult:
    success: bool
    namespace: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class _SandboxValidator(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._check_import(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module is None:
            raise SandboxViolation("Relative imports are not allowed")
        self._check_import(node.module)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        call_name = _call_name(node.func)
        if call_name in DANGEROUS_CALLS:
            raise SandboxViolation(f"Call to {call_name!r} is not allowed")
        if isinstance(node.func, ast.Attribute) and node.func.attr in DANGEROUS_ATTRIBUTES:
            raise SandboxViolation(f"Call to {node.func.attr!r} is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if node.attr.startswith("__"):
            raise SandboxViolation("Dunder attribute access is not allowed")
        self.generic_visit(node)

    @staticmethod
    def _check_import(module_name: str) -> None:
        root = module_name.split(".", maxsplit=1)[0]
        if module_name not in SAFE_IMPORTS:
            raise SandboxViolation(f"Import {module_name!r} is not allowed")
        if root in DANGEROUS_IMPORT_ROOTS:
            raise SandboxViolation(f"Import {module_name!r} is not allowed")


def validate_python_code(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SandboxViolation(f"Invalid Python syntax: {exc.msg}") from exc

    _SandboxValidator().visit(tree)


def run_sandboxed_code(source: str) -> SandboxResult:
    try:
        validate_python_code(source)
        namespace: dict[str, Any] = {
            "__builtins__": {**dict(SAFE_BUILTINS), "__import__": _safe_import},
            **dict(SAFE_IMPORTS),
        }
        exec(compile(source, "<strategy-sandbox>", "exec"), namespace, namespace)
        public_namespace = {
            key: value
            for key, value in namespace.items()
            if not key.startswith("__") and key not in SAFE_IMPORTS
        }
    except Exception as exc:  # noqa: BLE001
        return SandboxResult(success=False, error=str(exc))

    return SandboxResult(success=True, namespace=public_namespace)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _safe_import(
    name: str,
    globals_: object | None = None,
    locals_: object | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> object:
    del globals_, locals_, fromlist
    if level != 0 or name not in SAFE_IMPORTS:
        raise SandboxViolation(f"Import {name!r} is not allowed")
    return SAFE_IMPORTS[name]

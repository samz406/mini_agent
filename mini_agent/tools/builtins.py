"""mini_agent.tools.builtins — Built-in tools registered to GLOBAL_REGISTRY."""

from __future__ import annotations

import ast
import os
import operator
from datetime import datetime
from typing import Optional

from mini_agent.tools.base import GLOBAL_REGISTRY, ToolParameter, tool

# ---------------------------------------------------------------------------
# Persistent memory — lazy-initialised shared instance
# ---------------------------------------------------------------------------

_memory_file: str = ".mini_agent_memory.json"
_persistent_memory: Optional[object] = None


def _get_persistent_memory():
    """Return (or create) the shared PersistentMemory instance."""
    global _persistent_memory
    if _persistent_memory is None:
        from mini_agent.memory.persistent import PersistentMemory
        _persistent_memory = PersistentMemory(filepath=_memory_file)
    return _persistent_memory


def init_memory(filepath: str) -> None:
    """Reinitialise the shared persistent memory with a custom file path."""
    global _persistent_memory, _memory_file
    _memory_file = filepath
    _persistent_memory = None  # will be recreated on next access


# ---------------------------------------------------------------------------
# Safe math evaluator
# ---------------------------------------------------------------------------

def _safe_eval(expression: str) -> float:
    """Evaluate a mathematical expression using AST (no exec/eval)."""
    OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"Disallowed expression: {ast.dump(node)}")

    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


# ---------------------------------------------------------------------------
# Built-in tool definitions
# ---------------------------------------------------------------------------

@tool(
    name="calculate",
    description="Safely evaluate a mathematical expression (+, -, *, /, **, %).",
    parameters=[
        ToolParameter(name="expression", type="string", description="Math expression, e.g. '2 + 3 * 4'")
    ],
    returns="The numeric result as a string.",
)
def calculate(expression: str) -> str:
    """Safe AST-based math evaluator."""
    try:
        result = _safe_eval(expression)
        if result == int(result):
            return str(int(result))
        return str(round(result, 10))
    except Exception as exc:
        return f"Error: {exc}"


@tool(
    name="get_current_time",
    description="Return the current local time.",
    parameters=[],
    returns="Current time as HH:MM:SS string.",
)
def get_current_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


@tool(
    name="get_current_date",
    description="Return the current local date.",
    parameters=[],
    returns="Current date as YYYY-MM-DD string.",
)
def get_current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


@tool(
    name="read_file",
    description="Read the contents of a text file (max 10,000 characters). Only files within the current working directory tree are accessible.",
    parameters=[
        ToolParameter(name="path", type="string", description="Path to the file to read.")
    ],
    returns="File contents as a string.",
)
def read_file(path: str) -> str:
    """Read a file and return up to 10 000 chars of its content.

    The resolved path must remain inside the current working directory to
    prevent directory-traversal attacks.
    """
    try:
        resolved = os.path.realpath(os.path.abspath(path))
        cwd = os.path.realpath(os.getcwd())
        if not resolved.startswith(cwd + os.sep) and resolved != cwd:
            return f"Error: Access denied. Path must be within the current working directory."
        with open(resolved, "r", encoding="utf-8") as fh:
            content = fh.read(10_000)
        return content
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except OSError as exc:
        return f"Error reading file: {exc}"


@tool(
    name="write_file",
    description="Write text content to a file within the current working directory, creating or overwriting it.",
    parameters=[
        ToolParameter(name="path", type="string", description="Destination file path (must be within current working directory)."),
        ToolParameter(name="content", type="string", description="Text content to write."),
    ],
    returns="Confirmation message.",
)
def write_file(path: str, content: str) -> str:
    """Write content to a file.

    The resolved path must remain inside the current working directory to
    prevent directory-traversal attacks.
    """
    try:
        resolved = os.path.realpath(os.path.abspath(path))
        cwd = os.path.realpath(os.getcwd())
        if not resolved.startswith(cwd + os.sep) and resolved != cwd:
            return f"Error: Access denied. Path must be within the current working directory."
        with open(resolved, "w", encoding="utf-8") as fh:
            fh.write(content)
        return f"Successfully wrote {len(content)} characters to {path}."
    except OSError as exc:
        return f"Error writing file: {exc}"


@tool(
    name="list_directory",
    description="List the contents of a directory.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Directory path to list. Defaults to current directory.",
            required=False,
        )
    ],
    returns="Newline-separated list of filenames.",
)
def list_directory(path: str = ".") -> str:
    """List files and subdirectories in *path*."""
    try:
        entries = os.listdir(path)
        if not entries:
            return f"(empty directory: {path})"
        return "\n".join(sorted(entries))
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except OSError as exc:
        return f"Error listing directory: {exc}"


@tool(
    name="search_memory",
    description="Search persistent memory for entries matching a query string.",
    parameters=[
        ToolParameter(name="query", type="string", description="Search term to look for in memory keys and values.")
    ],
    returns="JSON-like representation of matching memory entries.",
)
def search_memory(query: str) -> str:
    """Search the persistent memory store."""
    mem = _get_persistent_memory()
    results = mem.search(query)  # type: ignore[attr-defined]
    if not results:
        return f"No memory entries found matching '{query}'."
    return "\n".join(f"{k}: {v}" for k, v in results.items())


@tool(
    name="save_memory",
    description="Save a key-value pair to persistent memory for future recall.",
    parameters=[
        ToolParameter(name="key", type="string", description="Memory key (identifier)."),
        ToolParameter(name="value", type="string", description="Value to store."),
    ],
    returns="Confirmation message.",
)
def save_memory(key: str, value: str) -> str:
    """Store a value in persistent memory."""
    mem = _get_persistent_memory()
    mem.set(key, value)  # type: ignore[attr-defined]
    return f"Saved memory: {key} = {value}"

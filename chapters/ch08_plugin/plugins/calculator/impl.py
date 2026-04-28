"""Calculator plugin implementation for ch08_plugin demo."""

from __future__ import annotations

import ast
import operator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Reuse the same SimpleTool and Plugin base from plugin_system (resolved at
# runtime via sys.modules after PluginLoader has imported plugin_system).
# For standalone clarity we import from the parent package using a relative
# path that importlib resolves at load-time.
# ---------------------------------------------------------------------------

# NOTE: the PluginLoader injects the Plugin base class and SimpleTool into the
# module's globals before calling exec_module, so we can reference them here
# without a direct import (see plugin_system.py PluginLoader._inject_globals).


def _safe_eval(expression: str) -> float:
    """Evaluate a math expression using AST — no exec/eval."""
    OPS: dict = {
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
        raise ValueError(f"Disallowed node: {type(node).__name__}")

    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


class CalculatorPlugin(Plugin):  # type: ignore[name-defined]  # injected by loader
    """Math calculation plugin."""

    def on_load(self) -> None:
        print(f"  [CalculatorPlugin] loaded (v{self.manifest.version})")

    def on_unload(self) -> None:
        print(f"  [CalculatorPlugin] unloaded")

    def get_tools(self) -> list:
        def calc(expression: str) -> str:
            try:
                result = _safe_eval(expression)
                return str(int(result) if result == int(result) else round(result, 10))
            except Exception as exc:
                return f"Error: {exc}"

        return [SimpleTool("calc", "Safely evaluate a math expression.", calc)]  # type: ignore[name-defined]

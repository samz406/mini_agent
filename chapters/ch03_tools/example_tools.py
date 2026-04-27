"""Chapter 3: Example tools using the tool decorator system."""

from __future__ import annotations

import ast
import json
import operator
from datetime import datetime

from tools import ToolParameter, ToolRegistry, tool

# Use a dedicated registry for this demo
demo_registry = ToolRegistry()


def _safe_eval(expression: str) -> float:
    """Evaluate a math expression safely using AST parsing.

    Only allows: numbers, +, -, *, /, **, %, unary minus.
    """
    ALLOWED_OPS = {
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
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
            return ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
            return ALLOWED_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"Disallowed expression node: {type(node).__name__}")

    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


@tool(
    name="calculator",
    description="Safely evaluate a mathematical expression and return the result.",
    parameters=[
        ToolParameter(
            name="expression",
            type="string",
            description="A math expression, e.g. '2 + 3 * 4' or '(10 / 2) ** 2'",
        )
    ],
    registry=demo_registry,
)
def calculator(expression: str) -> str:
    """Safe math evaluator — supports +, -, *, /, **, %."""
    try:
        result = _safe_eval(expression)
        if result == int(result):
            return str(int(result))
        return str(round(result, 10))
    except Exception as exc:
        return f"Error: {exc}"


@tool(
    name="get_time",
    description="Return the current local date and time.",
    parameters=[],
    registry=demo_registry,
)
def get_time() -> str:
    """Return current time as a human-readable string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool(
    name="echo",
    description="Echo a message back unchanged. Useful for testing.",
    parameters=[
        ToolParameter(
            name="message",
            type="string",
            description="The message to echo back",
        )
    ],
    registry=demo_registry,
)
def echo(message: str) -> str:
    """Return the message unchanged."""
    return message


if __name__ == "__main__":
    print("=== Registered Tools ===")
    for t in demo_registry.list_tools():
        print(f"  • {t.name}: {t.description}")

    print("\n=== OpenAI Function Calling Schemas ===")
    schemas = demo_registry.to_openai_schema()
    print(json.dumps(schemas, indent=2))

    print("\n=== Tool Executions ===")
    calc = demo_registry.get("calculator")
    if calc:
        print(f"  calculator('2 + 3 * 4') = {calc(expression='2 + 3 * 4')}")
        print(f"  calculator('(10 / 2) ** 2') = {calc(expression='(10 / 2) ** 2')}")

    timer = demo_registry.get("get_time")
    if timer:
        print(f"  get_time() = {timer()}")

    echoer = demo_registry.get("echo")
    if echoer:
        print(f"  echo('hello world') = {echoer(message='hello world')}")

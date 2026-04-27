# Chapter 3: Tool System

## What You'll Learn

This chapter builds a complete, extensible tool system. Tools are what transform an LLM from a text predictor into an agent that can *do things*.

## Core Concepts

### 1. Tool Abstraction
A `Tool` is more than just a function — it carries metadata: name, description, parameter schemas. This metadata is sent to the LLM so it knows what tools exist and how to call them.

### 2. Decorator Pattern
The `@tool()` decorator lets you define tools declaratively:

```python
@tool(
    name="calculator",
    description="Evaluate a math expression",
    parameters=[ToolParameter(name="expression", type="string", description="Math expression")]
)
def calculator(expression: str) -> str:
    ...
```

No manual registration needed — the decorator handles it.

### 3. Tool Registry
`ToolRegistry` is a central store for all tools. It supports:
- `register(tool)` — add a tool
- `get(name)` — retrieve by name
- `list_tools()` — enumerate all tools
- `to_openai_schema()` — export all tools in OpenAI function calling format

### 4. JSON Schema for OpenAI Function Calling
OpenAI's function calling API expects tools in a specific JSON format:

```json
{
  "type": "function",
  "function": {
    "name": "calculator",
    "description": "Evaluate a math expression",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {"type": "string", "description": "Math expression"}
      },
      "required": ["expression"]
    }
  }
}
```

`tool.to_json_schema()` generates this automatically from your `ToolParameter` definitions.

## How to Run

```bash
cd chapters/ch03_tools
python example_tools.py
```

You'll see all registered tools listed with their JSON schemas, then each tool executed with sample inputs.

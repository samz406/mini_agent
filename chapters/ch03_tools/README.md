# 第三章：工具系统

## 你将学到什么

本章构建一个完整的、可扩展的工具系统。工具（Tool）是让 LLM 从"文字预测机器"变成"能做事的 Agent"的关键组件。

> 📖 学完本章后，可以阅读 `extended_reading.md`，了解 nanobot 的类继承工具体系、MCP 协议标准化工具接入等设计。

## 核心概念

### 1. 工具抽象

一个工具不只是一个函数——它还携带**元数据**：名称、描述、参数定义。这些元数据会发送给 LLM，让 LLM 知道有哪些工具可以用、每个工具怎么调用。

```python
@dataclass
class Tool:
    name: str          # 工具名称（LLM 用这个名字调用工具）
    description: str   # 工具说明（帮助 LLM 决定什么时候用这个工具）
    parameters: list   # 参数定义（告诉 LLM 需要提供哪些参数）
    func: callable     # 实际执行函数
```

### 2. 装饰器模式（Decorator Pattern）

`@tool()` 装饰器让你用声明式的方式定义工具，无需手动注册：

```python
@tool(
    name="calculator",
    description="安全地计算数学表达式，返回结果",
    parameters=[
        ToolParameter(name="expression", type="string", description="数学表达式，如 '2 + 3 * 4'")
    ]
)
def calculator(expression: str) -> str:
    """安全的数学计算器"""
    result = _safe_eval(expression)
    return str(result)
```

装饰器在你定义函数的同时，自动完成工具注册。**通俗理解**：就像餐厅菜单——你不用每次点菜时都描述菜品，菜单（装饰器）已经把名称、描述、价格（参数）都整理好了。

### 3. 工具注册表（Tool Registry）

`ToolRegistry` 是所有工具的中央存储库，支持以下操作：

```python
registry = ToolRegistry()
registry.register(tool)          # 注册一个工具
registry.get("calculator")       # 按名称查找工具
registry.list_tools()            # 列出所有工具
registry.to_openai_schema()      # 导出 OpenAI Function Calling 格式
```

有了注册表，Agent 可以动态发现所有可用工具，而不需要硬编码工具列表。

### 4. JSON Schema（OpenAI Function Calling 格式）

OpenAI 的 Function Calling API 要求工具以特定的 JSON 格式描述：

```json
{
  "type": "function",
  "function": {
    "name": "calculator",
    "description": "安全地计算数学表达式",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "数学表达式，如 '2 + 3 * 4'"
        }
      },
      "required": ["expression"]
    }
  }
}
```

`tool.to_json_schema()` 方法根据你的 `ToolParameter` 定义自动生成这个格式。

## 安全计算器的实现

本章的 `calculator` 工具使用了 **AST（抽象语法树）解析**，而不是危险的 `eval()`：

```python
def _safe_eval(expression: str) -> float:
    """只允许数字和基本运算，拒绝任何危险代码"""
    # 1. 把表达式解析成语法树
    tree = ast.parse(expression, mode="eval")
    # 2. 只允许特定的节点类型（数字、加减乘除）
    # 3. 拒绝函数调用、变量访问等危险操作
```

这样用户无法通过 `calculator("__import__('os').system('rm -rf /')")` 执行危险命令。

## 如何运行

```bash
cd chapters/ch03_tools
python example_tools.py
```

你将看到：
1. 所有注册工具的列表（名称 + 描述）
2. 每个工具的完整 JSON Schema
3. 各工具的实际执行结果（计算、获取时间、回声）

# 第六章：提示词工程与 Builder 模式

## 你将学到什么

提示词（Prompt）是代码——本章就按这个思路来设计：结构化、可组合、可测试。你将构建三个互补的工具，用来生成高质量的提示词。

> 📖 学完本章后，可以阅读 `extended_reading.md`，其中包含：
> - **提示词组装详解**：逐层拆解 Claude Code、Nanobot、Hermes-Agent 三大生产级 Agent 的实际组装代码，包括多层覆盖系统、Jinja2 模板渲染、SOUL.md 人格机制，以及相同点与不同点的对比总结。
> - **进阶设计模式**：代码构建器 vs 模板引擎、SOUL.md 人格文件、动态 Few-Shot 选择、多代理提示词隔离、提示词版本管理。

## 三个工具

### 1. `SystemPromptBuilder` — 流式 Builder 模式

复杂的系统提示词用原始字符串很难维护。Builder 把提示词拆成有意义的**命名区块**，并提供**链式调用 API**：

```python
prompt = (
    SystemPromptBuilder()
    .add_role("你是一个专业的 Python 编程助手。")
    .add_tools_section(tool_schemas)
    .add_memory_section({"user_name": "Alice", "preferred_lang": "Python"})
    .add_rules([
        "解释代码前先说明你的思路。",
        "优先写可读性好的代码，而不是炫技的代码。",
        "提醒用户注意边界情况。"
    ])
    .build()
)
```

每个 `add_*` 方法返回 `self`，所以可以连续调用。`build()` 把所有区块拼装成格式规范的字符串。

**为什么要用 Builder？**

不用 Builder 时：
```python
# 一团字符串，改任何一部分都容易出错
system_prompt = f"你是助手。工具：{tools}。规则：{rules}。记忆：{memory}。"
```

用 Builder 后：
- **可维护**：每个区块独立，修改一处不影响其他部分
- **可测试**：每个区块可以单独断言
- **可复用**：不同 Agent 可以共享同一个 Builder 的部分配置

### 2. `PromptTemplate` — 变量替换

用占位符 `{variable}` 创建可复用的提示词模板：

```python
template = PromptTemplate("你好 {name}！你问的是关于 {topic} 的问题。以下是我的回答：\n{answer}")

result = template.render(
    name="Bob",
    topic="递归",
    answer="递归是函数调用自身的编程技术。"
)
# → "你好 Bob！你问的是关于递归的问题。以下是我的回答：\n递归是函数调用自身的编程技术。"

template.get_variables()  # → ["name", "topic", "answer"]
```

### 3. `FewShotBuilder` — 少样本示例构造

**少样本提示（Few-Shot Prompting）**：在提示词中加入几个输入→输出的示例，帮助 LLM 理解你期望的输出格式和风格。这是提升输出质量最有效的技巧之一。

```python
examples = (
    FewShotBuilder()
    .add_example(input="2+2 等于多少？", output="4")
    .add_example(input="法国的首都是哪里？", output="巴黎")
    .add_example(input="把 'hello' 翻译成中文。", output="你好")
    .build(prefix="以下是问答示例，请按同样的格式回答：")
)
```

## 结构化提示词的价值

| 问题 | 解决方案 |
|------|---------|
| 提示词越来越长，难以维护 | Builder 按区块组织 |
| 同样的提示词用在多个场景 | PromptTemplate 参数化 |
| LLM 输出格式不一致 | FewShot 示例引导 |
| 不知道提示词哪段出了问题 | 分区块独立调试 |

## 如何运行

```bash
cd chapters/ch06_prompt
python prompt_builder.py
```

你将看到：
1. `SystemPromptBuilder` 生成的完整系统提示词（含角色、工具、记忆、规则各区块）
2. `PromptTemplate` 的变量列表和渲染结果
3. `FewShotBuilder` 构建的少样本示例文本

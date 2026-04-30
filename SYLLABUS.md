# Mini Agent 教学大纲：从零构建生产级 AI Agent

## 项目简介

本项目是一个系统化的 AI Agent 开发教程，从最基础的 LLM 客户端封装，到完整的生产级 Agent 系统，循序渐进地讲解每一个核心组件的设计思路与实现方法。

## 课程目标

完成本课程后，你将能够：
- 独立设计和实现一个生产级 AI Agent 框架
- 理解 Agent 各核心组件之间的关系
- 掌握 Python 最佳实践：ABC、Pydantic v2、类型提示、装饰器
- 具备扩展和定制 Agent 能力的工程基础

---

## 第一章：LLM 客户端封装

**代码文件：** `chapters/ch01_llm_client/llm_client.py`

### 前置背景阅读
阅读 `chapters/ch01_llm_client/llm_background.md`，了解人工智能发展历史及大语言模型的演进过程，建立整体认知框架。

### 学习目标
- 理解如何对 LLM API 进行抽象封装
- 掌握 Python ABC（抽象基类）模式
- 学习指数退避重试策略
- 了解流式输出（Streaming）的实现方式

### 核心概念
| 概念 | 说明 |
|------|------|
| 抽象基类（ABC） | 定义接口规范，使不同 LLM 后端可互换 |
| 重试机制 | 处理 RateLimitError，指数退避防止压垮服务 |
| 流式输出 | `Iterator[str]` 逐块返回 token，提升用户体验 |
| `Message` 数据类 | 统一的消息格式，解耦上层逻辑与 API 细节 |

### 运行方式
```bash
cd chapters/ch01_llm_client
OPENAI_API_KEY=sk-xxx python llm_client.py
```

---

## 第二章：Agent 循环（ReAct 模式）

**代码文件：** `chapters/ch02_agent_loop/agent_loop.py`

### 学习目标
- 理解 ReAct（Reason + Act）推理框架
- 掌握 Agent 主循环的设计
- 学习如何解析 LLM 输出中的工具调用
- 了解循环终止条件的设计

### 核心概念
| 概念 | 说明 |
|------|------|
| ReAct 框架 | Reasoning（思考）→ Action（行动）→ Observation（观察）的循环 |
| 工具调用解析 | 从 LLM 文本中提取结构化的工具调用指令 |
| 最大迭代保护 | 防止 Agent 进入无限循环，是生产环境的必要保障 |
| 消息历史管理 | 每次迭代将观察结果追加到对话历史 |

### 运行方式
```bash
cd chapters/ch02_agent_loop
python agent_loop.py
```

---

## 第三章：工具系统（Tools）

**代码文件：** `chapters/ch03_tools/tools.py`, `chapters/ch03_tools/example_tools.py`

### 学习目标
- 设计可扩展的工具注册系统
- 掌握 Python 装饰器工厂模式
- 学习如何生成 OpenAI Function Calling 的 JSON Schema
- 理解工具参数的类型和约束描述

### 核心概念
| 概念 | 说明 |
|------|------|
| 工具注册表（Registry） | 集中管理所有可用工具，支持动态查找 |
| 装饰器工厂 | `@tool(name, description, parameters)` 声明式定义工具 |
| JSON Schema | OpenAI function calling 要求的工具描述格式 |
| Pydantic v2 模型 | 用于参数验证和序列化的数据模型 |

### 运行方式
```bash
cd chapters/ch03_tools
python example_tools.py
```

---

## 第四章：记忆系统（Memory）

**代码文件：** `chapters/ch04_memory/memory.py`

### 学习目标
- 区分对话记忆与持久化记忆的应用场景
- 掌握滑动窗口（deque）控制对话长度
- 学习 JSON 文件持久化方案
- 设计统一的 MemoryManager 门面

### 核心概念
| 概念 | 说明 |
|------|------|
| 对话记忆 | 存储当前会话的消息历史，有最大长度限制 |
| 持久化记忆 | 跨会话的键值存储，写入 JSON 文件 |
| `collections.deque` | 双端队列，`maxlen` 参数实现自动滑动窗口 |
| 记忆检索 | 基于字符串匹配的简单语义查找 |

### 运行方式
```bash
cd chapters/ch04_memory
python memory.py
```

---

## 第五章：上下文窗口管理（Context）

**代码文件：** `chapters/ch05_context/context_manager.py`

### 学习目标
- 理解 LLM token 限制的工程影响
- 掌握 tiktoken 进行精确 token 计数
- 学习滑动窗口截断策略
- 了解摘要策略的设计思路

### 核心概念
| 概念 | 说明 |
|------|------|
| Token 计数 | 使用 tiktoken 精确计算，避免超出上下文窗口 |
| 滑动窗口策略 | 保留系统提示词，丢弃最早的对话消息 |
| 摘要策略 | 将旧消息压缩为摘要，保留关键信息 |
| 优雅降级 | tiktoken 不可用时降级为字符数估算 |

### 运行方式
```bash
cd chapters/ch05_context
python context_manager.py
```

---

## 第六章：提示词构建（Prompt Engineering）

**代码文件：** `chapters/ch06_prompt/prompt_builder.py`

### 学习目标
- 掌握 Builder 模式构建复杂提示词
- 学习模板变量替换系统
- 理解 Few-Shot 提示词的构建技巧
- 建立可维护的提示词工程实践

### 核心概念
| 概念 | 说明 |
|------|------|
| Builder 模式 | 链式调用逐步构建复杂提示词，提高可读性 |
| 提示词模板 | `{variable}` 占位符实现参数化提示词 |
| Few-Shot 示例 | 提供输入输出样例，引导模型输出格式 |
| 分节提示词 | 角色、工具、记忆、规则分区管理 |

### 运行方式
```bash
cd chapters/ch06_prompt
python prompt_builder.py
```

---

## 第七章：技能系统（Skills）

**代码文件：** `chapters/ch07_skills/skill_system.py`

### 学习目标
- 设计插件化的技能扩展系统
- 掌握类装饰器实现自动注册
- 学习如何组合多个技能形成 Agent 能力
- 理解技能与工具的层次关系

### 核心概念
| 概念 | 说明 |
|------|------|
| 技能（Skill） | 工具 + 系统提示补充的能力单元，高于工具的抽象 |
| 插件注册 | `@skill` 类装饰器自动将技能注册到全局注册表 |
| 技能组合 | `SkillManager` 按需加载技能并聚合工具和提示词 |
| 单例注册表 | `SkillRegistry` 全局唯一，集中管理所有技能 |

### 运行方式
```bash
cd chapters/ch07_skills
python skill_system.py
```

---

## 第八章：插件机制（Plugin Mechanism）

**代码文件：** `chapters/ch08_plugin/plugin_system.py`

### 学习目标
- 理解基于文件系统的插件发现与动态加载
- 掌握 `importlib.util` 动态导入 Python 模块
- 学习插件清单（JSON）与插件生命周期钩子（on_load / on_unload）
- 区分静态技能系统（ch07）与动态插件系统的应用场景

### 核心概念
| 概念 | 说明 |
|------|------|
| 插件清单（PluginManifest） | `plugin.json` 描述插件元数据，含 `enabled` 开关 |
| 目录扫描（Discovery） | `PluginLoader` 运行时扫描文件系统，无需预知插件名 |
| 动态加载（importlib） | `spec_from_file_location` + `exec_module` 独立命名空间加载 |
| 生命周期钩子 | `on_load` 初始化资源，`on_unload` 释放资源 |
| 热重载（Reload） | 不重启进程，卸载并重新从磁盘读取插件 |

### 运行方式
```bash
cd chapters/ch08_plugin
python plugin_system.py
```

---

## 第九章：MCP（Model Context Protocol）

**代码文件：** `chapters/ch09_mcp/mcp_demo.py`

### 学习目标
- 理解 MCP 协议解决的核心问题（M×N 工具集成爆炸）
- 掌握 MCP Server 的编写方式（工具定义、工具调用处理器）
- 学会用 MCP Client 动态发现并调用工具
- 了解如何将 MCP 工具集成到 mini_agent 的工具注册表

### 核心概念
| 概念 | 说明 |
|------|------|
| MCP Server | 独立进程，通过 stdio/HTTP 对外暴露工具 |
| MCP Client | 嵌入 Agent，负责连接 Server、获取工具列表、调用工具 |
| Tools | MCP 三大能力之一，Agent 调用后得到结果 |
| MCPToolLoader | mini_agent 适配器，将 MCP 工具注册到 ToolRegistry |

### 运行方式
```bash
cd chapters/ch09_mcp
pip install mcp>=1.23.0
python mcp_demo.py
```

---

## 第十章：学习循环（Learning Loop）

**代码文件：** `chapters/ch10_learning_loop/learning_loop.py`

### 学习目标
- 理解 Agent 学习循环的设计思路：从经验中自动提炼可复用技能
- 掌握经验（Experience）→ 合成（Synthesis）→ 存储（Store）→ 检索（Search）的完整闭环
- 学习基于关键词的轻量级技能检索（无需向量数据库）
- 理解技能版本化改进的设计原则
- 了解 hermes-agent 的自改进技能系统

### 核心概念
| 概念 | 说明 |
|------|------|
| 经验（Experience） | 一次成功任务完成的完整记录（任务、步骤、结果、时间戳） |
| 技能（Skill） | 从经验中提炼的可复用过程性知识，带有版本和使用次数 |
| SkillStore | JSON 持久化技能库，跨会话保留所有学到的技能 |
| SkillSynthesizer | 将经验转化为技能（或改进现有技能）的合成器 |
| 版本化改进 | 每次遇到相似任务时，技能版本号递增、步骤持续完善 |

### 运行方式
```bash
cd chapters/ch10_learning_loop
python learning_loop.py
```

---

## 第十一章：多智能体协作（Multi-Agent）

**代码文件：** `chapters/ch11_multi_agent/multi_agent.py`

### 学习目标
- 理解单 Agent 架构的局限性（上下文窗口、无并行、难以专业化）
- 掌握 Orchestrator-SubAgent 模式：分解→并行委托→汇总
- 学习使用 `ThreadPoolExecutor` 并行执行多个 SubAgent
- 理解错误隔离：单个 SubAgent 失败不影响整体结果
- 了解 hermes-agent 的进程级子智能体隔离与 RPC 工具调用

### 核心概念
| 概念 | 说明 |
|------|------|
| OrchestratorAgent | 接收复杂任务，分解为子任务，协调所有 SubAgent，汇总结果 |
| SubAgent | 独立线程中运行的专项 Agent，拥有独立上下文和最小权限工具集 |
| TaskSpec | 子任务的结构化描述：工作内容、工具权限、超时保护 |
| Fan-out / Fan-in | 任务扇出到 N 个并行 SubAgent，N 个结果扇入合并为统一回答 |
| 错误隔离 | 任意 SubAgent 超时或崩溃，编排器照常聚合其他 SubAgent 的结果 |

### 运行方式
```bash
cd chapters/ch11_multi_agent
python multi_agent.py
```

---

## 第十二章：多层次记忆（Multi-Level Memory）

**代码文件：** `chapters/ch12_multi_level_memory/multi_level_memory.py`

### 学习目标
- 理解单一记忆结构无法满足长期 Agent 需求的根本原因
- 掌握四层记忆架构：工作记忆 → 情景记忆 → 语义记忆 → 程序性记忆
- 学会在会话结束时将工作记忆压缩为情景摘要（Episode）
- 实现基于类别和置信度的语义记忆（用户画像 + 偏好）
- 理解如何在新会话开始时重建历史上下文并注入 system prompt
- 了解 hermes-agent 的 Honcho 用户建模与 FTS5 会话检索

### 核心概念
| 概念 | 说明 |
|------|------|
| 工作记忆（Working Memory） | 当前对话上下文，deque 滑动窗口，会话结束后清空 |
| 情景记忆（Episodic Memory） | 历史会话的自然语言摘要，可按关键词检索 |
| 语义记忆（Semantic Memory） | 关于用户和世界的事实性知识，按类别/键名查询，带置信度 |
| 程序性记忆（Procedural Memory） | 如何完成任务的技能（见第十章），是持久性最强的一层 |
| 上下文重建（Context Reconstruction） | 新会话开始时从持久化层拉取相关历史，注入 system prompt |

### 运行方式
```bash
cd chapters/ch12_multi_level_memory
python multi_level_memory.py
```

---

## 综合项目：Mini Agent

**代码目录：** `mini_agent/`

完整的生产级 Agent 实现，整合上述所有章节的技术：

```
mini_agent/
├── config.py          # 统一配置，支持环境变量
├── main.py            # CLI 入口，rich 美化界面
├── core/
│   ├── llm.py         # LLM 客户端（第一章升级版）
│   ├── loop.py        # Agent 循环（第二章升级版）
│   ├── context.py     # 上下文管理（第五章）
│   └── prompt.py      # 提示词构建（第六章）
├── tools/
│   ├── base.py        # 工具系统（第三章升级版）
│   └── builtins.py    # 内置工具集
├── memory/
│   ├── conversation.py # 对话记忆（第四章）
│   └── persistent.py   # 持久化记忆（第四章）
└── skills/
    └── base.py         # 技能系统（第七章）
```

### 快速启动
```bash
pip install -e .
export OPENAI_API_KEY=sk-xxx
mini-agent
```

---

## 学习路径建议

```
第一章 → 第二章 → 第三章 → 第四章
                              ↓
第十二章 ← 第十一章 ← 第十章 ← 第九章 ← 第八章 ← 第七章 ← 第六章 ← 第五章
    ↓
综合项目
```

建议按顺序学习，每章先阅读 README.md，再研读代码，最后运行示例验证理解。

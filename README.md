# Mini Agent 🤖

> **从零构建生产级 AI Agent** — 用 Python 一步步搭建真实可用的 AI 智能体，专为编程初学者设计。

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 这是什么？

Mini Agent 是一套**循序渐进的 AI Agent 教学课程**，带你从零开始，亲手搭建一个完整的 AI Agent 框架。每个章节都是独立的小课程，介绍一个核心概念，并提供可以立刻运行的代码。

学完之后，你将真正理解驱动生产级 Agent 背后的每一个组件——而不只是调用别人的 SDK。

---

## 你将学到什么

| 章节 | 主题 | 核心概念 |
|------|------|----------|
| 01 | LLM 客户端 | 抽象基类（ABC）、重试 + 指数退避、流式输出 |
| 02 | Agent 循环 | ReAct 模式、工具调用解析、迭代控制 |
| 03 | 工具系统 | 装饰器工厂、JSON Schema、工具注册表 |
| 04 | 记忆系统 | 滑动窗口（deque）、JSON 持久化、搜索 |
| 05 | 上下文窗口 | Token 计数（tiktoken）、裁剪策略 |
| 06 | 提示词工程 | Builder 模式、模板、少样本提示 |
| 07 | 技能系统 | 插件架构、自动注册、组合 |

---

## 项目结构

```
mini_agent/
├── SYLLABUS.md              # 完整课程大纲（中文）
├── requirements.txt         # 依赖列表
├── pyproject.toml           # 项目配置文件
│
├── chapters/                # 📚 教学章节（从这里开始！）
│   ├── ch01_llm_client/     # LLM 抽象层 + extended_reading.md
│   ├── ch02_agent_loop/     # ReAct Agent 循环 + extended_reading.md
│   ├── ch03_tools/          # 带装饰器的工具系统 + extended_reading.md
│   ├── ch04_memory/         # 对话记忆 + 持久化记忆 + extended_reading.md
│   ├── ch05_context/        # 上下文窗口管理 + extended_reading.md
│   ├── ch06_prompt/         # 提示词构建模式 + extended_reading.md
│   └── ch07_skills/         # 技能插件系统 + extended_reading.md
│
└── mini_agent/              # 🚀 完整生产包
    ├── config.py            # 集中配置（环境变量驱动）
    ├── providers.py         # LLM 提供商注册表（通义、Kimi、MiniMax、DeepSeek、智谱…）
    ├── main.py              # 命令行入口（Rich 美化界面）
    ├── core/
    │   ├── llm.py           # OpenAI 兼容客户端
    │   ├── loop.py          # 完整 ReAct Agent 循环
    │   ├── context.py       # Token 计数 + 裁剪
    │   └── prompt.py        # 系统提示词构建器
    ├── tools/
    │   ├── base.py          # 工具 + 注册表抽象
    │   └── builtins.py      # 内置工具（计算器、文件、记忆…）
    ├── memory/
    │   ├── conversation.py  # 短期对话记忆
    │   └── persistent.py    # JSON 文件长期记忆
    └── skills/
        └── base.py          # 技能抽象 + 注册表
```

---

## 快速开始

### 第一步：环境准备

> **环境要求**：Python 3.10 或更高版本。
>
> 检查你的 Python 版本：
> ```bash
> python --version
> ```
> 如果显示低于 3.10，请到 [python.org](https://python.org) 下载最新版本。

### 第二步：克隆并安装

```bash
git clone https://github.com/samz406/mini_agent.git
cd mini_agent
pip install -e .
```

> **说明**：`pip install -e .` 以"可编辑模式"安装项目。这意味着你修改代码后无需重新安装，改动立即生效。

### 第三步：配置 API Key

**什么是 API Key？**
API Key（接口密钥）就像访问 AI 服务的"门票"。每个 AI 提供商都需要你注册账号，然后在控制台生成一串密钥字符串。程序凭借这个密钥来调用 AI 模型。

根据你选择的提供商，设置对应的环境变量：

```bash
# 通义千问（阿里云，推荐国内用户）
# 申请地址：https://dashscope.aliyun.com
export DASHSCOPE_API_KEY=sk-your-key-here

# DeepSeek（性价比高）
# 申请地址：https://platform.deepseek.com
export DEEPSEEK_API_KEY=sk-your-key-here

# Kimi / 月之暗面
# 申请地址：https://platform.moonshot.cn
export MOONSHOT_API_KEY=sk-your-key-here

# MiniMax
# 申请地址：https://www.minimax.io
export MINIMAX_API_KEY=your-key-here

# 智谱 GLM
# 申请地址：https://open.bigmodel.cn
export ZHIPU_API_KEY=your-key-here

# OpenAI（默认，需要科学上网）
# 申请地址：https://platform.openai.com
export OPENAI_API_KEY=sk-your-key-here
```

**推荐方式：创建 `.env` 文件**（这样不用每次重新设置）：
```bash
echo "MINI_AGENT_PROVIDER=deepseek" > .env
echo "DEEPSEEK_API_KEY=sk-your-key-here" >> .env
```

### 第四步：运行 Agent

```bash
# 使用默认提供商（OpenAI gpt-4o-mini）
mini-agent

# 通过 --provider 参数选择提供商
mini-agent --provider qwen
mini-agent --provider kimi
mini-agent --provider minimax
mini-agent --provider deepseek
mini-agent --provider glm

# 在某个提供商下指定具体模型
mini-agent --provider qwen --model qwen-max

# 也可以用环境变量指定提供商
MINI_AGENT_PROVIDER=deepseek mini-agent
```

---

## 支持的 LLM 提供商

所有提供商都使用 OpenAI 兼容接口，无需额外安装依赖。

| 提供商 | 环境变量 | 默认模型 | API 地址 |
|--------|----------|----------|----------|
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` | `https://api.openai.com/v1` |
| `qwen` | `DASHSCOPE_API_KEY` | `qwen-turbo` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `kimi` | `MOONSHOT_API_KEY` | `moonshot-v1-8k` | `https://api.moonshot.cn/v1` |
| `minimax` | `MINIMAX_API_KEY` | `MiniMax-Text-01` | `https://api.minimax.chat/v1` |
| `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` | `https://api.deepseek.com/v1` |
| `glm` | `ZHIPU_API_KEY` | `glm-4-flash` | `https://open.bigmodel.cn/api/paas/v4` |

在 Agent 运行时输入 `/providers` 命令，可以查看所有提供商列表（当前使用的会高亮显示）。

---

## 交互命令

Agent 启动后，可以使用以下斜杠命令：

| 命令 | 说明 |
|------|------|
| `/help` | 显示所有可用命令 |
| `/tools` | 列出所有可用工具 |
| `/memory` | 查看持久化记忆内容 |
| `/clear` | 清空当前对话历史 |
| `/provider` | 显示当前使用的提供商及所有提供商 |
| `/providers` | 列出所有支持的 LLM 提供商 |
| `/quit` | 退出 Agent |

---

## 内置工具

Agent 默认携带以下工具：

| 工具 | 说明 |
|------|------|
| `calculate` | 安全数学计算（基于 AST 解析，不使用危险的 `eval`） |
| `get_current_time` | 获取当前时间 |
| `get_current_date` | 获取当前日期 |
| `read_file` | 读取文本文件（最多 10000 字符） |
| `write_file` | 写入或创建文件 |
| `list_directory` | 列出目录内容 |
| `search_memory` | 搜索持久化记忆 |
| `save_memory` | 向持久化记忆中保存一条信息 |

---

## 各章节运行指南

每个章节都**完全独立**，可以单独运行，无需依赖其他章节。

```bash
# 第一章：LLM 客户端（需要 API Key）
cd chapters/ch01_llm_client
python llm_client.py

# 第二章：Agent 循环（无需 API Key，使用模拟 LLM）
cd chapters/ch02_agent_loop
python agent_loop.py

# 第三章：工具系统
cd chapters/ch03_tools
python example_tools.py

# 第四章：记忆系统
cd chapters/ch04_memory
python memory.py

# 第五章：上下文管理
cd chapters/ch05_context
python context_manager.py

# 第六章：提示词构建
cd chapters/ch06_prompt
python prompt_builder.py

# 第七章：技能系统
cd chapters/ch07_skills
python skill_system.py
```

> 每个章节目录中还有一个 `extended_reading.md`，对比了 nanobot、hermes-agent、openclaw 等主流开源项目在同一功能上的设计实现，帮助你理解不同的工程取舍。

---

## 环境变量参考

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MINI_AGENT_PROVIDER` | `openai` | 提供商名称（`openai`、`qwen`、`kimi`、`minimax`、`deepseek`、`glm`） |
| `OPENAI_API_KEY` | *（openai 必填）* | OpenAI API 密钥 |
| `DASHSCOPE_API_KEY` | *（qwen 必填）* | 阿里云灵积 API 密钥 |
| `MOONSHOT_API_KEY` | *（kimi 必填）* | 月之暗面 API 密钥 |
| `MINIMAX_API_KEY` | *（minimax 必填）* | MiniMax API 密钥 |
| `DEEPSEEK_API_KEY` | *（deepseek 必填）* | DeepSeek API 密钥 |
| `ZHIPU_API_KEY` | *（glm 必填）* | 智谱 AI API 密钥 |
| `MINI_AGENT_MODEL` | *（提供商默认值）* | 覆盖模型名称 |
| `MINI_AGENT_API_BASE` | *（提供商默认值）* | 自定义 API 地址 |
| `MINI_AGENT_MAX_ITERATIONS` | `10` | ReAct 循环最大迭代次数 |
| `MINI_AGENT_MAX_TOKENS` | `8000` | 上下文窗口 Token 预算 |
| `MINI_AGENT_TEMPERATURE` | `0.7` | LLM 温度参数（越高越随机） |
| `MINI_AGENT_SYSTEM_PROMPT` | *（默认角色设定）* | 自定义系统提示词 |
| `MINI_AGENT_MEMORY_FILE` | `.mini_agent_memory.json` | 持久化记忆文件路径 |

---

## 学习路径建议

```
第一章（LLM Client）
      ↓
第二章（Agent Loop）
      ↓
第三章（Tools）
      ↓
第四章（Memory）
      ↓
第五章（Context）
      ↓
第六章（Prompt）
      ↓
第七章（Skills）
      ↓
  完整项目（mini_agent/）
```

建议按章节顺序学习：先读 `README.md` 了解概念，再研读代码，最后运行示例验证理解，最后阅读 `extended_reading.md` 开拓视野。

---

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

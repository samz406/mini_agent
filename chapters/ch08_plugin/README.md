# 第八章：插件机制（Plugin Mechanism）

## 你将学到什么

本章构建一个**基于文件系统的插件机制**：Agent 在运行时自动扫描指定目录，动态加载其中的插件，无需修改任何核心代码即可扩展能力。

> 📖 本章是第七章技能系统的进化版本。如果还没有学过第七章，建议先完成 `ch07_skills`。

---

## 插件 vs 技能：哪里不同？

| 维度 | 第七章：技能（Skill） | 第八章：插件（Plugin） |
|---|---|---|
| 定义方式 | Python 类 + `@skill` 装饰器 | 目录 + `plugin.json` + `.py` 文件 |
| 注册时机 | **导入时**（静态，import-time） | **运行时**（动态，runtime scan） |
| 启用/禁用 | 从 `skill_names` 列表中删除 | 修改 `plugin.json` 中的 `"enabled": false` |
| 添加新插件 | 修改源代码 | 直接放入一个新目录 |
| 生命周期钩子 | 无 | `on_load` / `on_unload` |
| 隔离性 | 共享同一模块命名空间 | 每个插件独立的模块命名空间 |

**什么时候用技能，什么时候用插件？**
- 技能适合**内置、可预期**的能力集合（开发时确定）。
- 插件适合**用户扩展、第三方贡献**的能力（运行时发现）。

---

## 插件目录结构

每个插件是一个独立的文件夹，包含两个文件：

```
plugins/
├── calculator/
│   ├── plugin.json     ← 元数据清单（名称、版本、描述、是否启用）
│   └── impl.py         ← 插件实现（定义 Plugin 子类）
├── datetime_plugin/
│   ├── plugin.json
│   └── impl.py
└── disabled_example/
    ├── plugin.json     ← "enabled": false → 被 PluginManager 跳过
    └── impl.py
```

**要添加新插件，只需新建一个目录并放入两个文件**——无需修改任何已有代码。

---

## 插件清单（plugin.json）

```json
{
    "name": "calculator",
    "version": "1.0.0",
    "description": "Provides safe mathematical calculation tools.",
    "entry": "impl",
    "enabled": true,
    "prompt_addition": "You can perform mathematical calculations using the 'calc' tool."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 唯一标识，必须与目录名一致 |
| `version` | string | 语义化版本号 |
| `description` | string | 人类可读描述，用于列表展示 |
| `entry` | string | 入口 Python 文件名（不含 `.py`） |
| `enabled` | boolean | `false` 时插件被发现但不加载 |
| `prompt_addition` | string | 插件激活时追加到系统提示词的文字 |

---

## Plugin 基类与生命周期钩子

```python
class Plugin(ABC):
    manifest: PluginManifest   # 由 PluginLoader 在实例化后自动注入

    def on_load(self) -> None:
        """插件加载后立即调用：适合建立连接、读取配置。"""

    def on_unload(self) -> None:
        """插件被卸载时调用：适合释放资源、关闭连接。"""

    @abstractmethod
    def get_tools(self) -> list[SimpleTool]:
        """返回此插件提供的工具列表。"""
        ...

    def get_prompt_addition(self) -> str:
        """返回清单中声明的提示词补充（可覆盖）。"""
        return self.manifest.prompt_addition
```

**生命周期钩子的价值**：实际应用中，`on_load` 可以建立数据库连接、加载机器学习模型；`on_unload` 可以确保连接优雅关闭、缓存被刷盘。技能系统没有这个机制，插件可以管理有状态的外部资源。

---

## 动态加载：importlib 的作用

插件加载的核心是 Python 的 `importlib.util`：

```python
# 1. 根据文件路径创建模块规格（spec）
spec = importlib.util.spec_from_file_location("_plugin_calculator", entry_path)

# 2. 从规格创建一个空模块
module = importlib.util.module_from_spec(spec)

# 3. 注入基类，让插件代码无需显式 import
module.__dict__["Plugin"] = Plugin
module.__dict__["SimpleTool"] = SimpleTool

# 4. 执行插件源码，填充模块命名空间
spec.loader.exec_module(module)

# 5. 在模块中找到 Plugin 子类并实例化
plugin_cls = find_plugin_class(module)
instance = plugin_cls()
instance.manifest = manifest
instance.on_load()
```

**为什么用 `importlib` 而不是普通 `import`？**

| 方式 | 问题 |
|------|------|
| `import calculator.impl` | 需要 plugins 目录在 `sys.path` 上，会污染模块命名空间 |
| `exec(open(path).read())` | 不安全，没有独立的模块命名空间 |
| `importlib.util` | ✅ 独立命名空间，不修改 `sys.path`，可控可追溯 |

---

## PluginManager：全生命周期管理

```python
manager = PluginManager("plugins/")

# 批量发现并加载所有 enabled=true 的插件
manager.discover_and_load()   # → ['calculator', 'datetime_plugin']

# 获取所有插件提供的工具（合并列表）
tools = manager.get_all_tools()

# 获取所有插件的提示词补充
additions = manager.get_system_prompt_additions()

# 按需卸载（触发 on_unload）
manager.unload("calculator")

# 热重载：卸载 + 重新从磁盘读取清单并加载
manager.reload("calculator")
```

**热重载**（`reload`）是插件机制相比技能系统的关键优势：在不重启进程的情况下，可以更新插件代码或配置，然后 reload 生效。

---

## 如何运行

```bash
cd chapters/ch08_plugin
python plugin_system.py
```

你将看到：
1. PluginManager 扫描 `plugins/` 目录，加载两个启用的插件，跳过被禁用的插件
2. 各插件的 `on_load` 钩子被调用
3. 合并后的工具列表和提示词补充
4. 工具实际执行结果
5. 卸载（触发 `on_unload`）和重新加载的演示

---

## 如何添加自己的插件

1. 在 `plugins/` 下新建一个目录，例如 `plugins/my_plugin/`
2. 创建 `plugin.json`（参考上方格式）
3. 创建 `impl.py`，继承 `Plugin`，实现 `get_tools()`

```python
# plugins/my_plugin/impl.py

class MyPlugin(Plugin):               # Plugin 由 loader 自动注入，无需 import
    def on_load(self):
        print("MyPlugin loaded!")

    def get_tools(self):
        def greet(name: str) -> str:
            return f"Hello, {name}!"
        return [SimpleTool("greet", "Greet someone by name.", greet)]
```

重新运行 `python plugin_system.py`，你的插件会被自动发现并加载。

---

## 核心设计模式

| 模式 | 体现 |
|------|------|
| **发现者模式（Discovery）** | `PluginLoader.discover()` 扫描文件系统，无需预先知道插件名称 |
| **工厂方法（Factory Method）** | `PluginLoader.load()` 根据清单动态创建 Plugin 实例 |
| **模板方法（Template Method）** | `Plugin` 基类定义 `on_load`/`on_unload`/`get_tools` 框架 |
| **依赖注入（Dependency Injection）** | `manifest` 由 Loader 注入，插件不需要自己读取 JSON |

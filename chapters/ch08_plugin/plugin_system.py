"""Chapter 8: Plugin Mechanism — Filesystem-based dynamic plugin architecture.

Teaches: plugin manifests (JSON), dynamic importlib loading, plugin lifecycle
         hooks (on_load / on_unload), directory scanning, PluginManager,
         enable/disable without code changes.

Key differences from ch07 Skills
---------------------------------
| Dimension         | ch07 Skills              | ch08 Plugins                    |
|-------------------|--------------------------|---------------------------------|
| Definition        | Python class + @skill    | Directory + plugin.json + .py   |
| Registration      | Import-time decorator    | Runtime filesystem scan         |
| Loading           | Explicit by name         | Auto-discover all enabled        |
| Lifecycle hooks   | None                     | on_load / on_unload             |
| Enable / disable  | Remove from skill_names  | Set "enabled": false in JSON    |
| Adding a plugin   | Modify source code       | Drop a new directory            |
"""

from __future__ import annotations

import importlib.util
import json
import types
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Lightweight tool container (same role as SimpleTool in ch07)
# ---------------------------------------------------------------------------

class SimpleTool:
    """Lightweight callable tool with a name and description."""

    def __init__(self, name: str, description: str, fn: Any) -> None:
        self.name = name
        self.description = description
        self._fn = fn

    def __call__(self, **kwargs: Any) -> Any:
        return self._fn(**kwargs)

    def __repr__(self) -> str:
        return f"SimpleTool(name={self.name!r})"


# ---------------------------------------------------------------------------
# Plugin manifest — loaded from plugin.json
# ---------------------------------------------------------------------------

class PluginManifest(BaseModel):
    """Structured representation of a plugin's plugin.json manifest file.

    Fields
    ------
    name            Unique plugin identifier (must match directory name).
    version         Semantic version string, e.g. "1.0.0".
    description     Human-readable description shown in plugin listings.
    entry           Python source file name (without .py) inside the plugin
                    directory that contains the Plugin subclass.
    enabled         Set to false to skip this plugin during discovery.
    prompt_addition Text to append to the system prompt when this plugin is
                    active.
    """

    name: str
    version: str = "0.1.0"
    description: str = ""
    entry: str = "impl"
    enabled: bool = True
    prompt_addition: str = ""


# ---------------------------------------------------------------------------
# Plugin abstract base class
# ---------------------------------------------------------------------------

class Plugin(ABC):
    """Abstract base for all filesystem plugins.

    Concrete plugins must:
    1. Subclass ``Plugin``.
    2. Implement ``get_tools()``.
    3. Optionally override ``on_load`` / ``on_unload`` for setup/teardown.

    The ``manifest`` attribute is injected by ``PluginLoader`` before
    ``on_load`` is called, so it is always available inside lifecycle hooks
    and ``get_tools``.
    """

    manifest: PluginManifest  # set by PluginLoader after instantiation

    # --- Lifecycle hooks ---------------------------------------------------

    def on_load(self) -> None:
        """Called once immediately after the plugin is instantiated.

        Override to perform initialisation (open connections, read config…).
        """

    def on_unload(self) -> None:
        """Called when the plugin is explicitly unloaded by ``PluginManager``.

        Override to release resources (close connections, flush caches…).
        """

    # --- Capability interface ----------------------------------------------

    @abstractmethod
    def get_tools(self) -> list[SimpleTool]:
        """Return the list of ``SimpleTool`` objects this plugin provides."""
        ...

    def get_prompt_addition(self) -> str:
        """Return the prompt text declared in the manifest (overridable)."""
        return self.manifest.prompt_addition


# ---------------------------------------------------------------------------
# Plugin Loader — dynamic importlib loading
# ---------------------------------------------------------------------------

class PluginLoader:
    """Discovers plugin manifests and dynamically loads their Python modules.

    Discovery
    ---------
    ``PluginLoader`` scans *plugins_dir* for subdirectories that contain a
    ``plugin.json`` file.  Each such directory is treated as one plugin.

    Dynamic loading
    ---------------
    ``importlib.util.spec_from_file_location`` loads the plugin's entry
    module at runtime without permanently modifying ``sys.modules`` or
    requiring the plugins directory to be on ``sys.path``.

    Global injection
    ----------------
    Before executing the entry module, ``PluginLoader`` injects ``Plugin``
    and ``SimpleTool`` into the module's globals so that plugin authors can
    reference them without an explicit import — keeping plugin code concise.
    """

    MANIFEST_FILENAME = "plugin.json"

    def __init__(self, plugins_dir: str | Path) -> None:
        self.plugins_dir = Path(plugins_dir)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[PluginManifest]:
        """Return manifests for every plugin directory found under *plugins_dir*.

        Disabled plugins (``enabled: false``) are included in the result so
        callers can report them; filtering is the responsibility of
        ``PluginManager``.
        """
        manifests: list[PluginManifest] = []
        if not self.plugins_dir.is_dir():
            return manifests

        for subdir in sorted(self.plugins_dir.iterdir()):
            if not subdir.is_dir():
                continue
            manifest_path = subdir / self.MANIFEST_FILENAME
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                manifests.append(PluginManifest(**data))
            except Exception as exc:
                print(f"  [PluginLoader] Skipping {subdir.name}: {exc}")

        return manifests

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, manifest: PluginManifest) -> Plugin:
        """Dynamically import and instantiate the plugin described by *manifest*.

        Steps
        -----
        1. Resolve the entry ``.py`` file path.
        2. Create a fresh ``ModuleType`` and inject helpers into its globals.
        3. Execute the module source into that namespace.
        4. Find the ``Plugin`` subclass defined in the module.
        5. Instantiate it, attach the manifest, call ``on_load``.
        """
        plugin_dir = self.plugins_dir / manifest.name
        entry_path = plugin_dir / f"{manifest.entry}.py"

        if not entry_path.exists():
            raise FileNotFoundError(
                f"Plugin '{manifest.name}': entry module not found at {entry_path}"
            )

        # Build a module spec — this tells Python how to load the file.
        spec = importlib.util.spec_from_file_location(
            f"_plugin_{manifest.name}",
            entry_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {entry_path}")

        module = importlib.util.module_from_spec(spec)

        # Inject base classes so plugin code can reference them without importing.
        self._inject_globals(module)

        # Execute the plugin source in the module's namespace.
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        # Find the Plugin subclass defined in this module.
        plugin_cls = self._find_plugin_class(module)

        instance: Plugin = plugin_cls()
        instance.manifest = manifest
        instance.on_load()
        return instance

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _inject_globals(module: types.ModuleType) -> None:
        """Inject shared base classes into a freshly created module namespace.

        This lets plugin authors write ``class MyPlugin(Plugin)`` without an
        explicit import statement, keeping plugin files short and readable.
        """
        module.__dict__["Plugin"] = Plugin
        module.__dict__["SimpleTool"] = SimpleTool

    @staticmethod
    def _find_plugin_class(module: types.ModuleType) -> type[Plugin]:
        """Return the first concrete ``Plugin`` subclass defined in *module*.

        A class is considered concrete when it is a subclass of ``Plugin``
        but is **not** ``Plugin`` itself (i.e. it provides ``get_tools``).
        """
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Plugin)
                and obj is not Plugin
            ):
                return obj
        raise TypeError(
            f"Module '{module.__name__}' does not define a Plugin subclass."
        )


# ---------------------------------------------------------------------------
# Plugin Manager — orchestrates the full lifecycle
# ---------------------------------------------------------------------------

class PluginManager:
    """Orchestrates plugin discovery, loading, and unloading.

    Usage
    -----
    ::

        manager = PluginManager("chapters/ch08_plugin/plugins")
        manager.discover_and_load()

        for tool in manager.get_all_tools():
            print(tool.name, tool.description)

        manager.unload("calculator")
    """

    def __init__(self, plugins_dir: str | Path) -> None:
        self.loader = PluginLoader(plugins_dir)
        self._loaded: dict[str, Plugin] = {}

    # ------------------------------------------------------------------
    # Discovery + bulk loading
    # ------------------------------------------------------------------

    def discover_and_load(self) -> list[str]:
        """Scan *plugins_dir*, load all enabled plugins, return their names.

        Disabled plugins (``enabled: false`` in ``plugin.json``) are reported
        but not loaded.
        """
        manifests = self.loader.discover()
        loaded: list[str] = []
        skipped: list[str] = []

        for manifest in manifests:
            if not manifest.enabled:
                skipped.append(manifest.name)
                continue
            try:
                plugin = self.loader.load(manifest)
                self._loaded[manifest.name] = plugin
                loaded.append(manifest.name)
            except Exception as exc:
                print(f"  [PluginManager] Failed to load '{manifest.name}': {exc}")

        if skipped:
            print(f"  [PluginManager] Skipped (disabled): {skipped}")

        return loaded

    # ------------------------------------------------------------------
    # Individual load / unload
    # ------------------------------------------------------------------

    def load(self, name: str) -> None:
        """Load a single plugin by directory name (re-reads its manifest)."""
        manifests = self.loader.discover()
        for manifest in manifests:
            if manifest.name == name:
                if not manifest.enabled:
                    raise ValueError(f"Plugin '{name}' is disabled in its manifest.")
                plugin = self.loader.load(manifest)
                self._loaded[name] = plugin
                return
        raise KeyError(f"Plugin '{name}' not found in {self.loader.plugins_dir}")

    def unload(self, name: str) -> None:
        """Unload a plugin by name, calling its ``on_unload`` lifecycle hook."""
        if name not in self._loaded:
            raise KeyError(f"Plugin '{name}' is not currently loaded.")
        self._loaded[name].on_unload()
        del self._loaded[name]

    def reload(self, name: str) -> None:
        """Unload then re-load a plugin (picks up manifest changes on disk)."""
        if name in self._loaded:
            self.unload(name)
        self.load(name)

    # ------------------------------------------------------------------
    # Capability aggregation
    # ------------------------------------------------------------------

    def get_all_tools(self) -> list[SimpleTool]:
        """Return the combined tool list from all loaded plugins."""
        tools: list[SimpleTool] = []
        for plugin in self._loaded.values():
            tools.extend(plugin.get_tools())
        return tools

    def get_system_prompt_additions(self) -> str:
        """Return concatenated system prompt additions from all loaded plugins."""
        parts = [
            p.get_prompt_addition()
            for p in self._loaded.values()
            if p.get_prompt_addition()
        ]
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_loaded(self) -> list[str]:
        """Return names of all currently loaded plugins."""
        return list(self._loaded.keys())

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Return the loaded plugin instance for *name*, or ``None``."""
        return self._loaded.get(name)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    # Resolve the plugins/ directory relative to this script.
    here = Path(__file__).parent
    plugins_dir = here / "plugins"

    print("=" * 55)
    print("  Chapter 8: Plugin Mechanism Demo")
    print("=" * 55)

    # ── 1. Discovery + loading ─────────────────────────────────────────
    print("\n[1] Discovering and loading plugins …\n")
    manager = PluginManager(plugins_dir)
    loaded_names = manager.discover_and_load()
    print(f"\nLoaded plugins: {loaded_names}")

    # ── 2. Introspection ───────────────────────────────────────────────
    print("\n[2] Available tools:\n")
    for t in manager.get_all_tools():
        print(f"  • {t.name}: {t.description}")

    print("\n[2] System prompt additions:\n")
    print(manager.get_system_prompt_additions())

    # ── 3. Tool execution ─────────────────────────────────────────────
    print("\n[3] Executing tools:\n")
    tool_map = {t.name: t for t in manager.get_all_tools()}
    print(f"  calc('7 ** 3')      = {tool_map['calc'](expression='7 ** 3')}")
    print(f"  calc('22 / 7')      = {tool_map['calc'](expression='22 / 7')}")
    print(f"  now_time()          = {tool_map['now_time']()}")
    print(f"  now_date()          = {tool_map['now_date']()}")

    # ── 4. Lifecycle: unload / reload ─────────────────────────────────
    print("\n[4] Unloading 'calculator' plugin …\n")
    manager.unload("calculator")
    print(f"  Loaded after unload: {manager.list_loaded()}")

    print("\n[4] Reloading 'calculator' plugin …\n")
    manager.reload("calculator")
    print(f"  Loaded after reload: {manager.list_loaded()}")

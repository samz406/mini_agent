"""Disabled example plugin — intentionally never loaded.

This file exists only to show that a fully-formed plugin directory
with ``"enabled": false`` in plugin.json is silently skipped by the
PluginManager during discovery.
"""

from __future__ import annotations


class DisabledExamplePlugin(Plugin):  # type: ignore[name-defined]
    """A plugin that will never be loaded because enabled=false."""

    def get_tools(self) -> list:
        return []

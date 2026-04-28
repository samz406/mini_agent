"""DateTime plugin implementation for ch08_plugin demo."""

from __future__ import annotations

from datetime import datetime


class DateTimePlugin(Plugin):  # type: ignore[name-defined]  # injected by loader
    """Date and time information plugin."""

    def on_load(self) -> None:
        print(f"  [DateTimePlugin] loaded (v{self.manifest.version})")

    def on_unload(self) -> None:
        print(f"  [DateTimePlugin] unloaded")

    def get_tools(self) -> list:
        def now_time() -> str:
            return datetime.now().strftime("%H:%M:%S")

        def now_date() -> str:
            return datetime.now().strftime("%Y-%m-%d")

        return [
            SimpleTool("now_time", "Return the current local time.", now_time),  # type: ignore[name-defined]
            SimpleTool("now_date", "Return the current local date.", now_date),  # type: ignore[name-defined]
        ]

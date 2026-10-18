"""
System Tray Manager for BreakTimer Ultra.
Uses pystray to provide a background tray icon with live status and quick action menu.
"""

import os
import threading
from typing import Callable, Optional
from PIL import Image
import pystray

TRAY_ICON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "icons", "tray_icon.png"
)


class TrayManager:
    def __init__(self,
                 on_open_dashboard: Callable[[], None],
                 on_take_break: Callable[[], None],
                 on_toggle_pause: Callable[[], None],
                 on_quit: Callable[[], None]):
        self.on_open_dashboard = on_open_dashboard
        self.on_take_break = on_take_break
        self.on_toggle_pause = on_toggle_pause
        self.on_quit = on_quit

        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self.current_status_text = "BreakTimer Ultra — 準備完了"

    def start(self) -> None:
        if os.path.exists(TRAY_ICON_PATH):
            image = Image.open(TRAY_ICON_PATH)
        else:
            # Fallback simple 32x32 blue image
            image = Image.new("RGBA", (32, 32), (56, 139, 253, 255))

        menu = pystray.Menu(
            pystray.MenuItem(lambda text: self.current_status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙ ダッシュボード・設定を開く", self._on_open, default=True),
            pystray.MenuItem("☕ 今すぐ休憩を開始", self._on_break),
            pystray.MenuItem("⏸ 一時停止 / 再開", self._on_pause),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ 終了", self._on_quit)
        )

        self.icon = pystray.Icon("BreakTimerUltra", image, "BreakTimer Ultra", menu)

        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def update_status(self, text: str) -> None:
        self.current_status_text = text
        if self.icon:
            self.icon.title = f"BreakTimer Ultra: {text}"

    def stop(self) -> None:
        if self.icon:
            self.icon.stop()

    def _on_open(self, icon, item) -> None:
        self.on_open_dashboard()

    def _on_break(self, icon, item) -> None:
        self.on_take_break()

    def _on_pause(self, icon, item) -> None:
        self.on_toggle_pause()

    def _on_quit(self, icon, item) -> None:
        self.on_quit()

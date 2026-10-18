"""
Audio notification manager using native Windows winsound.
Supports BreakTimer's built-in sound themes: ping, gong, bloop, blip, scifi.
"""

import os
import winsound
from typing import Optional

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")


class AudioManager:
    def __init__(self, sounds_dir: Optional[str] = None):
        self.sounds_dir = sounds_dir or ASSETS_DIR

    def _play(self, filename: str) -> None:
        filepath = os.path.join(self.sounds_dir, filename)
        if os.path.exists(filepath):
            try:
                winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                print(f"[Audio] Error playing sound: {e}")
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            # Fallback beep
            winsound.MessageBeep(winsound.MB_ICONASTERISK)

    def play_break_start(self, theme: str = "ping", enabled: bool = True) -> None:
        if not enabled or theme.lower() == "none":
            return
        filename = f"{theme.lower()}_start.wav"
        self._play(filename)

    def play_break_end(self, theme: str = "ping", enabled: bool = True) -> None:
        if not enabled or theme.lower() == "none":
            return
        filename = f"{theme.lower()}_end.wav"
        self._play(filename)

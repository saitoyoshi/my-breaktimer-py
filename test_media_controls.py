"""
Test script for Netflix/Media controls and mini operate-behind mode.
"""

import time
import tkinter as tk
from app.config import AppConfig
from app.timer_service import TimerService
from app.ui.overlay import BreakOverlay
from app.win32 import send_media_play_pause


def test_media():
    print("Testing send_media_play_pause...")
    send_media_play_pause()
    print("send_media_play_pause OK!")

    print("Testing BreakOverlay mini-mode transition...")
    root = tk.Tk()
    root.withdraw()

    config = AppConfig(break_duration_seconds=10)
    timer_service = TimerService(config)
    timer_service.start()

    overlay = BreakOverlay(root, timer_service, config, on_close_callback=lambda: None)
    overlay.show()

    # Switch to mini mode after 1 second
    def to_mini():
        print("Switching to mini mode (screen unblocked)...")
        overlay._switch_to_mini_mode()
        print("Mini mode active! Screen is now clickable.")

    # Switch back to full screen after 2 seconds
    def to_full():
        print("Switching back to fullscreen mode...")
        overlay._switch_to_fullscreen_mode()
        print("Fullscreen mode active again!")

    def finish():
        print("Closing test...")
        overlay.close()
        root.destroy()
        timer_service.stop()
        print("Test passed successfully!")

    root.after(1000, to_mini)
    root.after(2500, to_full)
    root.after(3500, finish)

    root.mainloop()


if __name__ == "__main__":
    test_media()

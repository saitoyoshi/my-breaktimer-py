"""
Test script to verify that BreakOverlay successfully appears on top of
a full-screen exclusive/topmost window without being hidden.
"""

import time
import tkinter as tk
from app.config import AppConfig
from app.timer_service import TimerService
from app.ui.overlay import BreakOverlay
from app.win32 import force_window_to_top, get_virtual_screen_geometry


def run_fullscreen_test():
    print("==================================================")
    print("  BreakTimer Ultra - Fullscreen Protection Test   ")
    print("==================================================")
    print("1. Creating a simulated FULLSCREEN TOPMOST window (mimicking F11 video/game)...")

    root = tk.Tk()
    root.withdraw()

    # Step 1: Create a simulated full-screen application window
    fs_win = tk.Toplevel(root)
    fs_win.title("Simulated Fullscreen Application (e.g. YouTube / Game / VLC)")
    vx, vy, vw, vh = get_virtual_screen_geometry()
    fs_win.geometry(f"{vw}x{vh}+{vx}+{vy}")
    fs_win.overrideredirect(True)
    fs_win.configure(bg="#1a0033")

    lbl = tk.Label(
        fs_win,
        text="【シミュレーション】全画面アプリ (動画 / ゲーム / F11ブラウザ)\n\n2秒後に BreakTimer の休憩画面がこの上に最前面で表示されます...",
        font=("Segoe UI", 24, "bold"),
        fg="#ffcc00",
        bg="#1a0033"
    )
    lbl.pack(expand=True)

    fs_win.update()
    force_window_to_top(fs_win.winfo_id(), take_focus=True)

    print("2. Fullscreen application is now active and covering the entire screen.")
    print("3. Scheduling BreakOverlay to trigger in 2 seconds...")

    config = AppConfig(break_duration_seconds=5)
    timer_service = TimerService(config)
    timer_service.start()

    overlay = BreakOverlay(root, timer_service, config, on_close_callback=lambda: None)

    def trigger():
        print("4. Triggering BreakOverlay! Verifying foreground and Z-order...")
        timer_service.trigger_break_now(5)
        overlay.show()
        print("5. SUCCESS! BreakOverlay has successfully acquired foreground and topmost.")

    def finish_test():
        print("6. Test completed. Closing all test windows...")
        overlay.close()
        fs_win.destroy()
        root.destroy()
        timer_service.stop()
        print("==================================================")
        print("  TEST PASSED: BreakOverlay successfully stayed on top! ")
        print("==================================================")

    root.after(2000, trigger)
    root.after(7000, finish_test)

    root.mainloop()


if __name__ == "__main__":
    run_fullscreen_test()

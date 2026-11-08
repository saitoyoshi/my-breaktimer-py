"""
Main entry point for BreakTimer Ultra.
Connects timer service, UI dashboard, fullscreen break overlay, and system tray.
"""
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import psutil

from app.config import ConfigManager
from app.audio import AudioManager
from app.timer_service import TimerService, TimerState
from app.win32 import (
    acquire_single_instance, release_single_instance, send_media_play_pause
)
from app.ui.main_window import MainWindow
from app.ui.overlay import BreakOverlay
from app.ui.prompt_banner import BreakPromptBanner
from app.ui.tray import TrayManager


def kill_existing_instances() -> int:
    """
    Kill all other Python processes running main.py for BreakTimer Ultra.
    Returns the number of processes killed.
    Works with both `python main.py` and `pythonw main.py`.
    """
    current_pid = os.getpid()
    script_name = "main.py"
    # Get the directory of this script to match against
    script_dir = os.path.dirname(os.path.abspath(__file__))
    killed = 0

    for proc in psutil.process_iter(['pid', 'cmdline', 'exe', 'name']):
        try:
            pid = proc.info['pid']
            if pid == current_pid:
                continue

            proc_name = (proc.info.get('name') or '').lower()
            # Only look at python/pythonw processes
            if 'python' not in proc_name:
                continue

            cmd = proc.info.get('cmdline')
            if not cmd:
                continue

            # Check if any argument references main.py in our script directory
            for arg in cmd:
                try:
                    arg_abs = os.path.abspath(arg)
                    if (os.path.basename(arg).lower() == script_name
                            and os.path.dirname(arg_abs).lower() == script_dir.lower()):
                        proc.terminate()
                        killed += 1
                        break
                except (ValueError, OSError):
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return killed





class BreakTimerApp:
    def __init__(self):
        # 1. Initialize root Tk
        self.root = tk.Tk()
        self.root.withdraw()  # Start hidden or show dashboard

        # 2. Config & Services
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        self.audio_manager = AudioManager()
        self.timer_service = TimerService(self.config)

        # 3. Overlay, Prompt Banner, and Main Window
        self.overlay: Optional[BreakOverlay] = None
        self.prompt_banner: Optional[BreakPromptBanner] = None
        self.main_window = MainWindow(
            root=self.root,
            timer_service=self.timer_service,
            config_manager=self.config_manager,
            audio_manager=self.audio_manager,
            on_test_break=self.test_break,
            on_test_prompt=self.test_prompt
        )

        # 4. System Tray
        self.tray = TrayManager(
            on_open_dashboard=self.show_dashboard_threadsafe,
            on_take_break=self.take_break_threadsafe,
            on_toggle_pause=self.toggle_pause_threadsafe,
            on_quit=self.quit_app_threadsafe,
            on_reset_timer=self.reset_timer_threadsafe
        )

        # 5. Wire Timer Callbacks
        self.timer_service.on_tick_callbacks.append(self._on_timer_tick)
        self.timer_service.on_break_prompt_callbacks.append(self._on_break_prompt)
        self.timer_service.on_break_prompt_close_callbacks.append(self._on_break_prompt_close)
        self.timer_service.on_break_start_callbacks.append(self._on_break_start)
        self.timer_service.on_break_end_callbacks.append(self._on_break_end)
        self.timer_service.on_state_change_callbacks.append(self._on_state_change)
        self.timer_service.on_log_callbacks.append(self._on_log_entry)

        # Show main dashboard initially
        self.main_window.show()


    def _on_log_entry(self, entry: str) -> None:
        self.root.after(0, lambda: self.main_window.add_log_entry(entry))


    def run(self) -> None:
        # Start background timer and tray
        self.timer_service.start()
        self.tray.start()

        # Run Tkinter mainloop
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit_app()

    # Thread-safe UI triggers from Tray
    def show_dashboard_threadsafe(self) -> None:
        self.root.after(0, self.main_window.show)

    def take_break_threadsafe(self) -> None:
        self.root.after(0, self.timer_service.trigger_break_now)

    def reset_timer_threadsafe(self) -> None:
        def _reset():
            self.timer_service.reset_work_timer("手動リセット (トレイメニュー)")
            self.main_window.update_tick(
                self.timer_service.remaining_seconds,
                self.timer_service.current_total_seconds,
                self.timer_service.state
            )
        self.root.after(0, _reset)

    def toggle_pause_threadsafe(self) -> None:
        def _toggle():
            if self.timer_service.state == TimerState.PAUSED:
                self.timer_service.resume()
            else:
                self.timer_service.pause()
        self.root.after(0, _toggle)

    def quit_app_threadsafe(self) -> None:
        self.root.after(0, self.quit_app)

    def test_break(self, duration_seconds: int = 5) -> None:
        """Trigger an instant short break to test fullscreen penetration."""
        self.timer_service.trigger_break_now(duration_seconds=duration_seconds)

    def test_prompt(self, duration_seconds: int = 15) -> None:
        """Trigger the pre-break prompt banner to test notification flow."""
        self.timer_service.trigger_break_prompt()

    # Timer Service Callbacks (executed on worker thread -> dispatch to mainloop)
    def _on_timer_tick(self, remaining: int, total: int, state: TimerState) -> None:
        def _update():
            # Update main window dashboard
            self.main_window.update_tick(remaining, total, state)

            # Update overlay if active
            if self.overlay:
                self.overlay.update_tick(remaining, total)

            # Update prompt banner if active
            if self.prompt_banner:
                self.prompt_banner.update_tick(remaining, total)

            # Update tray text
            mins = remaining // 60
            secs = remaining % 60
            time_fmt = f"{mins:02d}:{secs:02d}"
            target_str = self.timer_service.get_target_time_str()
            if state == TimerState.WORKING:
                self.tray.update_status(f"作業中 — 次回 {target_str} (あと {time_fmt})")
            elif state == TimerState.PROMPTING:
                self.tray.update_status(f"休憩の確認中 — あと {time_fmt}")
            elif state == TimerState.BREAKING:
                self.tray.update_status(f"休憩中 — 残り {time_fmt}")
            elif state == TimerState.PAUSED:
                self.tray.update_status("タイマー一時停止中")

        self.root.after(0, _update)

    def _on_break_prompt(self) -> None:
        def _show_prompt():
            # Close existing prompt if any
            if self.prompt_banner:
                self.prompt_banner.close()

            # Play subtle prompt sound
            # Removed duplicate alarm sound; alarm will play only at break start

            # Show floating prompt banner at the top of the screen
            self.prompt_banner = BreakPromptBanner(
                root=self.root,
                timer_service=self.timer_service,
                config=self.config,
                on_close_callback=self._on_prompt_closed
            )
            self.prompt_banner.show()

        self.root.after(0, _show_prompt)

    def _on_break_prompt_close(self) -> None:
        def _close_prompt():
            if self.prompt_banner:
                self.prompt_banner.close()
                self.prompt_banner = None
        self.root.after(0, _close_prompt)

    def _on_prompt_closed(self) -> None:
        self.prompt_banner = None

    def _on_break_start(self) -> None:
        def _start():
            # Ensure prompt banner is closed
            if self.prompt_banner:
                self.prompt_banner.close()
                self.prompt_banner = None

            # Auto-pause video/music (Netflix, YouTube, etc.) if enabled
            if self.config.auto_pause_media:
                try:
                    send_media_play_pause()
                    self.timer_service._log("動画/音楽を自動一時停止 (Netflix/YouTube)")
                except Exception as e:
                    print(f"[Main] Auto pause error: {e}")

            # Play start sound
            self.audio_manager.play_break_start(
                theme=self.config.sound_theme,
                enabled=self.config.sound_enabled
            )

            # Create and show fullscreen overlay
            if not self.overlay:
                self.overlay = BreakOverlay(
                    root=self.root,
                    timer_service=self.timer_service,
                    config=self.config,
                    on_close_callback=self._on_overlay_closed
                )
            self.overlay.show()

        self.root.after(0, _start)


    def _on_break_end(self, completed: bool) -> None:
        def _end():
            # Play end sound
            if completed:
                self.audio_manager.play_break_end(
                    theme=self.config.sound_theme,
                    enabled=self.config.sound_enabled
                )

            # Auto-resume media if configured
            if completed and self.config.auto_resume_media:
                try:
                    send_media_play_pause()
                    self.timer_service._log("動画/音楽を自動再開")
                except Exception as e:
                    print(f"[Main] Auto resume error: {e}")

            # Close overlay
            if self.overlay:
                self.overlay.close()
                self.overlay = None

        self.root.after(0, _end)


    def _on_overlay_closed(self) -> None:
        self.overlay = None

    def _on_state_change(self, state: TimerState) -> None:
        pass

    def quit_app(self) -> None:
        self.timer_service.stop()
        self.tray.stop()
        if self.prompt_banner:
            self.prompt_banner.close()
        if self.overlay:
            self.overlay.close()
        # Release the singleton mutex so a new instance can start immediately
        release_single_instance()
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)



if __name__ == "__main__":
    # Step 1: Try to acquire the singleton mutex
    if not acquire_single_instance():
        # Another instance is running. Kill it so we can take over (reset/restart).
        print("[Main] 既存のインスタンスを検出。終了させて再起動します...")
        killed = kill_existing_instances()
        if killed > 0:
            print(f"[Main] {killed} 個のプロセスを終了しました。Mutex解放を待機中...")

        # Release and re-acquire: the old mutex handle was "already exists", discard it
        release_single_instance()

        # Wait for the killed processes to fully exit and release the mutex
        max_retries = 20  # up to 4 seconds
        acquired = False
        for i in range(max_retries):
            time.sleep(0.2)
            if acquire_single_instance():
                acquired = True
                print(f"[Main] Mutex取得成功 (リトライ {i+1}/{max_retries})")
                break
            else:
                release_single_instance()

        if not acquired:
            # Last resort: force-kill any remaining processes and try once more
            kill_existing_instances()
            time.sleep(1.0)
            release_single_instance()
            if not acquire_single_instance():
                release_single_instance()
                root_temp = tk.Tk()
                root_temp.withdraw()
                messagebox.showerror(
                    "BreakTimer Ultra",
                    "既存のプロセスを終了できませんでした。\n"
                    "タスクマネージャーから pythonw / python のプロセスを終了してから再起動してください。"
                )
                root_temp.destroy()
                sys.exit(1)

    app = BreakTimerApp()
    app.run()

import unittest
import time
import tkinter as tk
from app.config import AppConfig, ConfigManager
from app.timer_service import TimerService, TimerState
from app.audio import AudioManager
from app.ui.main_window import MainWindow


class TestResetTimer(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(
            work_duration_seconds=1200,  # 20 minutes
            break_duration_seconds=20
        )
        self.timer = TimerService(self.config)

    def test_reset_during_countdown(self):
        """Simulate timer running at 14:00 (840s left) and reset to 20:00 (1200s)."""
        self.timer.start()
        # Simulate timer running down to 14:00
        self.timer.target_time = time.time() + 840
        self.timer.remaining_seconds = 840
        self.assertEqual(self.timer.remaining_seconds, 840)

        # User clicks reset
        self.timer.reset_work_timer("ユーザーによるタイマーリセット")

        self.assertEqual(self.timer.state, TimerState.WORKING)
        self.assertEqual(self.timer.remaining_seconds, 1200)
        self.assertEqual(self.timer.current_total_seconds, 1200)
        self.assertAlmostEqual(self.timer.target_time, time.time() + 1200, delta=2.0)

    def test_reset_during_pause(self):
        """Simulate resetting while paused: should resume into fresh 20:00 working state."""
        self.timer.start()
        self.timer.pause()
        self.assertEqual(self.timer.state, TimerState.PAUSED)

        self.timer.reset_work_timer("一時停止中からのリセット")
        self.assertEqual(self.timer.state, TimerState.WORKING)
        self.assertEqual(self.timer.remaining_seconds, 1200)

    def test_main_window_reset_button(self):
        """Test MainWindow button exists and callback resets timer and label."""
        root = tk.Tk()
        root.withdraw()
        config_mgr = ConfigManager()
        audio_mgr = AudioManager()

        window = MainWindow(
            root=root,
            timer_service=self.timer,
            config_manager=config_mgr,
            audio_manager=audio_mgr,
            on_test_break=lambda d: None
        )

        # Check button existence
        self.assertTrue(hasattr(window, "btn_reset"))
        self.assertEqual(window.btn_reset.cget("text"), "🔄 最初から数え直す")

        # Simulate state at 14:00
        self.timer.remaining_seconds = 840
        window.update_tick(840, 1200, TimerState.WORKING)
        self.assertEqual(window.countdown_label.cget("text"), "14:00")

        # Click reset button
        window._on_reset_clicked()

        # Check countdown label is reset to 20:00
        self.assertEqual(window.countdown_label.cget("text"), "20:00")
        self.assertEqual(self.timer.remaining_seconds, 1200)

        root.destroy()


if __name__ == "__main__":
    unittest.main()

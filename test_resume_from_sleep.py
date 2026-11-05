import time
import unittest
from app.config import AppConfig
from app.timer_service import TimerService, TimerState
from app.win32 import get_system_idle_seconds


class TestResumeFromSleep(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(
            work_duration_seconds=1200,   # 20 min
            break_duration_seconds=20,
            reset_on_resume=True,
            sleep_threshold_seconds=1.0,   # Small threshold for test
            idle_reset_enabled=True,
            idle_reset_duration_seconds=2
        )
        self.timer = TimerService(self.config)

    def test_reset_work_timer_directly(self):
        """Test reset_work_timer resets target time and state."""
        self.timer.state = TimerState.BREAKING
        self.timer.target_time = time.time() - 100
        self.timer.remaining_seconds = 0

        closed_prompt = []
        closed_break = []
        self.timer.on_break_prompt_close_callbacks.append(lambda: closed_prompt.append(True))
        self.timer.on_break_end_callbacks.append(lambda comp: closed_break.append(comp))

        self.timer.reset_work_timer("スリープ復帰テスト")

        self.assertEqual(self.timer.state, TimerState.WORKING)
        self.assertEqual(self.timer.current_total_seconds, 1200)
        self.assertGreater(self.timer.target_time, time.time())
        self.assertEqual(len(closed_break), 1)
        self.assertTrue(closed_break[0])

    def test_sleep_detection_in_loop(self):
        """Test that loop detects delay simulating sleep and resets work timer."""
        closed_break = []
        self.timer.on_break_end_callbacks.append(lambda comp: closed_break.append(comp))

        # Start timer service
        self.timer.start()
        time.sleep(0.3)

        # Force state to BREAKING and target_time in past (simulating expired break during sleep)
        with self.timer._lock:
            self.timer.state = TimerState.BREAKING
            self.timer.target_time = time.time() - 50
            self.timer.remaining_seconds = 0

        # Simulate sleep gap (longer than sleep_threshold_seconds)
        time.sleep(1.2)

        # Check state: should be reset to WORKING with ~1200 seconds remaining
        with self.timer._lock:
            state = self.timer.state
            rem = self.timer.remaining_seconds

        self.timer.stop()

        self.assertEqual(state, TimerState.WORKING)
        self.assertGreater(rem, 1190)

    def test_win32_idle_seconds(self):
        """Test get_system_idle_seconds returns a non-negative float."""
        idle = get_system_idle_seconds()
        self.assertIsInstance(idle, float)
        self.assertGreaterEqual(idle, 0.0)


if __name__ == "__main__":
    unittest.main()

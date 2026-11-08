import unittest
from unittest.mock import patch, MagicMock

from main import BreakTimerApp


class TestSmartMediaPause(unittest.TestCase):
    def setUp(self):
        self.patcher_tk = patch("main.tk.Tk")
        self.mock_tk = self.patcher_tk.start()
        self.mock_root = MagicMock()
        self.mock_tk.return_value = self.mock_root

        # Safely execute thread-safe dispatch (ms == 0), avoid recurring timer loops (ms > 0)
        def _safe_after(ms, func=None, *args):
            if ms == 0 and callable(func):
                func(*args)
            return "timer_id"

        self.mock_root.after.side_effect = _safe_after

    def tearDown(self):
        self.patcher_tk.stop()

    @patch("main.BreakOverlay")
    @patch("main.AudioManager")
    @patch("main.send_media_play_pause")
    @patch("main.is_audio_active")
    @patch("main.TrayManager")
    @patch("main.MainWindow")
    def test_no_media_pause_when_audio_not_playing(self, mock_mw, mock_tray, mock_audio_active, mock_send_key, mock_audio_mgr, mock_overlay):
        """When audio/video is NOT playing, do NOT send play/pause key on break start."""
        mock_audio_active.return_value = False

        app = BreakTimerApp()
        app.config.auto_pause_media = True

        # Trigger break start
        app._on_break_start()

        # Assert key was NOT sent
        mock_send_key.assert_not_called()
        self.assertFalse(app._media_paused_by_break)

    @patch("main.BreakOverlay")
    @patch("main.AudioManager")
    @patch("main.send_media_play_pause")
    @patch("main.is_audio_active")
    @patch("main.TrayManager")
    @patch("main.MainWindow")
    def test_media_pause_when_audio_playing(self, mock_mw, mock_tray, mock_audio_active, mock_send_key, mock_audio_mgr, mock_overlay):
        """When audio/video IS playing, send play/pause key and remember state."""
        mock_audio_active.return_value = True

        app = BreakTimerApp()
        app.config.auto_pause_media = True

        # Trigger break start
        app._on_break_start()

        # Assert key was sent
        mock_send_key.assert_called_once()
        self.assertTrue(app._media_paused_by_break)

    @patch("main.BreakOverlay")
    @patch("main.AudioManager")
    @patch("main.send_media_play_pause")
    @patch("main.is_audio_active")
    @patch("main.TrayManager")
    @patch("main.MainWindow")
    def test_auto_resume_only_if_paused_by_break(self, mock_mw, mock_tray, mock_audio_active, mock_send_key, mock_audio_mgr, mock_overlay):
        """Break end should only resume media if it was actually paused by break start."""
        mock_audio_active.return_value = False

        app = BreakTimerApp()
        app.config.auto_pause_media = True
        app.config.auto_resume_media = True

        # 1. Break start when nothing playing
        app._on_break_start()
        mock_send_key.assert_not_called()

        # 2. Break end
        app._on_break_end(completed=True)
        # Should still NOT send key!
        mock_send_key.assert_not_called()


if __name__ == "__main__":
    unittest.main()

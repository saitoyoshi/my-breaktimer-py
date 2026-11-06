"""
Core Timer Service for BreakTimer Ultra.
Uses wall-clock timestamps (time.time()) to guarantee rock-solid accuracy.
Implements BreakTimer's original 2-phase break workflow:
1. WORKING: Working time countdown (e.g. 20 min)
2. PROMPTING: Notification prompt with grace period (e.g. 60s) allowing user to Start, Snooze, or Skip
3. BREAKING: Actual break execution (e.g. 20s circular countdown overlay)
"""

import collections
import datetime
import threading
import time
from enum import Enum, auto
from typing import Callable, List, Optional
from app.config import AppConfig

try:
    from app.win32 import get_system_idle_seconds, is_audio_playing
except ImportError:
    def get_system_idle_seconds() -> float:
        return 0.0
    def is_audio_playing() -> bool:
        return False


class TimerState(Enum):
    WORKING = auto()
    PROMPTING = auto()
    BREAKING = auto()
    PAUSED = auto()


class TimerService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.state = TimerState.WORKING
        self.current_total_seconds = config.work_duration_seconds
        
        # Wall-clock tracking
        self.target_time: float = time.time() + self.current_total_seconds
        self.remaining_seconds: int = self.current_total_seconds
        self._paused_remaining: int = self.current_total_seconds

        self.last_break_time: Optional[float] = None
        self.event_logs: collections.deque = collections.deque(maxlen=50)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Callbacks
        self.on_tick_callbacks: List[Callable[[int, int, TimerState], None]] = []
        self.on_break_prompt_callbacks: List[Callable[[], None]] = []
        self.on_break_prompt_close_callbacks: List[Callable[[], None]] = []
        self.on_break_start_callbacks: List[Callable[[], None]] = []
        self.on_break_end_callbacks: List[Callable[[bool], None]] = []
        self.on_state_change_callbacks: List[Callable[[TimerState], None]] = []
        self.on_log_callbacks: List[Callable[[str], None]] = []

        self._log(f"タイマー初期化: 作業間隔 {config.work_duration_seconds // 60}分, 休憩時間 {config.break_duration_seconds}秒, 選択通知: {'無効(即時)' if config.immediately_start_breaks else '有効(猶予60秒)'}")

    def _log(self, message: str) -> None:
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{now_str}] {message}"
        self.event_logs.append(entry)
        for cb in self.on_log_callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    def get_target_time_str(self) -> str:
        """Returns the formatted clock time of the next target event (e.g. '13:48:30')."""
        if self.state == TimerState.PAUSED:
            return "一時停止中"
        target_dt = datetime.datetime.fromtimestamp(self.target_time)
        return target_dt.strftime("%H:%M:%S")

    def get_last_break_str(self) -> str:
        if not self.last_break_time:
            return "まだありません"
        dt = datetime.datetime.fromtimestamp(self.last_break_time)
        return dt.strftime("%H:%M:%S")

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self.state = TimerState.WORKING
            self.current_total_seconds = self.config.work_duration_seconds
            self.target_time = time.time() + self.current_total_seconds
            self.remaining_seconds = self.current_total_seconds

            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

        target_str = self.get_target_time_str()
        self._log(f"作業タイマー開始 - 次の休憩予定: {target_str} (あと {self.config.work_duration_seconds // 60}分)")
        self._notify_state_change()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def pause(self) -> None:
        with self._lock:
            if self.state != TimerState.PAUSED:
                self._prev_state = self.state
                self.state = TimerState.PAUSED
                self._paused_remaining = max(1, int(round(self.target_time - time.time())))
                self.remaining_seconds = self._paused_remaining
        self._log(f"タイマー一時停止 (残り {self._paused_remaining // 60}分{self._paused_remaining % 60}秒)")
        self._notify_state_change()

    def resume(self) -> None:
        with self._lock:
            if self.state == TimerState.PAUSED:
                self.state = getattr(self, "_prev_state", TimerState.WORKING)
                self.target_time = time.time() + self._paused_remaining
                self.remaining_seconds = self._paused_remaining
        target_str = self.get_target_time_str()
        self._log(f"タイマー再開 - 次の休憩予定: {target_str}")
        self._notify_state_change()

    def trigger_break_prompt(self) -> None:
        """Trigger the pre-break notification bar allowing user to Start, Snooze, or Skip."""
        prompt_len = self.config.notification_countdown_seconds
        with self._lock:
            self.state = TimerState.PROMPTING
            self.current_total_seconds = prompt_len
            self.target_time = time.time() + prompt_len
            self.remaining_seconds = prompt_len

        self._log(f"🔔 休憩時間になりました - 選択通知を表示 (あと {prompt_len}秒で自動開始)")
        self._notify_state_change()

        for cb in self.on_break_prompt_callbacks:
            try:
                cb()
            except Exception as e:
                print(f"[Timer] Prompt callback error: {e}")

    def trigger_break_now(self, duration_seconds: Optional[int] = None) -> None:
        """Immediately trigger the full break (bypassing or concluding prompt)."""
        break_len = duration_seconds if duration_seconds is not None else self.config.break_duration_seconds
        with self._lock:
            self.state = TimerState.BREAKING
            self.current_total_seconds = break_len
            self.target_time = time.time() + break_len
            self.remaining_seconds = break_len
            self.last_break_time = time.time()

        # Close prompt notification if open
        for cb in self.on_break_prompt_close_callbacks:
            try:
                cb()
            except Exception:
                pass

        self._log(f"休憩開始! ({break_len}秒間)")
        self._notify_state_change()

        for cb in self.on_break_start_callbacks:
            try:
                cb()
            except Exception as e:
                print(f"[Timer] Callback error: {e}")

    def start_break_now(self) -> None:
        """Called when user explicitly clicks 'Start' on the notification prompt."""
        self._log("ユーザーが「開始」を選択しました")
        self.trigger_break_now()

    def skip_break(self) -> None:
        """Skip current break/prompt and restart work timer."""
        with self._lock:
            was_prompting_or_breaking = (self.state in (TimerState.BREAKING, TimerState.PROMPTING))
            self.state = TimerState.WORKING
            self.current_total_seconds = self.config.work_duration_seconds
            self.target_time = time.time() + self.current_total_seconds
            self.remaining_seconds = self.current_total_seconds

        # Close prompt if active
        for cb in self.on_break_prompt_close_callbacks:
            try:
                cb()
            except Exception:
                pass

        target_str = self.get_target_time_str()
        self._log(f"休憩をスキップ - 次の休憩: {target_str} (あと {self.config.work_duration_seconds // 60}分)")
        self._notify_state_change()

        if was_prompting_or_breaking:
            for cb in self.on_break_end_callbacks:
                try:
                    cb(False)
                except Exception as e:
                    print(f"[Timer] Callback error: {e}")

    def postpone_break(self, seconds: Optional[int] = None) -> None:
        """Snooze for the given seconds, then prompt/trigger break."""
        postpone_sec = seconds if seconds is not None else self.config.postpone_duration_seconds
        with self._lock:
            self.state = TimerState.WORKING
            self.current_total_seconds = postpone_sec
            self.target_time = time.time() + postpone_sec
            self.remaining_seconds = postpone_sec

        # Close prompt if active
        for cb in self.on_break_prompt_close_callbacks:
            try:
                cb()
            except Exception:
                pass

        target_str = self.get_target_time_str()
        snooze_min = postpone_sec // 60
        self._log(f"スヌーズ実行 ({snooze_min}分間延期) - 次の休憩予定: {target_str}")
        self._notify_state_change()

        for cb in self.on_break_end_callbacks:
            try:
                cb(False)
            except Exception as e:
                print(f"[Timer] Callback error: {e}")

    def finish_break_early(self) -> None:
        """Mark break as completed and restart work timer."""
        with self._lock:
            self.state = TimerState.WORKING
            self.current_total_seconds = self.config.work_duration_seconds
            self.target_time = time.time() + self.current_total_seconds
            self.remaining_seconds = self.current_total_seconds

        target_str = self.get_target_time_str()
        self._log(f"休憩完了 - 作業再開 (次の休憩予定: {target_str})")
        self._notify_state_change()

        for cb in self.on_break_end_callbacks:
            try:
                cb(True)
            except Exception as e:
                print(f"[Timer] Callback error: {e}")

    def update_config(self, new_config: AppConfig) -> None:
        with self._lock:
            old_work = self.config.work_duration_seconds
            self.config = new_config
            if self.state == TimerState.WORKING:
                if old_work != new_config.work_duration_seconds:
                    self.current_total_seconds = new_config.work_duration_seconds
                    self.target_time = time.time() + self.current_total_seconds
                    self.remaining_seconds = self.current_total_seconds

        target_str = self.get_target_time_str()
        self._log(f"設定更新 - 作業間隔: {new_config.work_duration_seconds // 60}分, 休憩: {new_config.break_duration_seconds}秒, 次回: {target_str}")

    def reset_work_timer(self, reason: str = "リセット") -> None:
        """
        Resets and starts a fresh work interval immediately.
        Used when resuming from sleep, returning from idle/away, or explicit user reset.
        """
        with self._lock:
            was_prompting_or_breaking = (self.state in (TimerState.BREAKING, TimerState.PROMPTING))
            self.state = TimerState.WORKING
            self.current_total_seconds = self.config.work_duration_seconds
            self.target_time = time.time() + self.current_total_seconds
            self.remaining_seconds = self.current_total_seconds

        # Close prompt notification if open
        for cb in self.on_break_prompt_close_callbacks:
            try:
                cb()
            except Exception:
                pass

        # Close break overlay if open
        if was_prompting_or_breaking:
            for cb in self.on_break_end_callbacks:
                try:
                    cb(True)
                except Exception as e:
                    print(f"[Timer] Callback error: {e}")

        target_str = self.get_target_time_str()
        self._log(f"{reason} - 作業タイマーを開始 (次回休憩予定: {target_str})")
        self._notify_state_change()

    def _loop(self) -> None:
        last_loop_time = time.time()
        was_idle = False

        while self._running:
            time.sleep(0.5)
            now = time.time()
            elapsed_loop = now - last_loop_time
            last_loop_time = now

            with self._lock:
                if self.state == TimerState.PAUSED:
                    continue

            # 1. Check for Resume from Sleep / Suspend (Gap detection)
            # Normal sleep(0.5) takes ~0.5s. If elapsed_loop is significantly longer, OS was suspended.
            if self.config.reset_on_resume and elapsed_loop >= self.config.sleep_threshold_seconds:
                self.reset_work_timer(f"スリープ復帰を検知 ({int(elapsed_loop)}秒間休止)")
                was_idle = False
                continue

            # 2. Check for Idle / Away from computer
            is_currently_idle = False
            if self.config.idle_reset_enabled:
                idle_sec = get_system_idle_seconds()
                if idle_sec >= self.config.idle_reset_duration_seconds:
                    # Input is idle, but check if sound/video is currently playing (YouTube, Netflix, etc.)
                    # If audio is playing, the user is actively watching or listening - DO NOT treat as idle!
                    audio_active = is_audio_playing()
                    if audio_active:
                        is_currently_idle = False
                        was_idle = False
                    else:
                        is_currently_idle = True
                        was_idle = True
                elif was_idle:
                    # User returned after being idle with no audio playing!
                    was_idle = False
                    self.reset_work_timer(f"離席からの復帰を検知 ({int(self.config.idle_reset_duration_seconds // 60)}分以上無操作)")
                    continue

            with self._lock:
                rem = max(0, int(round(self.target_time - now)))
                self.remaining_seconds = rem
                tot = self.current_total_seconds
                cur_state = self.state

            # Notify tick
            for cb in self.on_tick_callbacks:
                try:
                    cb(rem, tot, cur_state)
                except Exception as e:
                    print(f"[Timer] Tick callback error: {e}")

            # Don't trigger new breaks if user is currently away from computer
            if is_currently_idle and cur_state == TimerState.WORKING:
                continue

            if rem <= 0:
                if cur_state == TimerState.WORKING:
                    # Work time elapsed! Check if prompt mode is active
                    if self.config.immediately_start_breaks:
                        self.trigger_break_now()
                    else:
                        self.trigger_break_prompt()
                elif cur_state == TimerState.PROMPTING:
                    # Prompt grace period countdown expired! Automatically start full break
                    self._log("選択猶予時間が経過しました - 休憩を自動開始します")
                    self.trigger_break_now()
                elif cur_state == TimerState.BREAKING:
                    # Break completed naturally!
                    self.finish_break_early()

    def _notify_state_change(self) -> None:
        cur_state = self.state
        for cb in self.on_state_change_callbacks:
            try:
                cb(cur_state)
            except Exception as e:
                print(f"[Timer] State change callback error: {e}")

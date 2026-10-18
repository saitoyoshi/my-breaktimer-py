"""
Break Overlay Window for BreakTimer Ultra.
Features:
- Active Win32 Z-Order Enforcer (never gets buried behind fullscreens)
- Built-in Media Play/Pause control for Netflix, YouTube, media players
- "Operate Behind / Mini Mode" button to unblock screen so users can directly click Netflix controls
- Fullscreen Backdrop or Compact Floating Banner modes
"""

import math
import tkinter as tk
from typing import Optional, Callable

from app.config import AppConfig
from app.timer_service import TimerService, TimerState
from app.ui.styles import (
    BG_DARK, BG_CARD, BG_CARD_HOVER, BORDER_COLOR,
    ACCENT_CYAN, ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED, ACCENT_ORANGE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    FONT_FAMILY, FONT_TITLE, FONT_SUBTITLE, FONT_BIG_NUMBER, FONT_BUTTON
)
from app.win32 import force_window_to_top, maintain_topmost, get_virtual_screen_geometry, send_media_play_pause


class BreakOverlay:
    def __init__(self, root: tk.Tk, timer_service: TimerService, config: AppConfig,
                 on_close_callback: Optional[Callable[[], None]] = None):
        self.root = root
        self.timer_service = timer_service
        self.config = config
        self.on_close_callback = on_close_callback

        self.window: Optional[tk.Toplevel] = None
        self._topmost_timer_id: Optional[str] = None
        self._is_active = False
        self._is_mini_mode = False

        # Virtual screen metrics
        self.vx, self.vy, self.vw, self.vh = get_virtual_screen_geometry()

    def show(self) -> None:
        if self._is_active and self.window:
            self._enforce_topmost()
            return

        self._is_active = True
        self._is_mini_mode = False
        self.window = tk.Toplevel(self.root)
        self.window.title("BreakTimer - Break in Progress")
        self.window.configure(bg="#000000")

        # Borderless overlay
        self.window.overrideredirect(True)

        if self.config.display_mode == "compact":
            # Compact mode: Floating card on top-right, leaving screen clickable
            self._apply_compact_geometry()
            self._build_mini_ui()
        else:
            # Fullscreen mode: Covers whole virtual desktop with backdrop
            self._apply_fullscreen_geometry()
            self._build_fullscreen_ui()

        # Key bindings
        self.window.bind("<Escape>", lambda e: self._on_finish_clicked())
        self.window.bind("<space>", lambda e: self._on_media_toggle())
        self.window.bind("<KeyPress-s>", lambda e: self._on_snooze_clicked())
        self.window.bind("<KeyPress-k>", lambda e: self._on_skip_clicked())

        # Update geometry and apply aggressive Win32 topmost & foreground acquisition
        self.window.update_idletasks()
        self._enforce_topmost()

        # Start the continuous Z-Order enforcer loop
        self._start_topmost_enforcer()

    def _apply_fullscreen_geometry(self) -> None:
        self.vx, self.vy, self.vw, self.vh = get_virtual_screen_geometry()
        self.window.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")
        opacity = max(0.2, min(1.0, self.config.backdrop_opacity))
        self.window.wm_attributes("-alpha", opacity)
        self.window.wm_attributes("-topmost", True)

    def _apply_compact_geometry(self) -> None:
        self.vx, self.vy, self.vw, self.vh = get_virtual_screen_geometry()
        card_w, card_h = 360, 110
        pos_x = self.vx + self.vw - card_w - 30
        pos_y = self.vy + 30
        self.window.geometry(f"{card_w}x{card_h}+{pos_x}+{pos_y}")
        self.window.wm_attributes("-alpha", 0.95)
        self.window.wm_attributes("-topmost", True)

    def _build_fullscreen_ui(self) -> None:
        """Builds the full backdrop + central card UI."""
        self._clear_ui()
        self._is_mini_mode = False
        self._apply_fullscreen_geometry()

        # Full backdrop outer frame
        self.outer_frame = tk.Frame(self.window, bg="#000000")
        self.outer_frame.pack(fill=tk.BOTH, expand=True)

        # Center card
        card_w, card_h = 580, 520
        self.card = tk.Frame(
            self.outer_frame,
            bg=BG_CARD,
            highlightbackground=BORDER_COLOR,
            highlightthickness=2,
            padx=28,
            pady=24
        )
        self.card.place(relx=0.5, rely=0.5, anchor=tk.CENTER, width=card_w, height=card_h)

        # Header title
        title_label = tk.Label(
            self.card,
            text="👀 " + self.config.break_message,
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_CARD
        )
        title_label.pack(pady=(2, 4))

        # Subtitle message
        sub_label = tk.Label(
            self.card,
            text=self.config.break_submessage,
            font=FONT_SUBTITLE,
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            wraplength=500,
            justify=tk.CENTER
        )
        sub_label.pack(pady=(0, 10))

        # Netflix / Media control bar (Highlighted banner)
        media_bar = tk.Frame(self.card, bg="#1c2128", highlightbackground="#30363d", highlightthickness=1, padx=12, pady=6)
        media_bar.pack(fill=tk.X, pady=(0, 10))

        media_hint = tk.Label(
            media_bar,
            text="🎬 Netflix・動画の操作:",
            font=(FONT_FAMILY, 9, "bold"),
            fg=ACCENT_CYAN,
            bg="#1c2128"
        )
        media_hint.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_media = tk.Button(
            media_bar,
            text="⏯ 動画を一時停止 / 再開 (Space)",
            font=(FONT_FAMILY, 9, "bold"),
            fg=TEXT_PRIMARY,
            bg="#21262d",
            activebackground="#30363d",
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._on_media_toggle
        )
        self.btn_media.pack(side=tk.LEFT, padx=4)

        self.btn_operate_behind = tk.Button(
            media_bar,
            text="👁 背後を操作する (ミニ表示)",
            font=(FONT_FAMILY, 9, "bold"),
            fg="#ffffff",
            bg="#1f6feb",
            activebackground="#388bfd",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._switch_to_mini_mode
        )
        self.btn_operate_behind.pack(side=tk.RIGHT, padx=4)

        # Circular progress canvas
        self.canvas_size = 170
        self.canvas = tk.Canvas(
            self.card,
            width=self.canvas_size,
            height=self.canvas_size,
            bg=BG_CARD,
            highlightthickness=0
        )
        self.canvas.pack(pady=4)

        # Draw initial circle
        self._draw_progress(
            self.timer_service.remaining_seconds,
            self.timer_service.current_total_seconds
        )

        # Media status feedback label
        self.media_status_lbl = tk.Label(
            self.card,
            text="",
            font=(FONT_FAMILY, 9),
            fg=ACCENT_GREEN,
            bg=BG_CARD
        )
        self.media_status_lbl.pack(pady=(2, 6))

        # Button container
        btn_frame = tk.Frame(self.card, bg=BG_CARD)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 4))

        # Snooze button (+5m)
        snooze_min = max(1, self.config.postpone_duration_seconds // 60)
        self.btn_snooze = tk.Button(
            btn_frame,
            text=f"⏰ スヌーズ (+{snooze_min}分)",
            font=FONT_BUTTON,
            fg=TEXT_PRIMARY,
            bg="#21262d",
            activebackground="#30363d",
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._on_snooze_clicked
        )
        self.btn_snooze.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)

        # Skip button
        self.btn_skip = tk.Button(
            btn_frame,
            text="スキップ (K)",
            font=FONT_BUTTON,
            fg=TEXT_SECONDARY,
            bg="#161b22",
            activebackground="#21262d",
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._on_skip_clicked
        )
        self.btn_skip.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)

        # Finish early button
        self.btn_finish = tk.Button(
            btn_frame,
            text="今すぐ終了 (Esc)",
            font=FONT_BUTTON,
            fg="#ffffff",
            bg=ACCENT_BLUE,
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._on_finish_clicked
        )
        self.btn_finish.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)

        # Hint text
        hint_label = tk.Label(
            self.card,
            text="[Space] 動画一時停止/再開  |  [Esc] 終了  |  [S] スヌーズ",
            font=(FONT_FAMILY, 9),
            fg=TEXT_MUTED,
            bg=BG_CARD
        )
        hint_label.pack(side=tk.BOTTOM, pady=(4, 0))

    def _build_mini_ui(self) -> None:
        """
        Builds the compact mini banner on top-right of the screen.
        Leaves Netflix and other applications completely unobstructed and clickable!
        """
        self._clear_ui()
        self._is_mini_mode = True
        self._apply_compact_geometry()

        self.mini_frame = tk.Frame(
            self.window,
            bg=BG_CARD,
            highlightbackground=ACCENT_CYAN,
            highlightthickness=2,
            padx=12,
            pady=8
        )
        self.mini_frame.pack(fill=tk.BOTH, expand=True)

        top_row = tk.Frame(self.mini_frame, bg=BG_CARD)
        top_row.pack(fill=tk.X)

        self.mini_label = tk.Label(
            top_row,
            text=f"👀 休憩中: 残り {self.timer_service.remaining_seconds}秒",
            font=(FONT_FAMILY, 11, "bold"),
            fg=ACCENT_CYAN,
            bg=BG_CARD
        )
        self.mini_label.pack(side=tk.LEFT)

        btn_restore = tk.Button(
            top_row,
            text="↩ 全画面に戻す",
            font=(FONT_FAMILY, 8, "bold"),
            fg=TEXT_PRIMARY,
            bg="#21262d",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._switch_to_fullscreen_mode
        )
        btn_restore.pack(side=tk.RIGHT)

        # Control buttons row
        btn_row = tk.Frame(self.mini_frame, bg=BG_CARD)
        btn_row.pack(fill=tk.X, pady=(6, 0))

        btn_mini_media = tk.Button(
            btn_row,
            text="⏯ 動画停止/再開",
            font=(FONT_FAMILY, 8),
            fg=TEXT_PRIMARY,
            bg="#21262d",
            relief=tk.FLAT,
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._on_media_toggle
        )
        btn_mini_media.pack(side=tk.LEFT, padx=(0, 4))

        btn_mini_skip = tk.Button(
            btn_row,
            text="スキップ",
            font=(FONT_FAMILY, 8),
            fg=TEXT_SECONDARY,
            bg="#161b22",
            relief=tk.FLAT,
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._on_skip_clicked
        )
        btn_mini_skip.pack(side=tk.LEFT, padx=4)

        btn_mini_done = tk.Button(
            btn_row,
            text="今すぐ終了 (Done)",
            font=(FONT_FAMILY, 8, "bold"),
            fg="#ffffff",
            bg=ACCENT_BLUE,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._on_finish_clicked
        )
        btn_mini_done.pack(side=tk.RIGHT)

    def _clear_ui(self) -> None:
        if self.window:
            for child in self.window.winfo_children():
                child.destroy()
        self.canvas = None

    def _switch_to_mini_mode(self) -> None:
        """Switches to compact mini badge so the user can click Netflix directly."""
        self._build_mini_ui()
        self.window.update_idletasks()
        self._enforce_topmost()

    def _switch_to_fullscreen_mode(self) -> None:
        """Restores to full screen overlay."""
        self._build_fullscreen_ui()
        self.window.update_idletasks()
        self._enforce_topmost()

    def _on_media_toggle(self) -> None:
        """Sends the media play/pause key to stop or resume Netflix."""
        try:
            send_media_play_pause()
            if hasattr(self, "media_status_lbl") and self.media_status_lbl and self.media_status_lbl.winfo_exists():
                self.media_status_lbl.config(text="✔ 動画の一時停止/再開キーを送信しました")
                self.root.after(2500, lambda: self._clear_media_status())
        except Exception as e:
            print(f"[Overlay] Media toggle error: {e}")

    def _clear_media_status(self) -> None:
        if hasattr(self, "media_status_lbl") and self.media_status_lbl and self.media_status_lbl.winfo_exists():
            self.media_status_lbl.config(text="")

    def _draw_progress(self, remaining: int, total: int) -> None:
        """Draws the smooth circular ring and remaining countdown seconds."""
        if not hasattr(self, "canvas") or not self.canvas:
            return
        self.canvas.delete("all")

        center = self.canvas_size / 2
        radius = 70
        width = 10

        # 1. Background ring
        x0, y0 = center - radius, center - radius
        x1, y1 = center + radius, center + radius
        self.canvas.create_oval(
            x0, y0, x1, y1,
            outline="#21262d",
            width=width
        )

        # 2. Active progress arc
        fraction = max(0.0, min(1.0, remaining / max(1, total)))
        extent_angle = - (fraction * 360)
        start_angle = 90

        if extent_angle != 0:
            self.canvas.create_arc(
                x0, y0, x1, y1,
                start=start_angle,
                extent=extent_angle,
                outline=ACCENT_CYAN,
                width=width,
                style=tk.ARC
            )

        # 3. Big countdown text in the center
        self.canvas.create_text(
            center,
            center - 8,
            text=str(max(0, remaining)),
            font=(FONT_FAMILY, 34, "bold"),
            fill=TEXT_PRIMARY
        )

        # 4. Seconds label under the number
        self.canvas.create_text(
            center,
            center + 26,
            text="SECONDS",
            font=(FONT_FAMILY, 8, "bold"),
            fill=TEXT_SECONDARY
        )

    def update_tick(self, remaining: int, total: int) -> None:
        """Called by timer service on each tick."""
        if not self._is_active or not self.window:
            return

        if self._is_mini_mode:
            if hasattr(self, "mini_label") and self.mini_label and self.mini_label.winfo_exists():
                self.mini_label.config(text=f"👀 休憩中: 残り {remaining}秒")
        else:
            self._draw_progress(remaining, total)

    def _enforce_topmost(self) -> None:
        """Forcefully grabs foreground and applies topmost Win32 positioning."""
        if self.window and self.window.winfo_exists():
            try:
                hwnd = self.window.winfo_id()
                force_window_to_top(hwnd, take_focus=True)
            except Exception as e:
                print(f"[Overlay] Error enforcing topmost: {e}")

    def _start_topmost_enforcer(self) -> None:
        if not self._is_active or not self.window:
            return

        try:
            if self.window.winfo_exists():
                hwnd = self.window.winfo_id()
                maintain_topmost(hwnd)
        except Exception as e:
            print(f"[Overlay] Maintain topmost error: {e}")

        interval = max(50, self.config.topmost_enforce_interval_ms)
        self._topmost_timer_id = self.root.after(interval, self._start_topmost_enforcer)

    def _on_snooze_clicked(self) -> None:
        self.close()
        self.timer_service.postpone_break()

    def _on_skip_clicked(self) -> None:
        self.close()
        self.timer_service.skip_break()

    def _on_finish_clicked(self) -> None:
        self.close()
        self.timer_service.finish_break_early()

    def close(self) -> None:
        if not self._is_active:
            return
        self._is_active = False

        if self._topmost_timer_id:
            try:
                self.root.after_cancel(self._topmost_timer_id)
            except Exception:
                pass
            self._topmost_timer_id = None

        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None

        if self.on_close_callback:
            self.on_close_callback()

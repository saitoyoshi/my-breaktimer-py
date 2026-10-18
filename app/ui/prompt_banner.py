"""
Break Notification Prompt Banner for BreakTimer Ultra.
Faithfully recreates BreakTimer's original pre-break notification bar:
Floats at the top of the screen (height ~85px) without covering or blocking the screen,
allowing the user to choose 'Start Now', 'Snooze', or 'Skip' before the full break begins.
"""

import tkinter as tk
from typing import Optional, Callable

from app.config import AppConfig
from app.timer_service import TimerService, TimerState
from app.ui.styles import (
    BG_DARK, BG_CARD, BG_CARD_HOVER, BORDER_COLOR,
    ACCENT_CYAN, ACCENT_BLUE, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    FONT_FAMILY, FONT_BUTTON, FONT_MEDIUM
)
from app.win32 import force_window_to_top, maintain_topmost, get_virtual_screen_geometry


class BreakPromptBanner:
    def __init__(self, root: tk.Tk, timer_service: TimerService, config: AppConfig,
                 on_close_callback: Optional[Callable[[], None]] = None):
        self.root = root
        self.timer_service = timer_service
        self.config = config
        self.on_close_callback = on_close_callback

        self.window: Optional[tk.Toplevel] = None
        self._topmost_timer_id: Optional[str] = None
        self._is_active = False

    def show(self) -> None:
        if self._is_active and self.window:
            self._enforce_topmost()
            return

        self._is_active = True
        self.window = tk.Toplevel(self.root)
        self.window.title("BreakTimer - Ready for break?")
        self.window.configure(bg="#000000")

        # Top-center floating banner (does NOT block the screen!)
        card_w, card_h = 560, 85
        vx, vy, vw, vh = get_virtual_screen_geometry()
        pos_x = vx + (vw - card_w) // 2
        pos_y = vy + 40

        self.window.geometry(f"{card_w}x{card_h}+{pos_x}+{pos_y}")
        self.window.overrideredirect(True)
        self.window.wm_attributes("-alpha", 0.96)
        self.window.wm_attributes("-topmost", True)

        self._build_ui()

        # Keyboard shortcuts
        self.window.bind("<Return>", lambda e: self._on_start_clicked())
        self.window.bind("<KeyPress-s>", lambda e: self._on_snooze_clicked())
        self.window.bind("<KeyPress-k>", lambda e: self._on_skip_clicked())
        self.window.bind("<Escape>", lambda e: self._on_snooze_clicked())

        self.window.update_idletasks()
        self._enforce_topmost()
        self._start_topmost_enforcer()

    def _build_ui(self) -> None:
        if not self.window:
            return

        # Main container
        self.container = tk.Frame(
            self.window,
            bg=BG_CARD,
            highlightbackground=ACCENT_CYAN,
            highlightthickness=2,
            padx=16,
            pady=8
        )
        self.container.pack(fill=tk.BOTH, expand=True)

        # Upper row: Title + Buttons
        top_row = tk.Frame(self.container, bg=BG_CARD)
        top_row.pack(fill=tk.BOTH, expand=True)

        # Left: Title and countdown label
        text_frame = tk.Frame(top_row, bg=BG_CARD)
        text_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, anchor=tk.W)

        title_lbl = tk.Label(
            text_frame,
            text="☕ 休憩の時間です (Time for a break)",
            font=(FONT_FAMILY, 11, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD
        )
        title_lbl.pack(anchor=tk.W)

        self.countdown_lbl = tk.Label(
            text_frame,
            text=f"準備ができたら開始してください (あと {self.timer_service.remaining_seconds}秒で自動開始)",
            font=(FONT_FAMILY, 9),
            fg=ACCENT_CYAN,
            bg=BG_CARD
        )
        self.countdown_lbl.pack(anchor=tk.W, pady=(2, 0))

        # Right: Action Buttons
        btn_frame = tk.Frame(top_row, bg=BG_CARD)
        btn_frame.pack(side=tk.RIGHT, padx=(10, 0))

        # Start button
        self.btn_start = tk.Button(
            btn_frame,
            text="今すぐ開始 (Enter)",
            font=(FONT_FAMILY, 9, "bold"),
            fg="#ffffff",
            bg=ACCENT_BLUE,
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._on_start_clicked
        )
        self.btn_start.pack(side=tk.LEFT, padx=3)

        # Snooze button
        snooze_min = max(1, self.config.postpone_duration_seconds // 60)
        self.btn_snooze = tk.Button(
            btn_frame,
            text=f"⏰ スヌーズ (+{snooze_min}分)",
            font=(FONT_FAMILY, 9),
            fg=TEXT_PRIMARY,
            bg="#21262d",
            activebackground="#30363d",
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self._on_snooze_clicked
        )
        self.btn_snooze.pack(side=tk.LEFT, padx=3)

        # Skip button
        self.btn_skip = tk.Button(
            btn_frame,
            text="スキップ",
            font=(FONT_FAMILY, 9),
            fg=TEXT_SECONDARY,
            bg="#161b22",
            activebackground="#21262d",
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=6,
            pady=4,
            cursor="hand2",
            command=self._on_skip_clicked
        )
        self.btn_skip.pack(side=tk.LEFT, padx=3)

        # Bottom row: Slim progress bar
        self.pbar_canvas = tk.Canvas(
            self.container,
            height=4,
            bg="#21262d",
            highlightthickness=0
        )
        self.pbar_canvas.pack(fill=tk.X, side=tk.BOTTOM, pady=(6, 0))

    def update_tick(self, remaining: int, total: int) -> None:
        if not self._is_active or not self.window:
            return

        if hasattr(self, "countdown_lbl") and self.countdown_lbl.winfo_exists():
            self.countdown_lbl.config(
                text=f"準備ができたら開始してください (あと {remaining}秒で自動開始)"
            )

        # Update slim progress bar
        if hasattr(self, "pbar_canvas") and self.pbar_canvas.winfo_exists():
            self.pbar_canvas.delete("all")
            w = self.pbar_canvas.winfo_width()
            if w <= 1:
                w = 520
            fraction = max(0.0, min(1.0, 1.0 - (remaining / max(1, total))))
            fill_w = int(w * fraction)
            if fill_w > 0:
                self.pbar_canvas.create_rectangle(
                    0, 0, fill_w, 4,
                    fill=ACCENT_CYAN,
                    outline=""
                )

    def _on_start_clicked(self) -> None:
        self.close()
        self.timer_service.start_break_now()

    def _on_snooze_clicked(self) -> None:
        self.close()
        self.timer_service.postpone_break()

    def _on_skip_clicked(self) -> None:
        self.close()
        self.timer_service.skip_break()

    def _enforce_topmost(self) -> None:
        if self.window and self.window.winfo_exists():
            try:
                hwnd = self.window.winfo_id()
                force_window_to_top(hwnd, take_focus=False)
            except Exception as e:
                print(f"[PromptBanner] Topmost error: {e}")

    def _start_topmost_enforcer(self) -> None:
        if not self._is_active or not self.window:
            return

        try:
            if self.window.winfo_exists():
                hwnd = self.window.winfo_id()
                maintain_topmost(hwnd)
        except Exception as e:
            print(f"[PromptBanner] Maintain error: {e}")

        interval = max(50, self.config.topmost_enforce_interval_ms)
        self._topmost_timer_id = self.root.after(interval, self._start_topmost_enforcer)

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

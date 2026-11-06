"""
Main Dashboard & Settings Window for BreakTimer Ultra.
Features real-time countdown, progress visualization, settings sliders,
sound previews, 2-phase break workflow controls (pre-break prompt banner),
a 15-second prompt test button, a 5-second fullscreen test button,
target clock timestamps, and a live event log to transparently track break intervals.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable

from app.config import ConfigManager, AppConfig
from app.timer_service import TimerService, TimerState
from app.audio import AudioManager
from app.ui.styles import (
    BG_DARK, BG_CARD, BG_CARD_HOVER, BORDER_COLOR,
    ACCENT_CYAN, ACCENT_BLUE, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    FONT_FAMILY, FONT_TITLE, FONT_SUBTITLE, FONT_BIG_NUMBER, FONT_BUTTON, FONT_MEDIUM
)

ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons", "app_icon.png")


class MainWindow:
    def __init__(self, root: tk.Tk, timer_service: TimerService, config_manager: ConfigManager,
                 audio_manager: AudioManager, on_test_break: Callable[[int], None],
                 on_test_prompt: Optional[Callable[[int], None]] = None):
        self.root = root
        self.timer_service = timer_service
        self.config_manager = config_manager
        self.config = config_manager.config
        self.audio_manager = audio_manager
        self.on_test_break = on_test_break
        self.on_test_prompt = on_test_prompt

        self.root.title("BreakTimer Ultra — 20-20-20 ルール休憩タイマー")
        self.root.geometry("680x880")
        self.root.minsize(620, 780)
        self.root.configure(bg=BG_DARK)

        # Set application icon if exists
        if os.path.exists(ICON_PATH):
            try:
                icon_img = tk.PhotoImage(file=ICON_PATH)
                self.root.iconphoto(True, icon_img)
            except Exception:
                pass

        # Intercept window close to minimize to system tray
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self._build_ui()

    def _build_ui(self) -> None:
        main_frame = tk.Frame(self.root, bg=BG_DARK, padx=22, pady=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Header
        header_frame = tk.Frame(main_frame, bg=BG_DARK)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_lbl = tk.Label(
            header_frame,
            text="⏱ BreakTimer Ultra",
            font=(FONT_FAMILY, 20, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_DARK
        )
        title_lbl.pack(anchor=tk.W)

        sub_lbl = tk.Label(
            header_frame,
            text="全画面ゲーム・動画（YouTube/ブラウザ全画面）でも隠れない 20-20-20 ルールタイマー",
            font=FONT_SUBTITLE,
            fg=ACCENT_CYAN,
            bg=BG_DARK
        )
        sub_lbl.pack(anchor=tk.W, pady=(2, 0))

        # 2. Status & Countdown Card
        self.status_card = tk.Frame(
            main_frame,
            bg=BG_CARD,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=18,
            pady=12
        )
        self.status_card.pack(fill=tk.X, pady=(0, 10))

        status_top = tk.Frame(self.status_card, bg=BG_CARD)
        status_top.pack(fill=tk.X)

        self.status_badge = tk.Label(
            status_top,
            text="🟢 作業中 (Working)",
            font=(FONT_FAMILY, 10, "bold"),
            fg=ACCENT_GREEN,
            bg="#1f3629",
            padx=10,
            pady=4
        )
        self.status_badge.pack(side=tk.LEFT)

        self.next_label = tk.Label(
            status_top,
            text="次の休憩まで",
            font=FONT_MEDIUM,
            fg=TEXT_SECONDARY,
            bg=BG_CARD
        )
        self.next_label.pack(side=tk.RIGHT)

        # Large countdown
        self.countdown_label = tk.Label(
            self.status_card,
            text="20:00",
            font=(FONT_FAMILY, 36, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD
        )
        self.countdown_label.pack(pady=(4, 2))

        # Target clock time indicator (Transparent timestamping)
        self.target_time_label = tk.Label(
            self.status_card,
            text=f"次回休憩予定時刻: {self.timer_service.get_target_time_str()}  |  前回: {self.timer_service.get_last_break_str()}",
            font=(FONT_FAMILY, 9),
            fg=ACCENT_CYAN,
            bg=BG_CARD
        )
        self.target_time_label.pack(pady=(0, 4))

        # Progress bar (custom canvas)
        self.pbar_canvas = tk.Canvas(
            self.status_card,
            height=8,
            bg="#21262d",
            highlightthickness=0
        )
        self.pbar_canvas.pack(fill=tk.X, pady=(2, 10))

        # Quick action buttons row
        btn_row = tk.Frame(self.status_card, bg=BG_CARD)
        btn_row.pack(fill=tk.X)

        self.btn_take_break = tk.Button(
            btn_row,
            text="☕ 今すぐ休憩",
            font=FONT_BUTTON,
            fg="#ffffff",
            bg=ACCENT_BLUE,
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=6,
            cursor="hand2",
            command=self._on_take_break_clicked
        )
        self.btn_take_break.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.btn_test_prompt = tk.Button(
            btn_row,
            text="🔔 通知バーをテスト",
            font=FONT_BUTTON,
            fg=TEXT_PRIMARY,
            bg="#1f6feb",
            activebackground="#388bfd",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=6,
            cursor="hand2",
            command=self._on_test_prompt_clicked
        )
        self.btn_test_prompt.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)

        self.btn_test_break = tk.Button(
            btn_row,
            text="⚡ 全画面テスト (5秒)",
            font=FONT_BUTTON,
            fg=TEXT_PRIMARY,
            bg="#238636",
            activebackground="#2ea043",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=6,
            cursor="hand2",
            command=self._on_test_break_clicked
        )
        self.btn_test_break.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)

        self.btn_pause = tk.Button(
            btn_row,
            text="⏸ 一時停止",
            font=FONT_BUTTON,
            fg=TEXT_PRIMARY,
            bg="#21262d",
            activebackground="#30363d",
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=8,
            pady=6,
            cursor="hand2",
            command=self._on_pause_clicked
        )
        self.btn_pause.pack(side=tk.LEFT, padx=(4, 0), expand=True, fill=tk.X)

        # 3. Settings Card
        settings_card = tk.Frame(
            main_frame,
            bg=BG_CARD,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=18,
            pady=12
        )
        settings_card.pack(fill=tk.X, pady=(0, 10))

        set_title = tk.Label(
            settings_card,
            text="⚙ 設定 (Settings)",
            font=(FONT_FAMILY, 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD
        )
        set_title.pack(anchor=tk.W, pady=(0, 6))

        # 3.1 Work duration
        self.work_var = tk.IntVar(value=max(1, self.config.work_duration_seconds // 60))
        self._create_slider_row(
            settings_card,
            label="作業間隔 (Work Frequency):",
            unit="分",
            variable=self.work_var,
            from_=1, to_=60
        )

        # 3.2 Break duration
        self.break_var = tk.IntVar(value=self.config.break_duration_seconds)
        self._create_slider_row(
            settings_card,
            label="休憩時間 (Break Length):",
            unit="秒",
            variable=self.break_var,
            from_=5, to_=180
        )

        # 3.3 Postpone duration
        self.postpone_var = tk.IntVar(value=max(1, self.config.postpone_duration_seconds // 60))
        self._create_slider_row(
            settings_card,
            label="スヌーズ時間 (Snooze Length):",
            unit="分",
            variable=self.postpone_var,
            from_=1, to_=15
        )

        # 3.4 Pre-Break Prompt Settings (BreakTimer 2-phase workflow)
        prompt_frame = tk.Frame(settings_card, bg=BG_CARD)
        prompt_frame.pack(fill=tk.X, pady=(4, 2))

        self.immediately_var = tk.BooleanVar(value=self.config.immediately_start_breaks)
        chk_immediately = tk.Checkbutton(
            prompt_frame,
            text="休憩時間になったら通知バーを出さずに即座に全画面を開始する (オフ推奨: BreakTimer標準仕様)",
            variable=self.immediately_var,
            font=FONT_MEDIUM,
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            selectcolor=BG_DARK,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY
        )
        chk_immediately.pack(side=tk.LEFT)

        # 3.5 Prompt Countdown seconds
        self.prompt_sec_var = tk.IntVar(value=self.config.notification_countdown_seconds)
        self._create_slider_row(
            settings_card,
            label="通知バーの自動開始カウントダウン:",
            unit="秒",
            variable=self.prompt_sec_var,
            from_=10, to_=120
        )

        # 3.6 Backdrop Opacity
        self.opacity_var = tk.IntVar(value=int(self.config.backdrop_opacity * 100))
        self._create_slider_row(
            settings_card,
            label="全画面暗度 (Backdrop Opacity):",
            unit="%",
            variable=self.opacity_var,
            from_=30, to_=95
        )

        # 3.7 Netflix & Media Pause Row
        media_frame = tk.Frame(settings_card, bg=BG_CARD)
        media_frame.pack(fill=tk.X, pady=(4, 2))

        self.auto_pause_var = tk.BooleanVar(value=self.config.auto_pause_media)
        chk_pause = tk.Checkbutton(
            media_frame,
            text="🎬 休憩開始時に動画/音楽(Netflix・YouTube等)を自動一時停止",
            variable=self.auto_pause_var,
            font=FONT_MEDIUM,
            fg=ACCENT_CYAN,
            bg=BG_CARD,
            selectcolor=BG_DARK,
            activebackground=BG_CARD,
            activeforeground=ACCENT_CYAN
        )
        chk_pause.pack(side=tk.LEFT)

        # 3.8 Idle Detection Row (Smart away detection with audio playback protection)
        idle_frame = tk.Frame(settings_card, bg=BG_CARD)
        idle_frame.pack(fill=tk.X, pady=(4, 2))

        self.idle_reset_var = tk.BooleanVar(value=self.config.idle_reset_enabled)
        chk_idle = tk.Checkbutton(
            idle_frame,
            text="🚶 5分以上離席(完全無操作・無音)した場合に復帰時タイマーをリセット (動画再生中は保護)",
            variable=self.idle_reset_var,
            font=FONT_MEDIUM,
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            selectcolor=BG_DARK,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY
        )
        chk_idle.pack(side=tk.LEFT)

        # 3.9 Display Mode Row
        disp_frame = tk.Frame(settings_card, bg=BG_CARD)
        disp_frame.pack(fill=tk.X, pady=(4, 4))

        lbl_disp = tk.Label(disp_frame, text="表示スタイル:", font=FONT_MEDIUM, fg=TEXT_SECONDARY, bg=BG_CARD)
        lbl_disp.pack(side=tk.LEFT, padx=(0, 8))

        self.display_mode_var = tk.StringVar(value=self.config.display_mode)
        disp_modes = [("全画面オーバーレイ (推奨)", "fullscreen"), ("コンパクト浮動カード (背後クリック優先)", "compact")]
        for text, val in disp_modes:
            rb = tk.Radiobutton(
                disp_frame,
                text=text,
                value=val,
                variable=self.display_mode_var,
                font=FONT_MEDIUM,
                fg=TEXT_PRIMARY,
                bg=BG_CARD,
                selectcolor=BG_DARK,
                activebackground=BG_CARD,
                activeforeground=TEXT_PRIMARY
            )
            rb.pack(side=tk.LEFT, padx=6)

        # 3.9 Sound Settings Row
        snd_frame = tk.Frame(settings_card, bg=BG_CARD)
        snd_frame.pack(fill=tk.X, pady=(4, 2))

        self.sound_enabled_var = tk.BooleanVar(value=self.config.sound_enabled)
        chk_sound = tk.Checkbutton(
            snd_frame,
            text="サウンド通知",
            variable=self.sound_enabled_var,
            font=FONT_MEDIUM,
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            selectcolor=BG_DARK,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY
        )
        chk_sound.pack(side=tk.LEFT)

        self.sound_theme_var = tk.StringVar(value=self.config.sound_theme)
        themes = ["ping", "gong", "bloop", "blip", "scifi"]
        opt_theme = ttk.Combobox(
            snd_frame,
            textvariable=self.sound_theme_var,
            values=themes,
            state="readonly",
            width=8
        )
        opt_theme.pack(side=tk.LEFT, padx=10)

        btn_test_sound = tk.Button(
            snd_frame,
            text="🎵 試聴",
            font=(FONT_FAMILY, 9),
            fg=TEXT_PRIMARY,
            bg="#21262d",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._on_preview_sound
        )
        btn_test_sound.pack(side=tk.LEFT)

        btn_save = tk.Button(
            snd_frame,
            text="💾 設定を保存",
            font=FONT_BUTTON,
            fg="#ffffff",
            bg="#238636",
            activebackground="#2ea043",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._on_save_settings
        )
        btn_save.pack(side=tk.RIGHT)

        # 4. Live Event Log Card (Transparency)
        log_card = tk.Frame(
            main_frame,
            bg=BG_CARD,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=14,
            pady=10
        )
        log_card.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        log_header = tk.Frame(log_card, bg=BG_CARD)
        log_header.pack(fill=tk.X, pady=(0, 4))

        log_title = tk.Label(
            log_header,
            text="📜 動作履歴ログ (Event History)",
            font=(FONT_FAMILY, 10, "bold"),
            fg=TEXT_SECONDARY,
            bg=BG_CARD
        )
        log_title.pack(side=tk.LEFT)

        btn_clear_log = tk.Button(
            log_header,
            text="クリア",
            font=(FONT_FAMILY, 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_clear_log
        )
        btn_clear_log.pack(side=tk.RIGHT)

        # Listbox with Scrollbar
        list_frame = tk.Frame(log_card, bg=BG_CARD)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_listbox = tk.Listbox(
            list_frame,
            bg="#0d1117",
            fg="#c9d1d9",
            selectbackground="#1f6feb",
            selectforeground="#ffffff",
            font=("Consolas", 9),
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
            height=5
        )
        self.log_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_listbox.yview)

        # Populate initial logs
        for entry in self.timer_service.event_logs:
            self.log_listbox.insert(tk.END, entry)
        if self.log_listbox.size() > 0:
            self.log_listbox.see(tk.END)

        # Bottom info
        info_lbl = tk.Label(
            main_frame,
            text="※ ウィンドウを閉じてもタスクトレイに常駐します。終了はタスクトレイ右クリックから行ってください。",
            font=(FONT_FAMILY, 8),
            fg=TEXT_MUTED,
            bg=BG_DARK
        )
        info_lbl.pack(side=tk.BOTTOM, pady=(4, 0))

    def _create_slider_row(self, parent: tk.Widget, label: str, unit: str,
                           variable: tk.IntVar, from_: int, to_: int) -> None:
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill=tk.X, pady=2)

        lbl_text = tk.Label(row, text=label, font=FONT_MEDIUM, fg=TEXT_SECONDARY, bg=BG_CARD, width=32, anchor=tk.W)
        lbl_text.pack(side=tk.LEFT)

        val_lbl = tk.Label(row, text=f"{variable.get()} {unit}", font=(FONT_FAMILY, 9, "bold"),
                           fg=TEXT_PRIMARY, bg=BG_CARD, width=8, anchor=tk.E)
        val_lbl.pack(side=tk.RIGHT)

        def on_slide(val: str) -> None:
            int_val = int(float(val))
            variable.set(int_val)
            val_lbl.config(text=f"{int_val} {unit}")

        scale = tk.Scale(
            row,
            from_=from_,
            to=to_,
            orient=tk.HORIZONTAL,
            variable=variable,
            showvalue=False,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            troughcolor="#21262d",
            highlightthickness=0,
            activebackground=ACCENT_BLUE,
            command=on_slide
        )
        scale.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 8))

    def add_log_entry(self, entry: str) -> None:
        """Appends a new entry to the live listbox."""
        if hasattr(self, "log_listbox") and self.log_listbox.winfo_exists():
            self.log_listbox.insert(tk.END, entry)
            self.log_listbox.see(tk.END)

    def _on_clear_log(self) -> None:
        if hasattr(self, "log_listbox") and self.log_listbox.winfo_exists():
            self.log_listbox.delete(0, tk.END)

    def update_tick(self, remaining: int, total: int, state: TimerState) -> None:
        """Update countdown and progress bar on main UI."""
        mins = remaining // 60
        secs = remaining % 60
        if mins >= 60:
            hrs = mins // 60
            mins = mins % 60
            time_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        else:
            time_str = f"{mins:02d}:{secs:02d}"

        self.countdown_label.config(text=time_str)

        # Update target timestamp text
        target_str = self.timer_service.get_target_time_str()
        last_str = self.timer_service.get_last_break_str()
        self.target_time_label.config(
            text=f"次回休憩予定: {target_str}  |  前回: {last_str}"
        )

        # Update badge & labels based on state
        if state == TimerState.WORKING:
            self.status_badge.config(
                text="🟢 作業中 (Working)",
                fg=ACCENT_GREEN,
                bg="#1f3629"
            )
            self.next_label.config(text="次の休憩まで")
            self.btn_pause.config(text="⏸ 一時停止")
        elif state == TimerState.PROMPTING:
            self.status_badge.config(
                text="🔔 休憩の確認中 (Prompting)",
                fg=ACCENT_CYAN,
                bg="#1c2d42"
            )
            self.next_label.config(text="自動開始まで")
            self.btn_pause.config(text="⏸ 一時停止")
        elif state == TimerState.BREAKING:
            self.status_badge.config(
                text="🔵 休憩中 (Break Active)",
                fg=ACCENT_CYAN,
                bg="#1c2d42"
            )
            self.next_label.config(text="休憩終了まで")
            self.btn_pause.config(text="⏸ 一時停止")
        elif state == TimerState.PAUSED:
            self.status_badge.config(
                text="⏸ 一時停止中 (Paused)",
                fg=ACCENT_ORANGE,
                bg="#382d1c"
            )
            self.next_label.config(text="タイマー停止中")
            self.btn_pause.config(text="▶ 再開")

        # Update progress bar
        self._draw_progressbar(remaining, total)

    def _draw_progressbar(self, remaining: int, total: int) -> None:
        self.pbar_canvas.delete("all")
        w = self.pbar_canvas.winfo_width()
        if w <= 1:
            w = 560

        fraction = 1.0 - (remaining / max(1, total))
        fill_w = max(0, min(w, int(w * fraction)))

        if fill_w > 0:
            self.pbar_canvas.create_rectangle(
                0, 0, fill_w, 8,
                fill=ACCENT_CYAN,
                outline=""
            )

    def _on_take_break_clicked(self) -> None:
        self.timer_service.trigger_break_now()

    def _on_test_prompt_clicked(self) -> None:
        if self.on_test_prompt:
            self.on_test_prompt(15)

    def _on_test_break_clicked(self) -> None:
        self.on_test_break(5)

    def _on_pause_clicked(self) -> None:
        if self.timer_service.state == TimerState.PAUSED:
            self.timer_service.resume()
        else:
            self.timer_service.pause()

    def _on_preview_sound(self) -> None:
        theme = self.sound_theme_var.get()
        self.audio_manager.play_break_start(theme=theme, enabled=True)

    def _on_save_settings(self) -> None:
        self.config.work_duration_seconds = self.work_var.get() * 60
        self.config.break_duration_seconds = self.break_var.get()
        self.config.postpone_duration_seconds = self.postpone_var.get() * 60
        self.config.immediately_start_breaks = self.immediately_var.get()
        self.config.notification_countdown_seconds = self.prompt_sec_var.get()
        self.config.backdrop_opacity = self.opacity_var.get() / 100.0
        self.config.sound_enabled = self.sound_enabled_var.get()
        self.config.sound_theme = self.sound_theme_var.get()
        self.config.auto_pause_media = self.auto_pause_var.get()
        self.config.idle_reset_enabled = self.idle_reset_var.get()
        self.config.display_mode = self.display_mode_var.get()

        self.config_manager.save()
        self.timer_service.update_config(self.config)

        messagebox.showinfo("BreakTimer Ultra", "設定を保存しました！新しい時間設定と通知設定が反映されます。")

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_to_tray(self) -> None:
        self.root.withdraw()

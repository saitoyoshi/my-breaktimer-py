"""
Configuration management for BreakTimer Ultra.
Persists user settings to JSON in local app data directory or project root.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict

DEFAULT_WORK_SECONDS = 20 * 60       # 20 minutes (20-20-20 rule)
DEFAULT_BREAK_SECONDS = 20            # 20 seconds (20-20-20 rule)
DEFAULT_POSTPONE_SECONDS = 5 * 60    # 5 minutes snooze



@dataclass
class AppConfig:
    work_duration_seconds: int = DEFAULT_WORK_SECONDS
    break_duration_seconds: int = DEFAULT_BREAK_SECONDS
    postpone_duration_seconds: int = DEFAULT_POSTPONE_SECONDS
    sound_enabled: bool = True
    sound_theme: str = "ping"          # "ping", "gong", "bloop", "blip", "scifi"
    backdrop_enabled: bool = True
    backdrop_opacity: float = 0.82
    topmost_enforce_interval_ms: int = 150

    immediately_start_breaks: bool = False  # BreakTimer default: False (Show notification prompt first)
    notification_countdown_seconds: int = 60 # Seconds before auto-starting break

    postpone_break_enabled: bool = True
    skip_break_enabled: bool = True
    auto_start_breaks: bool = True     # Automatically start breaks when timer expires
    auto_pause_media: bool = True      # Automatically pause Netflix/YouTube/media on break start
    auto_resume_media: bool = False    # Automatically resume media when break finishes
    display_mode: str = "fullscreen"   # "fullscreen" (full screen overlay) or "compact" (floating card)
    break_message: str = "目を休めましょう (Look 20 feet away)"
    break_submessage: str = "20フィート（約6m）先を20秒間眺めて、目のピント調節筋をリラックスさせてください。"

    # Sleep & Idle detection
    reset_on_resume: bool = True               # Reset timer immediately upon resuming from sleep/suspend
    sleep_threshold_seconds: float = 4.0      # Loop gap seconds to detect sleep/suspend
    idle_reset_enabled: bool = True            # Reset timer when user returns from being away (idle)
    idle_reset_duration_seconds: int = 5 * 60 # Seconds of inactivity considered as idle break (5 min)



    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class ConfigManager:
    def __init__(self, filename: str = "breaktimer_config.json"):
        # Store in project directory or APPDATA
        appdata = os.environ.get("APPDATA")
        if appdata and os.path.exists(appdata):
            self.config_dir = os.path.join(appdata, "BreakTimerUltra")
        else:
            self.config_dir = os.path.dirname(os.path.abspath(__file__))
            
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_path = os.path.join(self.config_dir, filename)
        self.config = self.load()

    def load(self) -> AppConfig:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return AppConfig.from_dict(data)
            except Exception as e:
                print(f"[Config] Failed to load config, using defaults: {e}")
        return AppConfig()

    def save(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Failed to save config: {e}")

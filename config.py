"""DrillAI Configuration Management.

Loads configuration from environment variables and .env files.
Provides validated, typed configuration for all modules.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


VERSION = "0.1.0"
APP_NAME = "DrillAI"


@dataclass
class AppConfig:
    """Application configuration with validated defaults."""

    # API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    # Screenshot
    screenshot_interval: float = 1.0
    monitor_index: int = 1

    # Change detection
    change_threshold: float = 0.03
    api_cooldown: float = 3.0

    # Region of interest
    region_enabled: bool = False
    region: Optional[Tuple[int, int, int, int]] = None  # x, y, width, height

    # Mouse
    mouse_enabled: bool = False
    mouse_dry_run: bool = True
    auto_click: bool = False
    max_mouse_actions: int = 0  # 0 means unlimited

    # Logging
    debug: bool = False
    log_level: str = "INFO"
    save_screenshots: bool = False

    # Paths
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    log_dir: Path = field(default_factory=lambda: Path.cwd() / "logs")
    results_dir: Path = field(default_factory=lambda: Path.cwd() / "results")

    # Policy
    ambiguous_image_policy: str = "analyze"  # 'analyze' or 'skip'

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.screenshot_interval < 0.1:
            errors.append("Screenshot interval must be >= 0.1 seconds")
        if self.screenshot_interval > 60.0:
            errors.append("Screenshot interval must be <= 60.0 seconds")

        if self.change_threshold < 0.0 or self.change_threshold > 1.0:
            errors.append("Change threshold must be between 0.0 and 1.0")

        if self.api_cooldown < 0.0:
            errors.append("API cooldown must be >= 0.0 seconds")
        if self.api_cooldown > 300.0:
            errors.append("API cooldown must be <= 300.0 seconds")

        if self.monitor_index < 0:
            errors.append("Monitor index must be >= 0")

        if self.region_enabled and self.region:
            x, y, w, h = self.region
            if w <= 0:
                errors.append("Region width must be positive")
            if h <= 0:
                errors.append("Region height must be positive")
            if x < 0 or y < 0:
                errors.append("Region coordinates must be non-negative")

        if self.max_mouse_actions < 0:
            errors.append("Max mouse actions must be >= 0 (0 means unlimited)")

        if self.ambiguous_image_policy not in ("analyze", "skip"):
            errors.append("Ambiguous image policy must be 'analyze' or 'skip'")

        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            errors.append(f"Invalid log level: {self.log_level}")

        return errors

    def require_api_key(self) -> None:
        """Raise an error if API key is not configured."""
        if not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Set it in your .env file or as an environment variable.\n"
                "Get your API key from: https://aistudio.google.com/apikey"
            )


def parse_region(region_str: str) -> Tuple[int, int, int, int]:
    """Parse a region string 'X,Y,WIDTH,HEIGHT' into a tuple.

    Args:
        region_str: Comma-separated region specification.

    Returns:
        Tuple of (x, y, width, height).

    Raises:
        ValueError: If the format is invalid.
    """
    parts = region_str.strip().split(",")
    if len(parts) != 4:
        raise ValueError(
            f"Region must have exactly 4 values (X,Y,WIDTH,HEIGHT), got {len(parts)}"
        )
    try:
        values = tuple(int(p.strip()) for p in parts)
    except ValueError:
        raise ValueError("Region values must be integers")

    x, y, w, h = values
    if w <= 0:
        raise ValueError(f"Region width must be positive, got {w}")
    if h <= 0:
        raise ValueError(f"Region height must be positive, got {h}")
    if x < 0 or y < 0:
        raise ValueError(f"Region coordinates must be non-negative, got ({x}, {y})")

    return values  # type: ignore


def load_config(env_path: Optional[str] = None, base_dir: Optional[Path] = None) -> AppConfig:
    """Load configuration from environment variables and .env file.

    Args:
        env_path: Optional path to .env file.
        base_dir: Optional base directory for the application.

    Returns:
        Validated AppConfig instance.
    """
    if base_dir is None:
        # Try to find the project directory
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent

    # Load .env file
    if load_dotenv is not None:
        if env_path:
            load_dotenv(env_path)
        else:
            # Try project directory first, then cwd
            env_file = base_dir / ".env"
            if env_file.exists():
                load_dotenv(str(env_file))
            elif (Path.cwd() / ".env").exists():
                load_dotenv(str(Path.cwd() / ".env"))

    # Parse region if enabled
    region = None
    region_enabled = os.getenv("REGION_ENABLED", "false").lower() in ("true", "1", "yes")
    if region_enabled:
        try:
            rx = int(os.getenv("REGION_X", "0"))
            ry = int(os.getenv("REGION_Y", "0"))
            rw = int(os.getenv("REGION_WIDTH", "0"))
            rh = int(os.getenv("REGION_HEIGHT", "0"))
            if rw > 0 and rh > 0:
                region = (rx, ry, rw, rh)
        except ValueError:
            pass

    log_dir = base_dir / "logs"
    results_dir = base_dir / "results"

    config = AppConfig(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        screenshot_interval=float(os.getenv("SCREENSHOT_INTERVAL", "1.0")),
        monitor_index=int(os.getenv("MONITOR_INDEX", "1")),
        change_threshold=float(os.getenv("CHANGE_THRESHOLD", "0.03")),
        api_cooldown=float(os.getenv("API_COOLDOWN", "3.0")),
        region_enabled=region_enabled,
        region=region,
        mouse_enabled=os.getenv("MOUSE_ENABLED", "false").lower() in ("true", "1", "yes"),
        mouse_dry_run=os.getenv("MOUSE_DRY_RUN", "true").lower() in ("true", "1", "yes"),
        auto_click=os.getenv("AUTO_CLICK", "false").lower() in ("true", "1", "yes"),
        max_mouse_actions=int(os.getenv("MAX_MOUSE_ACTIONS", "0")),
        debug=os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        save_screenshots=os.getenv("SAVE_SCREENSHOTS", "false").lower() in ("true", "1", "yes"),
        base_dir=base_dir,
        log_dir=log_dir,
        results_dir=results_dir,
        ambiguous_image_policy=os.getenv("AMBIGUOUS_IMAGE_POLICY", "analyze").lower(),
    )

    return config

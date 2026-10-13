"""DrillAI Monitor Manager.

Enumerates and manages display monitors using mss.
Handles monitor selection, validation, and coordinate mapping.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

logger = logging.getLogger("drillai.monitor")


@dataclass
class MonitorInfo:
    """Information about a display monitor."""
    index: int  # mss monitor index (0=virtual desktop, 1+=individual monitors)
    left: int
    top: int
    width: int
    height: int
    is_primary: bool = False
    is_virtual_desktop: bool = False

    @property
    def bounds(self) -> dict:
        """Return monitor bounds as mss-compatible dict."""
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

    def contains_region(self, x: int, y: int, width: int, height: int) -> bool:
        """Check if a region fits within this monitor's bounds.

        Region coordinates are relative to the monitor.
        """
        if x < 0 or y < 0:
            return False
        if width <= 0 or height <= 0:
            return False
        if x + width > self.width:
            return False
        if y + height > self.height:
            return False
        return True

    def __str__(self) -> str:
        label = "Virtual Desktop" if self.is_virtual_desktop else f"Monitor {self.index}"
        if self.is_primary:
            label += " (Primary)"
        return f"{label}: {self.width}x{self.height} at ({self.left}, {self.top})"


class MonitorManager:
    """Manages display monitor enumeration and selection.

    Uses mss for cross-platform monitor detection.
    mss indexing: 0 = combined virtual desktop, 1 = primary monitor, 2+ = other monitors.
    """

    def __init__(self) -> None:
        if not MSS_AVAILABLE:
            raise ImportError(
                "mss is not installed. Install it with: pip install mss"
            )

    def enumerate_monitors(self) -> List[MonitorInfo]:
        """Enumerate all available monitors.

        Returns:
            List of MonitorInfo objects. Index 0 is always the virtual desktop.
            Index 1 is the primary monitor. Index 2+ are additional monitors.
        """
        monitors = []
        try:
            with mss.mss() as sct:
                for i, mon in enumerate(sct.monitors):
                    info = MonitorInfo(
                        index=i,
                        left=mon["left"],
                        top=mon["top"],
                        width=mon["width"],
                        height=mon["height"],
                        is_primary=(i == 1),
                        is_virtual_desktop=(i == 0),
                    )
                    monitors.append(info)
        except Exception as e:
            logger.error(f"Failed to enumerate monitors: {e}")
            raise RuntimeError(f"Monitor enumeration failed: {e}") from e

        if not monitors:
            raise RuntimeError("No monitors detected")

        return monitors

    def get_monitor(self, index: int) -> MonitorInfo:
        """Get a specific monitor by index.

        Args:
            index: Monitor index. 0 = virtual desktop, 1 = primary, 2+ = others.

        Returns:
            MonitorInfo for the requested monitor.

        Raises:
            ValueError: If the index is invalid.
        """
        monitors = self.enumerate_monitors()
        if index < 0 or index >= len(monitors):
            available = len(monitors) - 1  # Exclude virtual desktop from count
            raise ValueError(
                f"Monitor index {index} is invalid. "
                f"Available monitors: 0 (virtual desktop), 1-{available} (individual monitors)"
            )
        return monitors[index]

    def get_primary_monitor(self) -> MonitorInfo:
        """Get the primary monitor (index 1)."""
        return self.get_monitor(1)

    def validate_region(
        self, monitor: MonitorInfo, x: int, y: int, width: int, height: int
    ) -> List[str]:
        """Validate that a region fits within a monitor.

        Args:
            monitor: Target monitor.
            x: Region X offset (relative to monitor).
            y: Region Y offset (relative to monitor).
            width: Region width.
            height: Region height.

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors = []
        if width <= 0:
            errors.append(f"Region width must be positive, got {width}")
        if height <= 0:
            errors.append(f"Region height must be positive, got {height}")
        if x < 0:
            errors.append(f"Region X must be non-negative, got {x}")
        if y < 0:
            errors.append(f"Region Y must be non-negative, got {y}")
        if not errors:
            if x + width > monitor.width:
                errors.append(
                    f"Region extends beyond monitor width: {x}+{width} > {monitor.width}"
                )
            if y + height > monitor.height:
                errors.append(
                    f"Region extends beyond monitor height: {y}+{height} > {monitor.height}"
                )
        return errors

    def region_to_absolute(
        self, monitor: MonitorInfo, x: int, y: int, width: int, height: int
    ) -> dict:
        """Convert monitor-relative region coordinates to absolute screen coordinates.

        Args:
            monitor: The monitor the region is relative to.
            x: X offset relative to monitor.
            y: Y offset relative to monitor.
            width: Region width.
            height: Region height.

        Returns:
            Dict with absolute screen coordinates for mss capture.
        """
        return {
            "left": monitor.left + x,
            "top": monitor.top + y,
            "width": width,
            "height": height,
        }

    def format_monitor_list(self) -> str:
        """Format a human-readable list of monitors."""
        monitors = self.enumerate_monitors()
        lines = ["Available monitors:"]
        for mon in monitors:
            lines.append(f"  [{mon.index}] {mon}")
        return "\n".join(lines)

"""DrillAI Screenshot Capture.

Captures fullscreen desktop screenshots using mss.
Supports individual monitor selection, ROI cropping, and quality control.
"""

import io
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from monitor_manager import MonitorInfo, MonitorManager

logger = logging.getLogger("drillai.screenshot")


class ScreenshotCapture:
    """Captures desktop screenshots using mss.

    Processes images in memory to avoid unnecessary disk I/O.
    Supports monitor selection and region-of-interest cropping.
    """

    def __init__(self, monitor_manager: Optional[MonitorManager] = None) -> None:
        if not MSS_AVAILABLE:
            raise ImportError("mss is not installed. Install it with: pip install mss")
        if not PIL_AVAILABLE:
            raise ImportError("Pillow is not installed. Install it with: pip install Pillow")

        self.monitor_manager = monitor_manager or MonitorManager()

    def capture_monitor(self, monitor_index: int = 1) -> Image.Image:
        """Capture a screenshot of a specific monitor.

        Args:
            monitor_index: Monitor index. 0=virtual desktop, 1=primary, 2+=others.

        Returns:
            PIL Image of the captured screenshot.

        Raises:
            ValueError: If monitor index is invalid.
            RuntimeError: If capture fails.
        """
        monitor = self.monitor_manager.get_monitor(monitor_index)
        return self._capture_region(monitor.bounds)

    def capture_region(
        self,
        monitor_index: int,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Image.Image:
        """Capture a specific region of a monitor.

        Coordinates are relative to the selected monitor.

        Args:
            monitor_index: Monitor to capture from.
            x: X offset relative to monitor.
            y: Y offset relative to monitor.
            width: Region width in pixels.
            height: Region height in pixels.

        Returns:
            PIL Image of the captured region.

        Raises:
            ValueError: If region is invalid or outside monitor bounds.
            RuntimeError: If capture fails.
        """
        monitor = self.monitor_manager.get_monitor(monitor_index)

        errors = self.monitor_manager.validate_region(monitor, x, y, width, height)
        if errors:
            raise ValueError("Invalid region: " + "; ".join(errors))

        abs_region = self.monitor_manager.region_to_absolute(monitor, x, y, width, height)
        return self._capture_region(abs_region)

    def capture_with_roi(
        self,
        monitor_index: int = 1,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Image.Image:
        """Capture a screenshot with optional ROI cropping.

        Args:
            monitor_index: Monitor to capture.
            region: Optional (x, y, width, height) for ROI. If None, captures full monitor.

        Returns:
            PIL Image, cropped to ROI if specified.
        """
        if region:
            x, y, w, h = region
            return self.capture_region(monitor_index, x, y, w, h)
        else:
            return self.capture_monitor(monitor_index)

    def _capture_region(self, bounds: dict) -> Image.Image:
        """Capture a screen region defined by bounds dict.

        Args:
            bounds: Dict with 'left', 'top', 'width', 'height' keys.

        Returns:
            PIL Image of the captured region.

        Raises:
            RuntimeError: If capture fails.
        """
        try:
            with mss.mss() as sct:
                raw = sct.grab(bounds)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                return img
        except Exception as e:
            err_msg = str(e)
            if "BitBlt" in err_msg or "screen grab" in err_msg.lower():
                diagnostic = (
                    "Desktop display is not accessible in the current session. "
                    "This typically occurs in a headless environment, SSH session, disconnected RDP, "
                    "or when the Windows workstation is locked. Please run DrillAI in an active "
                    "interactive Windows desktop session."
                )
                logger.error(f"Screenshot capture failed: {diagnostic} (Internal error: {err_msg})")
                raise RuntimeError(diagnostic) from e
            logger.error(f"Screenshot capture failed: {err_msg}")
            raise RuntimeError(f"Failed to capture screenshot: {err_msg}") from e

    def image_to_bytes(self, image: Image.Image, format: str = "PNG", quality: int = 95) -> bytes:
        """Convert a PIL Image to bytes.

        Args:
            image: PIL Image to convert.
            format: Image format (PNG or JPEG).
            quality: JPEG quality (1-100). Ignored for PNG.

        Returns:
            Image data as bytes.
        """
        buffer = io.BytesIO()
        save_kwargs = {"format": format}
        if format.upper() == "JPEG":
            save_kwargs["quality"] = quality
        image.save(buffer, **save_kwargs)
        return buffer.getvalue()

    def save_screenshot(
        self, image: Image.Image, path: Path, format: str = "PNG"
    ) -> Path:
        """Save a screenshot to disk.

        Args:
            image: PIL Image to save.
            path: Target file path.
            format: Image format.

        Returns:
            Path where the image was saved.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path), format=format)
        logger.info(f"Screenshot saved to {path}")
        return path

    @staticmethod
    def is_blank_image(image: Image.Image, threshold: float = 0.01) -> bool:
        """Check if an image is effectively blank (uniform color).

        Args:
            image: PIL Image to check.
            threshold: Maximum allowed color variance (0.0-1.0).

        Returns:
            True if the image appears blank or unusable.
        """
        try:
            import numpy as np
            arr = np.array(image)
            if arr.size == 0:
                return True
            # Check variance across all channels
            variance = np.var(arr / 255.0)
            return bool(variance < threshold)
        except ImportError:
            # Fallback without numpy: sample pixels
            width, height = image.size
            if width == 0 or height == 0:
                return True
            pixels = []
            step_x = max(1, width // 10)
            step_y = max(1, height // 10)
            for px in range(0, width, step_x):
                for py in range(0, height, step_y):
                    pixels.append(image.getpixel((px, py)))
            if not pixels:
                return True
            first = pixels[0]
            return all(p == first for p in pixels)

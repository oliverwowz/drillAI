"""Tests for DrillAI Screenshot Capture."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from screenshot import ScreenshotCapture
from monitor_manager import MonitorInfo, MonitorManager


def test_image_to_bytes(synthetic_rgb_image):
    """Verify in-memory encoding to PNG and JPEG."""
    mgr = MagicMock(spec=MonitorManager)
    cap = ScreenshotCapture(monitor_manager=mgr)

    png_bytes = cap.image_to_bytes(synthetic_rgb_image, format="PNG")
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 0
    assert png_bytes.startswith(b"\x89PNG")

    jpeg_bytes = cap.image_to_bytes(synthetic_rgb_image, format="JPEG", quality=80)
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0
    assert jpeg_bytes.startswith(b"\xff\xd8")


def test_save_screenshot(synthetic_rgb_image, tmp_path):
    """Verify saving screenshot to disk."""
    mgr = MagicMock(spec=MonitorManager)
    cap = ScreenshotCapture(monitor_manager=mgr)

    target_file = tmp_path / "subdir" / "test_shot.png"
    saved = cap.save_screenshot(synthetic_rgb_image, target_file)

    assert saved.exists()
    assert saved == target_file
    loaded = Image.open(saved)
    assert loaded.size == synthetic_rgb_image.size


def test_is_blank_image(synthetic_blank_image, synthetic_rgb_image):
    """Verify blank image detection."""
    assert ScreenshotCapture.is_blank_image(synthetic_blank_image) is True
    assert ScreenshotCapture.is_blank_image(synthetic_rgb_image) is False


def test_capture_monitor_with_mock():
    """Verify capture_monitor calls internal grab with monitor bounds."""
    mgr = MagicMock(spec=MonitorManager)
    mgr.get_monitor.return_value = MonitorInfo(index=1, left=0, top=0, width=100, height=100)

    cap = ScreenshotCapture(monitor_manager=mgr)
    dummy_img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    with patch.object(cap, "_capture_region", return_value=dummy_img) as mock_grab:
        img = cap.capture_monitor(1)
        assert img == dummy_img
        mock_grab.assert_called_once_with({"left": 0, "top": 0, "width": 100, "height": 100})


def test_capture_with_roi():
    """Verify capture_with_roi routes to capture_region when region is provided."""
    mgr = MagicMock(spec=MonitorManager)
    mgr.get_monitor.return_value = MonitorInfo(index=1, left=0, top=0, width=1920, height=1080)
    mgr.validate_region.return_value = []
    mgr.region_to_absolute.return_value = {"left": 50, "top": 50, "width": 200, "height": 150}

    cap = ScreenshotCapture(monitor_manager=mgr)
    dummy_img = Image.new("RGB", (200, 150), color=(100, 100, 100))
    with patch.object(cap, "_capture_region", return_value=dummy_img) as mock_grab:
        img = cap.capture_with_roi(1, region=(50, 50, 200, 150))
        assert img == dummy_img
        mock_grab.assert_called_once_with({"left": 50, "top": 50, "width": 200, "height": 150})

"""Tests for DrillAI Monitor Manager."""

from unittest.mock import MagicMock, patch
import pytest

from monitor_manager import MonitorInfo, MonitorManager


def test_monitor_info_contains_region():
    """Verify MonitorInfo bounds checking."""
    mon = MonitorInfo(index=1, left=0, top=0, width=1920, height=1080)
    assert mon.contains_region(0, 0, 1920, 1080) is True
    assert mon.contains_region(100, 100, 800, 600) is True
    assert mon.contains_region(-1, 0, 100, 100) is False
    assert mon.contains_region(0, 0, 2000, 500) is False
    assert mon.contains_region(0, 0, 1000, 1200) is False


def test_enumerate_monitors(mock_mss_monitors):
    """Verify monitor enumeration correctly labels indices."""
    with patch("mss.mss") as mock_mss:
        instance = MagicMock()
        instance.monitors = mock_mss_monitors
        mock_mss.return_value.__enter__.return_value = instance

        mgr = MonitorManager()
        monitors = mgr.enumerate_monitors()

        assert len(monitors) == 3
        assert monitors[0].is_virtual_desktop is True
        assert monitors[0].width == 3840
        assert monitors[1].is_primary is True
        assert monitors[1].width == 1920
        assert monitors[2].left == 1920


def test_get_monitor_valid_and_invalid(mock_mss_monitors):
    """Verify valid retrieval and invalid index handling."""
    with patch("mss.mss") as mock_mss:
        instance = MagicMock()
        instance.monitors = mock_mss_monitors
        mock_mss.return_value.__enter__.return_value = instance

        mgr = MonitorManager()
        primary = mgr.get_primary_monitor()
        assert primary.index == 1

        with pytest.raises(ValueError, match="invalid"):
            mgr.get_monitor(99)
        with pytest.raises(ValueError, match="invalid"):
            mgr.get_monitor(-1)


def test_validate_region(mock_mss_monitors):
    """Verify region validation logic against monitor bounds."""
    mon = MonitorInfo(index=1, left=1920, top=0, width=1920, height=1080)
    mgr = MonitorManager()

    # Valid region
    errs = mgr.validate_region(mon, 100, 100, 800, 600)
    assert len(errs) == 0

    # Region outside bounds
    errs_overflow = mgr.validate_region(mon, 1500, 500, 800, 600)
    assert len(errs_overflow) > 0
    assert any("width" in e for e in errs_overflow)

    # Negative coordinates
    errs_neg = mgr.validate_region(mon, -50, 0, 100, 100)
    assert len(errs_neg) > 0


def test_region_to_absolute():
    """Verify relative coordinates correctly map to absolute desktop position."""
    mon = MonitorInfo(index=2, left=1920, top=100, width=1920, height=1080)
    mgr = MonitorManager()

    abs_rect = mgr.region_to_absolute(mon, 50, 60, 400, 300)
    assert abs_rect == {
        "left": 1970,
        "top": 160,
        "width": 400,
        "height": 300,
    }

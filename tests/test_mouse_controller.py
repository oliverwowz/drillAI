"""Tests for DrillAI Mouse Controller."""

from unittest.mock import patch
import pytest

from mouse_controller import MouseController, MouseControllerError


def test_mouse_disabled_by_default():
    """Verify click/move raises error when mouse controller is disabled."""
    mc = MouseController(enabled=False)
    with pytest.raises(MouseControllerError, match="not enabled"):
        mc.click(100, 100)
    with pytest.raises(MouseControllerError, match="not enabled"):
        mc.move(100, 100)


def test_mouse_dry_run_mode():
    """Verify dry-run logs action without executing actual mouse calls."""
    bounds = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    mc = MouseController(enabled=True, dry_run=True, monitor_bounds=bounds)

    action = mc.click(500, 400, button="left")
    assert action.dry_run is True
    assert action.executed is False
    assert action.x == 500
    assert action.y == 400
    assert mc.action_count == 1
    assert "DRY-RUN" in str(action)


def test_coordinate_validation():
    """Verify out-of-bounds and negative coordinates are rejected."""
    bounds = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    mc = MouseController(enabled=True, dry_run=True, monitor_bounds=bounds)

    with pytest.raises(MouseControllerError, match="Invalid coordinates"):
        mc.click(-10, 100)

    with pytest.raises(MouseControllerError, match="Invalid coordinates"):
        mc.click(2000, 500)


def test_action_limit_enforcement():
    """Verify controller stops after exceeding max_actions."""
    bounds = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    mc = MouseController(enabled=True, dry_run=True, max_actions=2, monitor_bounds=bounds)

    mc.click(100, 100)
    mc.click(100, 100)
    assert mc.action_count == 2
    assert mc.remaining_actions == 0

    with pytest.raises(MouseControllerError, match="Maximum action count"):
        mc.click(100, 100)


def test_unlimited_action_limit():
    """Verify controller allows unlimited clicks when max_actions is 0 or negative."""
    bounds = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    mc = MouseController(enabled=True, dry_run=True, max_actions=0, monitor_bounds=bounds)
    for _ in range(50):
        mc.click(100, 100)
    assert mc.action_count == 50
    assert mc.remaining_actions == float("inf")


def test_format_log():
    """Verify action log formatting."""
    bounds = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    mc = MouseController(enabled=True, dry_run=True, monitor_bounds=bounds)
    mc.click(250, 300)
    log_text = mc.format_log()
    assert "Mouse action log (1 actions):" in log_text
    assert "click(250, 300)" in log_text

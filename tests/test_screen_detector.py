"""Tests for DrillAI Screen Change Detector."""

import time
from PIL import Image, ImageDraw
import pytest

from screen_detector import ScreenChangeDetector


def test_compute_image_hash_deterministic(synthetic_rgb_image):
    """Verify perceptual hash is consistent for identical images."""
    detector = ScreenChangeDetector()
    h1 = detector.compute_image_hash(synthetic_rgb_image)
    h2 = detector.compute_image_hash(synthetic_rgb_image)
    assert h1 == h2
    assert len(h1) == 32  # MD5 hex length


def test_is_duplicate_detection(synthetic_rgb_image):
    """Verify duplicate frame identification."""
    detector = ScreenChangeDetector()
    assert detector.is_duplicate(synthetic_rgb_image) is False
    assert detector.is_duplicate(synthetic_rgb_image) is True
    assert detector.stats["duplicates_suppressed"] == 1


def test_change_ratio_identical_and_different(synthetic_rgb_image):
    """Verify change ratio for first frame, identical frame, and changed frame."""
    detector = ScreenChangeDetector(comparison_scale=1.0)

    # First frame always yields 1.0
    r1 = detector.compute_change_ratio(synthetic_rgb_image)
    assert r1 == 1.0

    # Identical frame yields 0.0
    r2 = detector.compute_change_ratio(synthetic_rgb_image)
    assert r2 == 0.0

    # Modified frame yields ratio > 0.0
    modified = synthetic_rgb_image.copy()
    draw = ImageDraw.Draw(modified)
    draw.rectangle([0, 0, 400, 300], fill=(255, 0, 0))  # Completely changed
    r3 = detector.compute_change_ratio(modified)
    assert r3 > 0.5


def test_detect_change_threshold_and_debounce(synthetic_rgb_image):
    """Verify detect_change applies threshold and debounce."""
    detector = ScreenChangeDetector(
        change_threshold=0.05,
        debounce_time=0.5,
    )

    # First frame triggers
    changed, ratio, reason = detector.detect_change(synthetic_rgb_image)
    assert changed is True

    # Immediate second frame blocked by debounce or duplicate
    changed2, ratio2, reason2 = detector.detect_change(synthetic_rgb_image)
    assert changed2 is False


def test_api_cooldown_behavior():
    """Verify can_send_api_request enforces api_cooldown interval."""
    detector = ScreenChangeDetector(api_cooldown=0.2)

    # Initially allowed
    can_send, wait = detector.can_send_api_request()
    assert can_send is True
    assert wait == 0.0

    # Record API call
    detector.record_api_request()

    # Immediately disallowed
    can_send2, wait2 = detector.can_send_api_request()
    assert can_send2 is False
    assert wait2 > 0.0

    # After cooldown period
    time.sleep(0.25)
    can_send3, wait3 = detector.can_send_api_request()
    assert can_send3 is True
    assert wait3 == 0.0


def test_reset_clears_state(synthetic_rgb_image):
    """Verify reset clears hash history and frame state."""
    detector = ScreenChangeDetector()
    detector.detect_change(synthetic_rgb_image)
    detector.record_api_request()

    detector.reset()
    assert detector.stats["changes_detected"] == 0
    assert detector.stats["duplicates_suppressed"] == 0
    assert detector.stats["hash_history_size"] == 0
    can_send, _ = detector.can_send_api_request()
    assert can_send is True

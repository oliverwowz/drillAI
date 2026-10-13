"""DrillAI Screen Change Detector.

Detects meaningful visual changes between screenshots using OpenCV.
Implements duplicate suppression, debouncing, and cooldown management.
"""

import hashlib
import logging
import time
from collections import deque
from typing import Optional, Tuple

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger("drillai.detector")


class ScreenChangeDetector:
    """Detects meaningful visual changes between consecutive screenshots.
    
    Uses structural comparison with configurable thresholds to avoid
    unnecessary API calls for minor visual changes like cursor movement
    or animations.
    
    Attributes:
        change_threshold: Minimum change ratio to trigger detection (0.0-1.0).
        api_cooldown: Minimum seconds between API requests.
        debounce_time: Minimum seconds between change detections.
        comparison_scale: Scale factor for comparison (smaller = faster but less precise).
    """
    
    def __init__(
        self,
        change_threshold: float = 0.03,
        api_cooldown: float = 3.0,
        debounce_time: float = 0.5,
        comparison_scale: float = 0.5,
        max_queue_size: int = 100,
    ) -> None:
        if not CV2_AVAILABLE:
            raise ImportError(
                "OpenCV is not installed. Install with: pip install opencv-python"
            )
        
        self.change_threshold = max(0.0, min(1.0, change_threshold))
        self.api_cooldown = max(0.0, api_cooldown)
        self.debounce_time = max(0.0, debounce_time)
        self.comparison_scale = max(0.1, min(1.0, comparison_scale))
        self.max_queue_size = max(1, max_queue_size)
        
        self._previous_frame: Optional[np.ndarray] = None
        self._previous_hash: Optional[str] = None
        self._last_change_time: float = 0.0
        self._last_api_time: float = 0.0
        self._hash_history: deque = deque(maxlen=max_queue_size)
        self._change_count: int = 0
        self._duplicate_count: int = 0
    
    def compute_image_hash(self, image: Image.Image) -> str:
        """Compute a perceptual hash of an image for duplicate detection.
        
        Uses a downscaled grayscale version to create a stable hash
        that is resistant to minor rendering differences.
        
        Args:
            image: PIL Image to hash.
            
        Returns:
            Hex string hash of the image.
        """
        # Downscale to small size for hashing
        small = image.resize((64, 64), Image.Resampling.LANCZOS).convert("L")
        pixels = small.tobytes()
        return hashlib.md5(pixels).hexdigest()
    
    def is_duplicate(self, image: Image.Image) -> bool:
        """Check if an image is a duplicate of a recently seen image.
        
        Args:
            image: PIL Image to check.
            
        Returns:
            True if this image has been seen recently.
        """
        img_hash = self.compute_image_hash(image)
        
        if img_hash in self._hash_history:
            self._duplicate_count += 1
            logger.debug(f"Duplicate frame detected (hash: {img_hash[:8]}...)")
            return True
        
        self._hash_history.append(img_hash)
        return False
    
    def _pil_to_cv2_gray(self, image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV grayscale array."""
        arr = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        return gray
    
    def _downscale(self, frame: np.ndarray) -> np.ndarray:
        """Downscale a frame for faster comparison."""
        if self.comparison_scale >= 1.0:
            return frame
        h, w = frame.shape[:2]
        new_w = max(1, int(w * self.comparison_scale))
        new_h = max(1, int(h * self.comparison_scale))
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    def _normalize(self, frame: np.ndarray) -> np.ndarray:
        """Normalize frame for consistent comparison."""
        # Apply slight Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        return blurred
    
    def compute_change_ratio(self, image: Image.Image) -> float:
        """Compute the visual change ratio compared to the previous frame.
        
        Args:
            image: Current screenshot as PIL Image.
            
        Returns:
            Change ratio between 0.0 (identical) and 1.0 (completely different).
            Returns 1.0 if no previous frame exists (first frame).
        """
        current_gray = self._pil_to_cv2_gray(image)
        current_small = self._downscale(current_gray)
        current_norm = self._normalize(current_small)
        
        if self._previous_frame is None:
            self._previous_frame = current_norm
            return 1.0  # First frame always triggers
        
        # Ensure same dimensions
        if self._previous_frame.shape != current_norm.shape:
            self._previous_frame = current_norm
            return 1.0  # Resolution changed
        
        # Compute absolute difference
        diff = cv2.absdiff(self._previous_frame, current_norm)
        
        # Threshold to ignore very minor changes (noise, sub-pixel rendering)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        
        # Calculate ratio of changed pixels
        total_pixels = thresh.size
        changed_pixels = np.count_nonzero(thresh)
        change_ratio = changed_pixels / total_pixels if total_pixels > 0 else 0.0
        
        self._previous_frame = current_norm
        return change_ratio
    
    def detect_change(self, image: Image.Image) -> Tuple[bool, float, str]:
        """Detect if a meaningful visual change occurred.
        
        Combines change detection with debouncing and duplicate suppression.
        
        Args:
            image: Current screenshot as PIL Image.
            
        Returns:
            Tuple of (change_detected, change_ratio, reason):
            - change_detected: True if a meaningful change was found.
            - change_ratio: The computed change ratio.
            - reason: Human-readable explanation of the detection result.
        """
        current_time = time.time()
        
        # Check debounce
        time_since_last = current_time - self._last_change_time
        if self._last_change_time > 0 and time_since_last < self.debounce_time:
            return False, 0.0, f"Debounce active ({time_since_last:.1f}s < {self.debounce_time:.1f}s)"
        
        # Check duplicate
        if self.is_duplicate(image):
            return False, 0.0, "Duplicate frame"
        
        # Compute change
        change_ratio = self.compute_change_ratio(image)
        
        if change_ratio >= self.change_threshold:
            self._change_count += 1
            self._last_change_time = current_time
            logger.info(
                f"Visual change detected: {change_ratio:.4f} "
                f"(threshold: {self.change_threshold})"
            )
            return True, change_ratio, f"Change detected ({change_ratio:.4f})"
        else:
            return False, change_ratio, (
                f"Below threshold ({change_ratio:.4f} < {self.change_threshold})"
            )
    
    def can_send_api_request(self) -> Tuple[bool, float]:
        """Check if enough time has passed for a new API request.
        
        Returns:
            Tuple of (can_send, wait_time):
            - can_send: True if an API request is allowed now.
            - wait_time: Seconds to wait if not allowed (0.0 if allowed).
        """
        if self._last_api_time == 0.0:
            return True, 0.0
        
        elapsed = time.time() - self._last_api_time
        if elapsed >= self.api_cooldown:
            return True, 0.0
        else:
            wait_time = self.api_cooldown - elapsed
            return False, wait_time
    
    def record_api_request(self) -> None:
        """Record that an API request was made."""
        self._last_api_time = time.time()
    
    def reset(self) -> None:
        """Reset all detection state."""
        self._previous_frame = None
        self._previous_hash = None
        self._last_change_time = 0.0
        self._last_api_time = 0.0
        self._hash_history.clear()
        self._change_count = 0
        self._duplicate_count = 0
        logger.debug("Screen change detector reset")
    
    @property
    def stats(self) -> dict:
        """Return detection statistics."""
        return {
            "changes_detected": self._change_count,
            "duplicates_suppressed": self._duplicate_count,
            "hash_history_size": len(self._hash_history),
        }

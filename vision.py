"""DrillAI Vision Utilities.

Helper functions for image processing, quality checks, and ROI analysis.
"""

import logging
from typing import Optional, Tuple

try:
    from PIL import Image, ImageStat
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger("drillai.vision")


def check_image_quality(image: Image.Image) -> Tuple[bool, str]:
    """Check if an image is suitable for analysis.
    
    Args:
        image: PIL Image to check.
        
    Returns:
        Tuple of (is_usable, reason).
    """
    if not PIL_AVAILABLE:
        return True, "Cannot check quality (Pillow not available)"
    
    width, height = image.size
    
    # Check minimum dimensions
    if width < 50 or height < 50:
        return False, f"Image too small: {width}x{height}"
    
    # Check if image is blank
    try:
        stat = ImageStat.Stat(image)
        variances = stat.var
        avg_variance = sum(variances) / len(variances)
        if avg_variance < 0.5:
            return False, "Image appears blank (near-uniform color)"
    except Exception as e:
        logger.debug(f"Image quality check error: {e}")
    
    return True, "OK"


def estimate_content_region(image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """Estimate the main content region of an image using edge detection.
    
    This is an estimate and not an absolute calibration.
    
    Args:
        image: PIL Image to analyze.
        
    Returns:
        Tuple of (x, y, width, height) or None if unable to estimate.
    """
    try:
        import cv2
        import numpy as np
        
        arr = np.array(image.convert("L"))
        edges = cv2.Canny(arr, 50, 150)
        coords = cv2.findNonZero(edges)
        if coords is None:
            return None
        
        x, y, w, h = cv2.boundingRect(coords)
        pad = 20
        x = max(0, x - pad)
        y = max(0, y - pad)
        w = min(image.width - x, w + 2 * pad)
        h = min(image.height - y, h + 2 * pad)
        
        return (x, y, w, h)
    except ImportError:
        logger.debug("OpenCV not available for content estimation")
        return None
    except Exception as e:
        logger.debug(f"Content region estimation failed: {e}")
        return None

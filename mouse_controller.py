"""DrillAI Mouse Controller.

Provides controlled mouse interaction for local practice/test environments.
Requires explicit opt-in and includes safety controls.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5
except ImportError:
    PYAUTOGUI_AVAILABLE = False

logger = logging.getLogger("drillai.mouse")


@dataclass
class MouseAction:
    """Record of a mouse action."""
    action_type: str  # 'click', 'move', 'double_click'
    x: int = 0
    y: int = 0
    button: str = "left"
    executed: bool = False
    dry_run: bool = True
    timestamp: float = 0.0
    error: Optional[str] = None
    
    def __str__(self) -> str:
        status = "DRY-RUN" if self.dry_run else ("OK" if self.executed else "FAILED")
        return f"[{status}] {self.action_type}({self.x}, {self.y}) button={self.button}"


class MouseControllerError(Exception):
    """Mouse controller error."""
    pass


class MouseController:
    """Controlled mouse interaction with safety features.
    
    Features:
    - Dry-run mode (default): logs actions without executing.
    - Explicit opt-in required for real mouse actions.
    - Coordinate validation against screen bounds.
    - Maximum action count limit.
    - Action logging.
    - Emergency stop via Ctrl+C / moving mouse to corner (FAILSAFE).
    """
    
    def __init__(
        self,
        enabled: bool = False,
        dry_run: bool = True,
        max_actions: int = 0,  # 0 or negative means unlimited
        monitor_bounds: Optional[dict] = None,
    ) -> None:
        self.enabled = enabled
        self.dry_run = dry_run
        self.max_actions = max_actions  # <= 0 means unlimited
        self.monitor_bounds = monitor_bounds
        self._action_count = 0
        self._action_log: List[MouseAction] = []
        
        if enabled and not PYAUTOGUI_AVAILABLE:
            raise ImportError(
                "pyautogui is not installed. Install with: pip install pyautogui"
            )
        
        if enabled and not dry_run:
            logger.warning(
                "Mouse controller enabled in LIVE mode. "
                "Move mouse to screen corner to emergency stop."
            )
    
    def _validate_coordinates(self, x: int, y: int) -> List[str]:
        """Validate coordinates against screen bounds."""
        errors = []
        if x < 0:
            errors.append(f"X coordinate must be non-negative, got {x}")
        if y < 0:
            errors.append(f"Y coordinate must be non-negative, got {y}")
        
        if self.monitor_bounds:
            max_x = self.monitor_bounds.get("left", 0) + self.monitor_bounds.get("width", 0)
            max_y = self.monitor_bounds.get("top", 0) + self.monitor_bounds.get("height", 0)
            if x >= max_x:
                errors.append(f"X coordinate {x} exceeds monitor boundary {max_x}")
            if y >= max_y:
                errors.append(f"Y coordinate {y} exceeds monitor boundary {max_y}")
        elif PYAUTOGUI_AVAILABLE:
            try:
                screen_w, screen_h = pyautogui.size()
                if x >= screen_w:
                    errors.append(f"X coordinate {x} exceeds screen width {screen_w}")
                if y >= screen_h:
                    errors.append(f"Y coordinate {y} exceeds screen height {screen_h}")
            except Exception:
                pass
        
        return errors
    
    def _check_action_limit(self) -> None:
        """Check if the action limit has been reached. Ignored if max_actions <= 0."""
        if self.max_actions > 0 and self._action_count >= self.max_actions:
            raise MouseControllerError(
                f"Maximum action count ({self.max_actions}) reached. "
                f"Increase max_actions or restart the controller."
            )
    
    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
    ) -> MouseAction:
        """Click at the specified coordinates."""
        action = MouseAction(
            action_type="click",
            x=x,
            y=y,
            button=button,
            dry_run=self.dry_run,
            timestamp=time.time(),
        )
        
        if not self.enabled:
            action.error = "Mouse controller is not enabled"
            self._action_log.append(action)
            raise MouseControllerError("Mouse controller is not enabled. Set --mouse-enabled.")
        
        coord_errors = self._validate_coordinates(x, y)
        if coord_errors:
            action.error = "; ".join(coord_errors)
            self._action_log.append(action)
            raise MouseControllerError(f"Invalid coordinates: {action.error}")
        
        if button not in ("left", "right", "middle"):
            action.error = f"Invalid button: {button}"
            self._action_log.append(action)
            raise MouseControllerError(f"Invalid mouse button: {button}")
        
        self._check_action_limit()
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Click at ({x}, {y}) button={button}")
            action.executed = False
            self._action_log.append(action)
            self._action_count += 1
            return action
        
        try:
            pyautogui.click(x=x, y=y, button=button)
            action.executed = True
            logger.info(f"Clicked at ({x}, {y}) button={button}")
        except Exception as e:
            action.error = str(e)
            logger.error(f"Click failed at ({x}, {y}): {e}")
        
        self._action_log.append(action)
        self._action_count += 1
        return action
    
    def move(
        self,
        x: int,
        y: int,
        duration: float = 0.3,
    ) -> MouseAction:
        """Move the mouse to specified coordinates."""
        action = MouseAction(
            action_type="move",
            x=x,
            y=y,
            dry_run=self.dry_run,
            timestamp=time.time(),
        )
        
        if not self.enabled:
            action.error = "Mouse controller is not enabled"
            self._action_log.append(action)
            raise MouseControllerError("Mouse controller is not enabled.")
        
        coord_errors = self._validate_coordinates(x, y)
        if coord_errors:
            action.error = "; ".join(coord_errors)
            self._action_log.append(action)
            raise MouseControllerError(f"Invalid coordinates: {action.error}")
        
        self._check_action_limit()
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Move to ({x}, {y})")
            action.executed = False
            self._action_log.append(action)
            self._action_count += 1
            return action
        
        try:
            pyautogui.moveTo(x=x, y=y, duration=duration)
            action.executed = True
            logger.info(f"Moved to ({x}, {y})")
        except Exception as e:
            action.error = str(e)
            logger.error(f"Move failed to ({x}, {y}): {e}")
        
        self._action_log.append(action)
        self._action_count += 1
        return action
    
    @property
    def action_log(self) -> List[MouseAction]:
        """Get the action log."""
        return list(self._action_log)
    
    @property
    def action_count(self) -> int:
        """Get the current action count."""
        return self._action_count
    
    @property
    def remaining_actions(self) -> float:
        """Get remaining allowed actions count (inf if unlimited)."""
        if self.max_actions <= 0:
            return float("inf")
        return max(0, self.max_actions - self._action_count)
    
    def reset_count(self) -> None:
        """Reset action counter."""
        self._action_count = 0
        logger.debug("Action count reset")
    
    def format_log(self) -> str:
        """Format action log for display."""
        if not self._action_log:
            return "No mouse actions recorded."
        lines = [f"Mouse action log ({len(self._action_log)} actions):"]
        for i, action in enumerate(self._action_log, 1):
            lines.append(f"  {i}. {action}")
        return "\n".join(lines)

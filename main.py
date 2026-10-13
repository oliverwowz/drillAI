"""DrillAI - Fullscreen AI Desktop Automation for Windows.

Main entry point and CLI interface.
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure the project directory is in the path
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import AppConfig, load_config, parse_region, VERSION, APP_NAME
from logger import setup_logging, get_logger


def print_banner() -> None:
    """Print the application banner."""
    banner = f"""====================================
           {APP_NAME} v{VERSION}
===================================="""
    print(banner)


def cmd_doctor(config: AppConfig, args: argparse.Namespace) -> int:
    """Run environment diagnostics."""
    print_banner()
    print("[INFO] Running environment diagnostics...\n")
    
    issues = []
    
    # Python version
    py_ver = sys.version.split()[0]
    print(f"[CHECK] Python version: {py_ver}")
    if sys.version_info < (3, 9):
        issues.append("Python 3.9+ is required")
        print("  [FAIL] Python 3.9+ required")
    else:
        print("  [OK] Python version compatible")
    
    # Check dependencies
    deps = [
        ("mss", "mss"),
        ("PIL", "Pillow"),
        ("cv2", "opencv-python"),
        ("pyautogui", "pyautogui"),
        ("dotenv", "python-dotenv"),
        ("google.genai", "google-genai"),
    ]
    print("\n[CHECK] Dependencies:")
    for mod_name, pkg_name in deps:
        try:
            __import__(mod_name)
            print(f"  [OK] {pkg_name}")
        except ImportError:
            print(f"  [FAIL] {pkg_name} - NOT INSTALLED")
            issues.append(f"{pkg_name} is not installed")
    
    # pywin32 check
    try:
        import win32api  # noqa
        print("  [OK] pywin32")
    except ImportError:
        print("  [INFO] pywin32 - Not installed (optional on this platform)")
    
    # API key check
    print("\n[CHECK] API Configuration:")
    if config.gemini_api_key:
        masked_key = (
            config.gemini_api_key[:4] + "..." + config.gemini_api_key[-4:]
            if len(config.gemini_api_key) > 8
            else "***"
        )
        print(f"  [OK] GEMINI_API_KEY is configured ({masked_key})")
    else:
        print("  [WARN] GEMINI_API_KEY is NOT set")
        issues.append("GEMINI_API_KEY not configured")
    
    print(f"  Model: {config.gemini_model}")
    
    # Test Gemini connectivity if requested
    if getattr(args, "test_api", False) and config.gemini_api_key:
        print("\n[CHECK] Gemini API connectivity:")
        try:
            from gemini_client import GeminiClient
            client = GeminiClient(
                api_key=config.gemini_api_key,
                model_name=config.gemini_model,
            )
            health = client.health_check()
            if health.get("model_available"):
                print(f"  [OK] Model '{config.gemini_model}' is available")
            else:
                err_msg = health.get("error", "Unknown error")
                print(f"  [FAIL] Model check failed: {err_msg}")
                issues.append(f"Model not available: {err_msg}")
        except Exception as e:
            print(f"  [FAIL] API connection failed: {e}")
            issues.append(f"API connection failed: {e}")
    
    # Directories check
    print("\n[CHECK] Directories:")
    for dir_name, dir_path in [("Logs", config.log_dir), ("Results", config.results_dir)]:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            test_file = dir_path / ".write_test"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            print(f"  [OK] {dir_name}: {dir_path}")
        except OSError as e:
            print(f"  [FAIL] {dir_name}: {dir_path} - {e}")
            issues.append(f"{dir_name} directory not writable")
    
    # Config validation
    print("\n[CHECK] Configuration:")
    config_errors = config.validate()
    if config_errors:
        for err in config_errors:
            print(f"  [FAIL] {err}")
            issues.append(err)
    else:
        print("  [OK] Configuration is valid")
    
    print("\n" + "=" * 40)
    if issues:
        print(f"Found {len(issues)} issue(s):")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return 1
    else:
        print("All checks passed! [OK]")
        return 0


def cmd_monitors(config: AppConfig, args: argparse.Namespace) -> int:
    """List available monitors."""
    print_banner()
    try:
        from monitor_manager import MonitorManager
        mm = MonitorManager()
        print(mm.format_monitor_list())
        print("\nNote: Index 0 = combined virtual desktop, 1 = primary monitor, 2+ = secondary monitors")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to enumerate monitors: {e}")
        return 1


def cmd_preview(config: AppConfig, args: argparse.Namespace) -> int:
    """Capture and save/display a screenshot preview."""
    print_banner()
    log = get_logger("preview")
    
    try:
        from screenshot import ScreenshotCapture
        
        capture = ScreenshotCapture()
        monitor_idx = getattr(args, "monitor", None)
        if monitor_idx is None:
            monitor_idx = config.monitor_index
        
        region = None
        region_str = getattr(args, "region", None)
        if region_str:
            region = parse_region(region_str)
            print(f"[INFO] Using region: {region}")
        
        print(f"[INFO] Capturing monitor {monitor_idx}...")
        image = capture.capture_with_roi(monitor_idx, region)
        
        save_path = getattr(args, "output", None)
        if save_path:
            out_file = Path(save_path)
        else:
            out_file = BASE_DIR / "preview.png"
        
        capture.save_screenshot(image, out_file)
        print(f"[INFO] Preview saved to: {out_file}")
        print(f"[INFO] Image size: {image.width}x{image.height}")
        
        if getattr(args, "show", True) and sys.platform == "win32":
            try:
                os.startfile(str(out_file))
            except Exception:
                pass
        
        return 0
    except Exception as e:
        print(f"[ERROR] Preview failed: {e}")
        log.error(f"Preview failed: {e}", exc_info=config.debug)
        return 1


def cmd_history(config: AppConfig, args: argparse.Namespace) -> int:
    """Show analysis history."""
    print_banner()
    try:
        from storage import AnalysisStorage
        storage = AnalysisStorage(db_path=config.results_dir / "drillai.db")
        limit = getattr(args, "limit", 20)
        results = storage.get_recent(limit)
        print(storage.format_results(results))
        print(f"\nTotal stored results: {storage.get_count()}")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to query history: {e}")
        return 1


def cmd_start(config: AppConfig, args: argparse.Namespace) -> int:
    """Start the monitoring loop."""
    log = get_logger("main")
    print_banner()
    
    # Command-line overrides
    if getattr(args, "monitor", None) is not None:
        config.monitor_index = args.monitor
    if getattr(args, "interval", None) is not None:
        config.screenshot_interval = args.interval
    if getattr(args, "threshold", None) is not None:
        config.change_threshold = args.threshold
    if getattr(args, "cooldown", None) is not None:
        config.api_cooldown = args.cooldown
    if getattr(args, "region", None):
        config.region = parse_region(args.region)
        config.region_enabled = True
    
    dry_run = getattr(args, "dry_run", False)
    
    errors = config.validate()
    if errors:
        for err in errors:
            print(f"[ERROR] {err}")
        return 1
    
    if not dry_run:
        try:
            config.require_api_key()
        except ValueError as e:
            print(f"[ERROR] {e}")
            return 1
    
    try:
        from screenshot import ScreenshotCapture
        from screen_detector import ScreenChangeDetector
        from vision import check_image_quality
        from storage import AnalysisStorage
    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        return 1
    
    print("[INFO] Initializing configuration")
    
    try:
        capture = ScreenshotCapture()
    except Exception as e:
        print(f"[ERROR] Screenshot system initialization failed: {e}")
        return 1

    detector = ScreenChangeDetector(
        change_threshold=config.change_threshold,
        api_cooldown=config.api_cooldown,
    )
    storage = AnalysisStorage(db_path=config.results_dir / "drillai.db")
    
    solver = None
    if not dry_run:
        try:
            from gemini_client import GeminiClient
            from solver import QuestionSolver
            
            gemini_client = GeminiClient(
                api_key=config.gemini_api_key,
                model_name=config.gemini_model,
            )
            print("[INFO] Gemini client initialized")
            solver = QuestionSolver(gemini_client=gemini_client)
        except Exception as e:
            print(f"[ERROR] Failed to initialize Gemini: {e}")
            return 1
    else:
        print("[INFO] Running in DRY-RUN mode (no Gemini API calls)")
    
    mon = None
    try:
        from monitor_manager import MonitorManager
        mm = MonitorManager()
        mon = mm.get_monitor(config.monitor_index)
        print(f"[INFO] Selected monitor: {mon}")
    except Exception as e:
        print(f"[WARNING] Selected monitor index: {config.monitor_index} ({e})")
    
    # Initialize mouse controller
    mouse_controller = None
    mouse_enabled = getattr(args, "mouse_enabled", False) or config.mouse_enabled
    mouse_live = getattr(args, "mouse_live", False) or (not config.mouse_dry_run)
    auto_click = getattr(args, "auto_click", False) or config.auto_click
    raw_max = getattr(args, "max_mouse_actions", None)
    max_actions = raw_max if (raw_max is not None and raw_max != 0) else config.max_mouse_actions
    
    if mouse_enabled:
        try:
            from mouse_controller import MouseController
            mon_bounds = mon.bounds if mon else None
            mouse_controller = MouseController(
                enabled=True,
                dry_run=not mouse_live,
                max_actions=max_actions,
                monitor_bounds=mon_bounds,
            )
            mode_str = "LIVE (Real Clicks)" if mouse_live else "DRY-RUN (Simulated)"
            limit_str = "Unlimited" if max_actions <= 0 else str(max_actions)
            print(f"[INFO] Mouse controller enabled: {mode_str} (max_actions={limit_str})")
            if auto_click:
                print("[INFO] Auto-click enabled: automatically clicking detected answer button")
        except Exception as e:
            print(f"[WARNING] Mouse controller initialization failed: {e}")
    
    capture_mode = "ROI" if config.region_enabled else "Fullscreen"
    print(f"[INFO] Capture mode: {capture_mode}")
    if config.region_enabled and config.region:
        print(f"[INFO] Region: {config.region}")
    print(f"[INFO] Screenshot interval: {config.screenshot_interval}s")
    print(f"[INFO] Visual change threshold: {config.change_threshold}")
    print(f"[INFO] API cooldown: {config.api_cooldown}s")
    
    shutdown_requested = False
    
    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            print("\n[WARNING] Immediate shutdown requested.")
            sys.exit(1)
        shutdown_requested = True
        print("\n[INFO] Shutdown requested, stopping monitoring loop...")
    
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal_handler)
    
    print("\n[INFO] Monitoring started (Press Ctrl+C to stop)")
    print("=" * 40)
    
    try:
        while not shutdown_requested:
            try:
                region = config.region if config.region_enabled else None
                image = capture.capture_with_roi(config.monitor_index, region)
                
                is_usable, reason = check_image_quality(image)
                if not is_usable:
                    log.debug(f"Unusable screenshot: {reason}")
                    time.sleep(config.screenshot_interval)
                    continue
                
                changed, ratio, det_reason = detector.detect_change(image)
                if not changed:
                    log.debug(f"No visual change: {det_reason}")
                    time.sleep(config.screenshot_interval)
                    continue
                
                can_send, wait_time = detector.can_send_api_request()
                if not can_send:
                    log.debug(f"API cooldown active: wait {wait_time:.1f}s")
                    time.sleep(min(wait_time, config.screenshot_interval))
                    continue
                
                print(f"\n[INFO] Significant visual change detected (ratio: {ratio:.4f})")
                print("[INFO] Screenshot prepared")
                
                img_hash = detector.compute_image_hash(image)
                
                if dry_run:
                    print(f"[INFO] [DRY-RUN] Screenshot hash: {img_hash[:16]}")
                    print("[INFO] [DRY-RUN] Skipping actual Gemini API call")
                    detector.record_api_request()
                    time.sleep(config.screenshot_interval)
                    continue
                
                print("[INFO] Analyzing image with Gemini...")
                result = solver.solve(image=image, image_hash=img_hash)
                detector.record_api_request()
                
                print("\n" + result.format_display() + "\n")
                
                # Execute controlled mouse click on detected answer
                if mouse_controller and result.question_detected and result.click_target:
                    try:
                        ct = result.click_target
                        x_pct = ct.get("x_percent", 0.0)
                        y_pct = ct.get("y_percent", 0.0)
                        
                        mon_left = mon.left if mon else 0
                        mon_top = mon.top if mon else 0
                        if config.region_enabled and config.region:
                            base_x = mon_left + config.region[0]
                            base_y = mon_top + config.region[1]
                        else:
                            base_x = mon_left
                            base_y = mon_top
                        
                        target_x = int(base_x + (image.width * (x_pct / 100.0)))
                        target_y = int(base_y + (image.height * (y_pct / 100.0)))
                        
                        print(f"[INFO] Answer target located at ({target_x}, {target_y}) for option '{result.proposed_answer}'")
                        print(f"[INFO] Moving cursor and clicking answer...")
                        
                        mouse_controller.move(target_x, target_y, duration=0.3)
                        action = mouse_controller.click(target_x, target_y, button="left")
                        if action.executed:
                            print(f"[INFO] [SUCCESS] REAL mouse click executed at ({target_x}, {target_y})!")
                        else:
                            print(f"[INFO] Mouse action recorded: {action}")
                    except Exception as me:
                        print(f"[WARNING] Mouse interaction error: {me}")
                        log.error(f"Mouse interaction error: {me}")
                
                try:
                    storage.save_result(
                        result=result.to_dict(),
                        screenshot_hash=img_hash,
                    )
                    print("[INFO] Result saved")
                except Exception as e:
                    log.error(f"Failed to save result: {e}")
                
                print("=" * 40)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"Error in monitoring loop: {e}", exc_info=config.debug)
                print(f"[ERROR] Monitoring loop error: {e}")
                time.sleep(config.screenshot_interval)
            
            time.sleep(config.screenshot_interval)
            
    except KeyboardInterrupt:
        pass
    
    print("\n[INFO] Shutting down...")
    print(f"[INFO] Changes detected: {detector.stats['changes_detected']}")
    print(f"[INFO] Duplicates suppressed: {detector.stats['duplicates_suppressed']}")
    if solver:
        print(f"[INFO] Questions analyzed: {solver.solve_count}")
    print(f"[INFO] Total stored results: {storage.get_count()}")
    print("[INFO] Shutdown complete")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="DrillAI",
        description=f"{APP_NAME} v{VERSION} - Fullscreen AI Desktop Automation for Windows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py doctor                    Run environment diagnostics
  python main.py doctor --test-api         Verify Gemini API connectivity
  python main.py monitors                  List available display monitors
  python main.py preview                   Capture screenshot preview
  python main.py preview --monitor 1       Preview specific monitor
  python main.py preview --region 100,100,800,600
  python main.py start                     Start monitoring primary monitor
  python main.py start --dry-run           Test monitoring without API calls
  python main.py start --region 200,150,1200,800
  python main.py history                   Show recent analysis results
""",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # doctor
    doctor_p = subparsers.add_parser("doctor", help="Run environment diagnostics")
    doctor_p.add_argument("--test-api", action="store_true", help="Test Gemini API connectivity")
    
    # monitors
    subparsers.add_parser("monitors", help="List available display monitors")
    
    # preview
    prev_p = subparsers.add_parser("preview", help="Capture a screenshot preview")
    prev_p.add_argument("--monitor", type=int, default=None, help="Monitor index")
    prev_p.add_argument("--region", type=str, default=None, help="Region as X,Y,WIDTH,HEIGHT")
    prev_p.add_argument("--output", "-o", type=str, default=None, help="Output image file path")
    prev_p.add_argument("--no-show", dest="show", action="store_false", help="Do not open preview image")
    
    # start
    start_p = subparsers.add_parser("start", help="Start monitoring desktop")
    start_p.add_argument("--capture", choices=["fullscreen", "region"], default="fullscreen", help="Capture mode")
    start_p.add_argument("--monitor", type=int, default=None, help="Monitor index")
    start_p.add_argument("--region", type=str, default=None, help="Region as X,Y,WIDTH,HEIGHT")
    start_p.add_argument("--interval", type=float, default=None, help="Screenshot interval (seconds)")
    start_p.add_argument("--threshold", type=float, default=None, help="Visual change threshold (0.0-1.0)")
    start_p.add_argument("--cooldown", type=float, default=None, help="API cooldown (seconds)")
    start_p.add_argument("--dry-run", action="store_true", help="Run without sending API requests")
    start_p.add_argument("--mouse-enabled", action="store_true", help="Enable mouse interaction controller")
    start_p.add_argument("--mouse-live", action="store_true", help="Execute REAL physical mouse clicks (disables dry-run)")
    start_p.add_argument("--auto-click", action="store_true", help="Automatically click detected answer buttons")
    start_p.add_argument("--max-mouse-actions", type=int, default=0, help="Maximum allowed mouse actions limit (0 for unlimited)")
    
    # history
    hist_p = subparsers.add_parser("history", help="Show saved analysis results")
    hist_p.add_argument("--limit", type=int, default=20, help="Number of records to show")
    
    return parser


def main() -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    config = load_config(base_dir=BASE_DIR)
    
    setup_logging(
        log_level=config.log_level,
        log_dir=config.log_dir,
        debug=config.debug,
    )
    
    commands = {
        "doctor": cmd_doctor,
        "monitors": cmd_monitors,
        "preview": cmd_preview,
        "start": cmd_start,
        "history": cmd_history,
    }
    
    handler = commands.get(args.command)
    if handler:
        try:
            return handler(config, args)
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
            return 0
        except Exception as e:
            print(f"\n[ERROR] {e}")
            if config.debug:
                import traceback
                traceback.print_exc()
            return 1
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

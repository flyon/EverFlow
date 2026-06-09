#!/usr/bin/env python3
"""
EverFlow headless session helper.

Run:
    python3 everflow_headless.py

Stop:
    Ctrl+C, close the terminal, or terminate the process.

The script controls the centered 33% of the main display by default.
It supports macOS and Windows without third-party Python packages.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import math
import random
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform.startswith("win")

if not (IS_MACOS or IS_WINDOWS):
    raise SystemExit("This script currently supports macOS and Windows.")

APP = None
USER32 = None
KERNEL32 = None
WIN_ENUM_WINDOWS_PROC = None


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


if IS_MACOS:
    APP = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")

    APP.CGMainDisplayID.restype = ctypes.c_uint32
    APP.CGDisplayPixelsWide.argtypes = [ctypes.c_uint32]
    APP.CGDisplayPixelsWide.restype = ctypes.c_size_t
    APP.CGDisplayPixelsHigh.argtypes = [ctypes.c_uint32]
    APP.CGDisplayPixelsHigh.restype = ctypes.c_size_t
    APP.CGEventCreate.restype = ctypes.c_void_p
    APP.CGEventGetLocation.argtypes = [ctypes.c_void_p]
    APP.CGEventGetLocation.restype = CGPoint
    APP.CFRelease.argtypes = [ctypes.c_void_p]
    APP.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
    APP.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    APP.CGEventCreateScrollWheelEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_int32,
    ]
    APP.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
    APP.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    APP.AXIsProcessTrusted.restype = ctypes.c_bool
    APP.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    APP.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double

if IS_WINDOWS:
    USER32 = ctypes.windll.user32
    KERNEL32 = ctypes.windll.kernel32
    WIN_ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    USER32.SetProcessDPIAware()
    USER32.GetSystemMetrics.argtypes = [ctypes.c_int]
    USER32.GetSystemMetrics.restype = ctypes.c_int
    USER32.GetCursorPos.argtypes = [ctypes.POINTER(WinPoint)]
    USER32.GetCursorPos.restype = ctypes.c_bool
    USER32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    USER32.SetCursorPos.restype = ctypes.c_bool
    USER32.EnumWindows.argtypes = [WIN_ENUM_WINDOWS_PROC, ctypes.c_void_p]
    USER32.EnumWindows.restype = ctypes.c_bool
    USER32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    USER32.GetWindowTextLengthW.restype = ctypes.c_int
    USER32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    USER32.GetWindowTextW.restype = ctypes.c_int
    USER32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    USER32.IsWindowVisible.restype = ctypes.c_bool
    USER32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    USER32.ShowWindow.restype = ctypes.c_bool
    USER32.GetForegroundWindow.restype = ctypes.c_void_p
    USER32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    USER32.SetForegroundWindow.restype = ctypes.c_bool
    USER32.mouse_event.argtypes = [
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_void_p,
    ]
    USER32.GetLastInputInfo.argtypes = [ctypes.POINTER(LastInputInfo)]
    USER32.GetLastInputInfo.restype = ctypes.c_bool
    KERNEL32.GetTickCount.restype = ctypes.c_uint


K_CG_EVENT_MOUSE_MOVED = 5
K_CG_EVENT_LEFT_MOUSE_DOWN = 1
K_CG_EVENT_LEFT_MOUSE_UP = 2
K_CG_MOUSE_BUTTON_LEFT = 0
K_CG_EVENT_TAP_HID = 0
K_CG_SCROLL_EVENT_UNIT_LINE = 1
K_CG_EVENT_SOURCE_STATE_COMBINED_SESSION = 0
K_CG_ANY_INPUT_EVENT_TYPE = 0xFFFFFFFF

WIN_SM_CXSCREEN = 0
WIN_SM_CYSCREEN = 1
WIN_MOUSEEVENTF_LEFTDOWN = 0x0002
WIN_MOUSEEVENTF_LEFTUP = 0x0004
WIN_MOUSEEVENTF_WHEEL = 0x0800
WIN_WHEEL_DELTA = 120
WIN_SW_RESTORE = 9


RUNNING = True
LAST_AUTOMATION_AT = 0.0


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass
class AutoPauseSchedule:
    pause_minutes: int | None = None
    auto_resume: bool = False
    jitter_minutes: int = 10
    paused_for_date: dt.date | None = None
    resumed_for_date: dt.date | None = None
    effective_pause_date: dt.date | None = None
    effective_pause_minutes: int | None = None


def stop(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def main_display_size() -> tuple[int, int]:
    if IS_MACOS:
        display = APP.CGMainDisplayID()
        return int(APP.CGDisplayPixelsWide(display)), int(APP.CGDisplayPixelsHigh(display))
    if IS_WINDOWS:
        return int(USER32.GetSystemMetrics(WIN_SM_CXSCREEN)), int(USER32.GetSystemMetrics(WIN_SM_CYSCREEN))
    raise RuntimeError("Unsupported platform.")


def default_area() -> Rect:
    width, height = main_display_size()
    area_width = width / 3.0
    area_height = height / 3.0
    return Rect(
        x=(width - area_width) / 2.0,
        y=(height - area_height) / 2.0,
        width=area_width,
        height=area_height,
    )


def current_mouse_position() -> Point:
    if IS_MACOS:
        event = APP.CGEventCreate(None)
        if not event:
            return Point(500, 500)
        location = APP.CGEventGetLocation(event)
        APP.CFRelease(event)
        return Point(location.x, location.y)
    if IS_WINDOWS:
        point = WinPoint()
        if USER32.GetCursorPos(ctypes.byref(point)):
            return Point(float(point.x), float(point.y))
        return Point(500, 500)
    raise RuntimeError("Unsupported platform.")


def post_mouse_event(kind: int, point: Point) -> None:
    if IS_MACOS:
        event = APP.CGEventCreateMouseEvent(None, kind, CGPoint(point.x, point.y), K_CG_MOUSE_BUTTON_LEFT)
        if event:
            APP.CGEventPost(K_CG_EVENT_TAP_HID, event)
            APP.CFRelease(event)
            mark_automation_activity()
        return
    if IS_WINDOWS:
        if kind == K_CG_EVENT_MOUSE_MOVED:
            USER32.SetCursorPos(int(round(point.x)), int(round(point.y)))
        elif kind == K_CG_EVENT_LEFT_MOUSE_DOWN:
            USER32.mouse_event(WIN_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
        elif kind == K_CG_EVENT_LEFT_MOUSE_UP:
            USER32.mouse_event(WIN_MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
        mark_automation_activity()
        return
    raise RuntimeError("Unsupported platform.")


def post_scroll(lines: int) -> None:
    if IS_MACOS:
        event = APP.CGEventCreateScrollWheelEvent(
            None,
            K_CG_SCROLL_EVENT_UNIT_LINE,
            1,
            int(lines),
        )
        if event:
            APP.CGEventPost(K_CG_EVENT_TAP_HID, event)
            APP.CFRelease(event)
            mark_automation_activity()
        return
    if IS_WINDOWS:
        USER32.mouse_event(WIN_MOUSEEVENTF_WHEEL, 0, 0, int(lines) * WIN_WHEEL_DELTA, None)
        mark_automation_activity()
        return
    raise RuntimeError("Unsupported platform.")


def idle_seconds() -> float:
    if IS_MACOS:
        return float(
            APP.CGEventSourceSecondsSinceLastEventType(
                K_CG_EVENT_SOURCE_STATE_COMBINED_SESSION,
                K_CG_ANY_INPUT_EVENT_TYPE,
            )
        )
    if IS_WINDOWS:
        info = LastInputInfo()
        info.cbSize = ctypes.sizeof(LastInputInfo)
        if not USER32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        elapsed_ms = (int(KERNEL32.GetTickCount()) - int(info.dwTime)) & 0xFFFFFFFF
        return max(0.0, elapsed_ms / 1000.0)
    raise RuntimeError("Unsupported platform.")


def mark_automation_activity() -> None:
    global LAST_AUTOMATION_AT
    LAST_AUTOMATION_AT = time.monotonic()


def user_activity_detected() -> bool:
    return idle_seconds() < 1.5 and (time.monotonic() - LAST_AUTOMATION_AT) > 2.0


def current_time_label() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str, silent: bool = False) -> None:
    if silent:
        return
    print(f"[{current_time_label()}] {message}", flush=True)


def run_silent_intro() -> None:
    frames = [
        "EF starting    ",
        "EF starting.   ",
        "EF starting..  ",
        "EF starting... ",
        "EF starting .. ",
        "EF starting  . ",
        "EF starting    ",
        "EF             ",
        "E              ",
        "               ",
    ]
    for frame in frames:
        sys.stdout.write("\r" + frame)
        sys.stdout.flush()
        time.sleep(0.12)
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    print("EF Running...", flush=True)


def target_app_variants(target_app: str) -> list[str]:
    normalized = target_app.strip().lower()
    aliases = {
        "code": ["Visual Studio Code"],
        "vs code": ["Visual Studio Code"],
        "vscode": ["Visual Studio Code"],
        "visual studio code": ["Visual Studio Code"],
    }
    return aliases.get(normalized, [target_app.strip()])


def capture_foreground_target() -> str | int | None:
    if IS_MACOS:
        script = 'tell application "System Events" to get name of first application process whose frontmost is true'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            foreground = result.stdout.strip()
            return foreground or None
        return None
    if IS_WINDOWS:
        hwnd = USER32.GetForegroundWindow()
        return int(hwnd) if hwnd else None
    return None


def restore_foreground_target(target: str | int | None) -> bool:
    if target is None:
        return False
    if IS_MACOS and isinstance(target, str):
        escaped_target = target.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "{escaped_target}" to activate\n'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            mark_automation_activity()
            time.sleep(0.25)
            return True
        return False
    if IS_WINDOWS and isinstance(target, int):
        USER32.ShowWindow(target, WIN_SW_RESTORE)
        time.sleep(0.1)
        restored = bool(USER32.SetForegroundWindow(target))
        if restored:
            mark_automation_activity()
            time.sleep(0.25)
        return restored
    return False


def focus_target_app(target_app: str) -> bool:
    variants = [variant for variant in target_app_variants(target_app) if variant]
    if not variants:
        return True
    if IS_MACOS:
        return focus_target_app_macos(variants)
    if IS_WINDOWS:
        return focus_target_app_windows(variants)
    return False


def focus_target_app_macos(variants: list[str]) -> bool:
    for app_name in variants:
        escaped_app_name = app_name.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            f'if application "{escaped_app_name}" is running then\n'
            f'  tell application "{escaped_app_name}" to activate\n'
            "  return true\n"
            "else\n"
            "  return false\n"
            "end if\n"
        )
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip().lower() == "true":
            mark_automation_activity()
            time.sleep(0.35)
            return True
    return False


def focus_target_app_windows(variants: list[str]) -> bool:
    lowered_variants = [variant.lower() for variant in variants]
    matches: list[tuple[int, str]] = []

    def enum_window(hwnd: int, _lparam: int) -> bool:
        if not USER32.IsWindowVisible(hwnd):
            return True
        length = USER32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        USER32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if title and any(variant in title.lower() for variant in lowered_variants):
            matches.append((hwnd, title))
        return True

    callback = WIN_ENUM_WINDOWS_PROC(enum_window)
    USER32.EnumWindows(callback, None)
    if not matches:
        return False

    hwnd, _title = matches[0]
    USER32.ShowWindow(hwnd, WIN_SW_RESTORE)
    time.sleep(0.15)
    focused = bool(USER32.SetForegroundWindow(hwnd))
    if focused:
        mark_automation_activity()
        time.sleep(0.35)
    return focused


def prove_target_app_focus(target_app: str, silent: bool = False) -> bool:
    previous = capture_foreground_target()
    log(f"Checking target app '{target_app}' at startup.", silent)
    focused = focus_target_app(target_app)
    if not focused:
        log(f"Target app check failed: '{target_app}' is not open or could not be focused.", silent)
        return False

    log(f"Target app check passed: focused '{target_app}' for 1 second.", silent)
    time.sleep(1)
    if restore_foreground_target(previous):
        log("Returned focus to the previous terminal/window after target app check.", silent)
    else:
        log("Could not automatically return focus to the previous terminal/window after target app check.", silent)
    return True


def parse_time_of_day(value: str) -> int:
    normalized = value.strip().lower().replace(" ", "")
    formats = ["%I:%M%p", "%I%p", "%H:%M", "%H%M", "%H"]
    for time_format in formats:
        try:
            parsed = dt.datetime.strptime(normalized, time_format).time()
            return parsed.hour * 60 + parsed.minute
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("Use a local time like 6pm, 6:30pm, 18:00, or 1800.")


def format_minutes(minutes: int) -> str:
    minutes = minutes % (24 * 60)
    hour = minutes // 60
    minute = minutes % 60
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12
    if minute == 0:
        return f"{display_hour}{suffix}"
    return f"{display_hour}:{minute:02d}{suffix}"


def effective_pause_minutes(schedule: AutoPauseSchedule, today: dt.date | None = None) -> int:
    if schedule.pause_minutes is None:
        raise ValueError("pause_minutes is required")
    today = today or dt.date.today()
    if schedule.effective_pause_date != today or schedule.effective_pause_minutes is None:
        jitter = random.randint(-schedule.jitter_minutes, schedule.jitter_minutes)
        schedule.effective_pause_date = today
        schedule.effective_pause_minutes = (schedule.pause_minutes + jitter) % (24 * 60)
    return schedule.effective_pause_minutes


def should_auto_pause(schedule: AutoPauseSchedule | None) -> bool:
    if schedule is None or schedule.pause_minutes is None:
        return False

    now = dt.datetime.now()
    today = now.date()
    current_minutes = now.hour * 60 + now.minute
    pause_minutes = effective_pause_minutes(schedule, today)

    if schedule.paused_for_date is not None and schedule.resumed_for_date != schedule.paused_for_date:
        return True

    if current_minutes < pause_minutes:
        return False
    if schedule.paused_for_date == today:
        return False
    return True


def wait_for_auto_resume(schedule: AutoPauseSchedule, silent: bool = False) -> None:
    today = dt.date.today()
    pause_minutes = effective_pause_minutes(schedule, today)
    if schedule.paused_for_date != today:
        schedule.paused_for_date = today
        log(
            f"Pausing activity because today's auto-pause time {format_minutes(pause_minutes)} has passed.",
            silent,
        )

    if not schedule.auto_resume:
        log("Waiting because auto-resume is disabled; activity will remain paused for this schedule window.", silent)
        while RUNNING and should_auto_pause(schedule):
            time.sleep(1)
        return

    log(
        "Waiting to resume because --autoResume is enabled; activity remains paused until user input is detected in the next pre-pause window.",
        silent,
    )
    while RUNNING and should_auto_pause(schedule):
        now = dt.datetime.now()
        current_minutes = now.hour * 60 + now.minute
        pause_minutes = effective_pause_minutes(schedule, now.date())
        is_after_pause_day = schedule.paused_for_date is not None and now.date() > schedule.paused_for_date
        is_before_pause_time = current_minutes < pause_minutes
        if is_after_pause_day and is_before_pause_time and user_activity_detected():
            schedule.resumed_for_date = schedule.paused_for_date
            mark_automation_activity()
            log("Resuming activity because user input was detected after the overnight scheduled pause.", silent)
            return
        time.sleep(0.5)


def sleep_interruptible(seconds: float, stop_on_user_activity: bool = False) -> bool:
    deadline = time.monotonic() + seconds
    while RUNNING and time.monotonic() < deadline:
        if stop_on_user_activity and user_activity_detected():
            return False
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    return RUNNING


def random_point(rect: Rect) -> Point:
    inset_x = min(rect.width * 0.08, 20)
    inset_y = min(rect.height * 0.08, 20)
    return Point(
        random.uniform(rect.x + inset_x, rect.x + rect.width - inset_x),
        random.uniform(rect.y + inset_y, rect.y + rect.height - inset_y),
    )


def cubic_bezier(start: Point, a: Point, b: Point, end: Point, t: float) -> Point:
    mt = 1.0 - t
    return Point(
        mt**3 * start.x + 3 * mt**2 * t * a.x + 3 * mt * t**2 * b.x + t**3 * end.x,
        mt**3 * start.y + 3 * mt**2 * t * a.y + 3 * mt * t**2 * b.y + t**3 * end.y,
    )


def ease_in_out(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    return 1 - ((-2 * t + 2) ** 3) / 2


def natural_path(start: Point, end: Point) -> list[Point]:
    distance = math.hypot(end.x - start.x, end.y - start.y)
    steps = max(28, min(140, math.ceil(distance / random.uniform(10, 22))))
    wander = random.uniform(95, 220) if random.random() < 0.28 else random.uniform(28, 85)
    control_a = Point(
        start.x + (end.x - start.x) * random.uniform(0.12, 0.46) + random.uniform(-wander, wander),
        start.y + (end.y - start.y) * random.uniform(0.12, 0.46) + random.uniform(-wander, wander),
    )
    control_b = Point(
        start.x + (end.x - start.x) * random.uniform(0.54, 0.88) + random.uniform(-wander, wander),
        start.y + (end.y - start.y) * random.uniform(0.54, 0.88) + random.uniform(-wander, wander),
    )

    points: list[Point] = []
    for index in range(1, steps + 1):
        t = index / steps
        eased = ease_in_out(t)
        jitter = (1 - abs(2 * t - 1)) * random.uniform(2.0, 8.5)
        point = cubic_bezier(start, control_a, control_b, end, eased)
        points.append(Point(point.x + random.uniform(-jitter, jitter), point.y + random.uniform(-jitter, jitter)))
    return points


def erratic_step_delays(step_count: int, total_ms: int) -> list[float]:
    if step_count <= 0:
        return []
    weights: list[float] = []
    for index in range(step_count):
        progress = index / step_count
        edge_slowdown = 0.75 + abs(2 * progress - 1) * 1.8
        hesitation = random.uniform(2.5, 6.5) if random.random() < 0.08 else 1.0
        weights.append(edge_slowdown * hesitation * random.uniform(0.35, 1.9))
    total_weight = sum(weights)
    return [(weight / total_weight) * total_ms / 1000.0 for weight in weights]


def move_naturally(target: Point) -> None:
    start = current_mouse_position()
    path = natural_path(start, target)
    total_ms = random.randint(500, 4000)
    delays = erratic_step_delays(len(path), total_ms)
    for point, delay in zip(path, delays):
        if not RUNNING:
            return
        if user_activity_detected():
            return
        post_mouse_event(K_CG_EVENT_MOUSE_MOVED, point)
        if not sleep_interruptible(delay, stop_on_user_activity=True):
            return


def click() -> None:
    point = current_mouse_position()
    post_mouse_event(K_CG_EVENT_LEFT_MOUSE_DOWN, point)
    sleep_interruptible(random.uniform(0.045, 0.13))
    post_mouse_event(K_CG_EVENT_LEFT_MOUSE_UP, point)


def smooth_scroll(total_lines: int) -> None:
    direction = 1 if total_lines > 0 else -1
    remaining = abs(total_lines)
    steps: list[int] = []
    while remaining > 0:
        max_pulse = min(remaining, 3 if random.random() < 0.25 else 2)
        pulse = random.randint(1, max_pulse)
        steps.append(direction * pulse)
        remaining -= pulse

    for index, step in enumerate(steps):
        if not RUNNING:
            return
        if user_activity_detected():
            return
        post_scroll(step)
        tail = 0.028 if index + 2 >= len(steps) else 0.0
        if not sleep_interruptible(random.uniform(0.022, 0.072) + tail, stop_on_user_activity=True):
            return


def choose_actions() -> list[str]:
    actions = ["move"]
    roll = random.randrange(100)
    if roll < 30:
        return actions
    if roll >= 78:
        if random.random() < 0.5:
            actions.extend(["click", "scroll"])
        else:
            actions.extend(["scroll", "click"])
        return actions
    actions.append("scroll" if random.random() < 0.6 else "click")
    return actions


def next_scroll_amount(direction: int) -> int:
    magnitude = random.randint(14, 32) if random.random() < 0.22 else random.randint(4, 13)
    return direction * magnitude


def run(
    area: Rect,
    min_interval_ms: int = 2500,
    max_interval_ms: int = 7000,
    idle_threshold_seconds: int = 180,
    schedule: AutoPauseSchedule | None = None,
    silent: bool = False,
    target_app: str | None = None,
) -> None:
    if IS_MACOS and not APP.AXIsProcessTrusted():
        print("Accessibility permission is not enabled.")
        print("Enable it for Terminal/iTerm in System Settings > Privacy & Security > Accessibility.")
        raise SystemExit(1)

    scroll_direction = 1 if random.random() < 0.5 else -1
    platform_name = "macOS" if IS_MACOS else "Windows"
    if silent:
        run_silent_intro()
    log(f"EverFlow headless armed on {platform_name}.", silent)
    log(f"Using area x={area.x:.0f}, y={area.y:.0f}, w={area.width:.0f}, h={area.height:.0f}.", silent)
    log(f"Waiting for inactivity; activity starts after {idle_threshold_seconds} idle seconds.", silent)
    if schedule and schedule.pause_minutes is not None:
        resume_text = " and resumes on user activity" if schedule.auto_resume else ""
        todays_pause = effective_pause_minutes(schedule)
        log(
            f"Scheduled pause is centered on {format_minutes(schedule.pause_minutes)} "
            f"with +/-{schedule.jitter_minutes}m jitter; today's pause time is {format_minutes(todays_pause)}{resume_text}.",
            silent,
        )
    if target_app:
        log(f"Target app guard is enabled for '{target_app}'; activity will pause if it cannot be focused.", silent)
        prove_target_app_focus(target_app, silent)
    log("Stop with Ctrl+C or close this terminal.", silent)

    while RUNNING:
        if should_auto_pause(schedule):
            wait_for_auto_resume(schedule, silent)
            continue
        log("Waiting because activity has not reached the idle threshold yet.", silent)
        while RUNNING and idle_seconds() < idle_threshold_seconds:
            if should_auto_pause(schedule):
                wait_for_auto_resume(schedule, silent)
                break
            time.sleep(1)
        if not RUNNING:
            break
        if should_auto_pause(schedule):
            continue

        if target_app and not focus_target_app(target_app):
            log(f"Pausing activity because target app '{target_app}' is not open or could not be focused.", silent)
            sleep_interruptible(30, stop_on_user_activity=True)
            continue

        log(f"Starting activity because idle threshold reached; idle={idle_seconds():.1f}s.", silent)
        mark_automation_activity()
        while RUNNING:
            if should_auto_pause(schedule):
                wait_for_auto_resume(schedule, silent)
                break
            wait_ms = random.randint(min_interval_ms, max(max_interval_ms, min_interval_ms + 250))
            if not sleep_interruptible(wait_ms / 1000.0, stop_on_user_activity=True):
                log("Pausing activity because user input was detected during the wait interval.", silent)
                break
            if not RUNNING:
                break
            if should_auto_pause(schedule):
                wait_for_auto_resume(schedule, silent)
                break

            if target_app and not focus_target_app(target_app):
                log(f"Pausing activity because target app '{target_app}' is no longer focusable.", silent)
                sleep_interruptible(30, stop_on_user_activity=True)
                break

            target = random_point(area)
            actions = choose_actions()
            move_naturally(target)
            if user_activity_detected():
                log("Pausing activity because user input was detected during mouse movement.", silent)
                break

            for action in actions[1:]:
                if not RUNNING:
                    break
                if should_auto_pause(schedule):
                    wait_for_auto_resume(schedule, silent)
                    break
                if not sleep_interruptible(0.12, stop_on_user_activity=True):
                    log(f"Pausing activity because user input was detected before {action}.", silent)
                    break
                if action == "click":
                    click()
                elif action == "scroll":
                    amount = next_scroll_amount(scroll_direction)
                    scroll_direction *= -1
                    smooth_scroll(amount)
            if user_activity_detected():
                log("Pausing activity because user input was detected after activity tick.", silent)
                break

    log("Stopping because the process received a stop signal.", silent)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EverFlow headless session helper.")
    parser.add_argument(
        "--autoPause",
        "--auto-pause",
        dest="auto_pause",
        type=parse_time_of_day,
        help="Pause automation after this local time, for example 6pm, 18:00, or 1830.",
    )
    parser.add_argument(
        "--autoResume",
        "--auto-resume",
        dest="auto_resume",
        action="store_true",
        help="After auto-pause, resume when real user activity is detected.",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Show a brief startup animation, clear the terminal, then keep only a minimal running message.",
    )
    parser.add_argument(
        "--pauseJitterMinutes",
        "--pause-jitter-minutes",
        dest="pause_jitter_minutes",
        type=int,
        default=10,
        help="Randomize the daily auto-pause time by this many minutes in either direction. Default: 10.",
    )
    parser.add_argument(
        "--targetApp",
        "--target-app",
        dest="target_app",
        help="Focus this app before activity. Use 'vscode', 'vs code', or 'Visual Studio Code' for VS Code.",
    )
    argv = sys.argv[1:]
    if argv and argv[0] == "--":
        argv = argv[1:]
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    run(
        default_area(),
        schedule=AutoPauseSchedule(
            pause_minutes=args.auto_pause,
            auto_resume=args.auto_resume,
            jitter_minutes=max(0, args.pause_jitter_minutes),
        ),
        silent=args.silent,
        target_app=args.target_app,
    )

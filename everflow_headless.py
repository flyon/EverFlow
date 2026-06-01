#!/usr/bin/env python3
"""
EverFlow headless macOS automation.

Run:
    python3 everflow_headless.py

Stop:
    Ctrl+C, close the terminal, or terminate the process.

The script controls the centered 33% of the main display by default and
randomly performs move-only, click, scroll, and click/scroll combinations.
macOS Accessibility permission is required for the terminal app running it.
"""

from __future__ import annotations

import ctypes
import math
import random
import signal
import sys
import time
from dataclasses import dataclass
from typing import Iterable


if sys.platform != "darwin":
    raise SystemExit("This script is macOS-only.")


APP = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class CGRect(ctypes.Structure):
    _fields_ = [("origin", CGPoint), ("size", CGPoint)]


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


K_CG_EVENT_MOUSE_MOVED = 5
K_CG_EVENT_LEFT_MOUSE_DOWN = 1
K_CG_EVENT_LEFT_MOUSE_UP = 2
K_CG_MOUSE_BUTTON_LEFT = 0
K_CG_EVENT_TAP_HID = 0
K_CG_SCROLL_EVENT_UNIT_LINE = 1
K_CG_EVENT_SOURCE_STATE_COMBINED_SESSION = 0
K_CG_ANY_INPUT_EVENT_TYPE = 0xFFFFFFFF


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


def stop(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def main_display_size() -> tuple[int, int]:
    display = APP.CGMainDisplayID()
    return int(APP.CGDisplayPixelsWide(display)), int(APP.CGDisplayPixelsHigh(display))


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
    event = APP.CGEventCreate(None)
    if not event:
        return Point(500, 500)
    location = APP.CGEventGetLocation(event)
    APP.CFRelease(event)
    return Point(location.x, location.y)


def post_mouse_event(kind: int, point: Point) -> None:
    event = APP.CGEventCreateMouseEvent(None, kind, CGPoint(point.x, point.y), K_CG_MOUSE_BUTTON_LEFT)
    if event:
        APP.CGEventPost(K_CG_EVENT_TAP_HID, event)
        APP.CFRelease(event)
        mark_automation_activity()


def post_scroll(lines: int) -> None:
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


def idle_seconds() -> float:
    return float(
        APP.CGEventSourceSecondsSinceLastEventType(
            K_CG_EVENT_SOURCE_STATE_COMBINED_SESSION,
            K_CG_ANY_INPUT_EVENT_TYPE,
        )
    )


def mark_automation_activity() -> None:
    global LAST_AUTOMATION_AT
    LAST_AUTOMATION_AT = time.monotonic()


def user_activity_detected() -> bool:
    return idle_seconds() < 1.5 and (time.monotonic() - LAST_AUTOMATION_AT) > 2.0


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
) -> None:
    if not APP.AXIsProcessTrusted():
        print("Accessibility permission is not enabled.")
        print("Enable it for Terminal/iTerm in System Settings > Privacy & Security > Accessibility.")
        raise SystemExit(1)

    scroll_direction = 1 if random.random() < 0.5 else -1
    print(f"EverFlow headless armed. Area: x={area.x:.0f}, y={area.y:.0f}, w={area.width:.0f}, h={area.height:.0f}")
    print(f"Auto-starts after {idle_threshold_seconds} seconds of inactivity.")
    print("Stop with Ctrl+C or close this terminal.")

    while RUNNING:
        while RUNNING and idle_seconds() < idle_threshold_seconds:
            time.sleep(1)
        if not RUNNING:
            break

        print("Inactive threshold reached; automation active.")
        mark_automation_activity()
        while RUNNING:
            wait_ms = random.randint(min_interval_ms, max(max_interval_ms, min_interval_ms + 250))
            if not sleep_interruptible(wait_ms / 1000.0, stop_on_user_activity=True):
                print("User activity detected; automation paused.")
                break
            if not RUNNING:
                break

            target = random_point(area)
            move_naturally(target)
            if user_activity_detected():
                print("User activity detected; automation paused.")
                break

            for action in choose_actions()[1:]:
                if not RUNNING:
                    break
                if not sleep_interruptible(0.12, stop_on_user_activity=True):
                    print("User activity detected; automation paused.")
                    break
                if action == "click":
                    click()
                elif action == "scroll":
                    amount = next_scroll_amount(scroll_direction)
                    scroll_direction *= -1
                    smooth_scroll(amount)
            if user_activity_detected():
                print("User activity detected; automation paused.")
                break


if __name__ == "__main__":
    run(default_area())

# ============================================================
#  controller.py — virtual Xbox 360 gamepad via vgamepad
#
#  Keyboard injection (pyautogui, SendInput, PostMessage) all
#  fail against RetroArch because its input stack (SDL2/dinput/
#  winraw) sits below the Windows message layer.
#
#  A virtual gamepad created with ViGEmBus IS treated as real
#  hardware — RetroArch sees it the same as a physical Xbox pad.
#
#  Requirements:
#    1. Install ViGEmBus driver:
#       https://github.com/nefarius/ViGEmBus/releases/latest
#    2. pip install vgamepad
# ============================================================

import time
import ctypes
import ctypes.wintypes

try:
    import vgamepad as vg
    _VGAMEPAD_OK = True
except ImportError:
    _VGAMEPAD_OK = False

from config import RETROARCH_WINDOW_TITLE

_user32    = ctypes.windll.user32
SW_RESTORE = 9

# ---------------------------------------------------------------------------
# GBA button  →  Xbox 360 button
#
# RetroArch mGBA default autoconfig maps:
#   GBA A  →  Xbox A (east face)
#   GBA B  →  Xbox B (south face)... wait, no:
#   mGBA core uses RetroPad layout:
#     GBA A  = RetroPad A  = Xbox A
#     GBA B  = RetroPad B  = Xbox B
#   Start/Select/Dpad map directly.
# ---------------------------------------------------------------------------
_BTN_MAP: dict = {}   # populated after vgamepad import check

if _VGAMEPAD_OK:
    _BTN_MAP = {
        "A":      vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "B":      vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "START":  vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
        "SELECT": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        "UP":     vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        "DOWN":   vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        "LEFT":   vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        "RIGHT":  vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        "L":      vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        "R":      vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    }

# Module-level gamepad instance — created once, reused forever
_gamepad = None


def _get_gamepad():
    global _gamepad
    if not _VGAMEPAD_OK:
        raise RuntimeError(
            "vgamepad not installed.\n"
            "  1. Install ViGEmBus: https://github.com/nefarius/ViGEmBus/releases/latest\n"
            "  2. pip install vgamepad"
        )
    if _gamepad is None:
        print("[Controller] Creating virtual Xbox 360 gamepad...")
        _gamepad = vg.VX360Gamepad()
        time.sleep(0.8)   # give RetroArch time to detect it
        print("[Controller] Virtual gamepad ready.")
    return _gamepad


# ---------------------------------------------------------------------------
# Window focus (still useful so RetroArch renders at full speed)
# ---------------------------------------------------------------------------
def _find_retroarch_hwnd():
    result = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(hwnd, _):
        length = _user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, buf, length + 1)
            if RETROARCH_WINDOW_TITLE.lower() in buf.value.lower():
                result.append(hwnd)
        return True
    _user32.EnumWindows(EnumProc(_cb), 0)
    return result[0] if result else None


def focus_retroarch() -> bool:
    """Bring RetroArch to the foreground (for rendering, not input)."""
    hwnd = _find_retroarch_hwnd()
    if not hwnd:
        print("[Controller] RetroArch window not found.")
        return False
    _user32.ShowWindow(hwnd, SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
    _user32.BringWindowToTop(hwnd)
    time.sleep(0.2)
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def press(action: str, delay: float = 0.08):
    """Press and release a single button."""
    key = action.strip().upper()
    btn = _BTN_MAP.get(key)
    if btn is None:
        print(f"[Controller] Unknown action: {action}")
        return
    pad = _get_gamepad()
    pad.press_button(button=btn)
    pad.update()
    time.sleep(delay)
    pad.release_button(button=btn)
    pad.update()
    time.sleep(0.05)


def hold(action: str, duration: float = 0.5):
    """Hold a button for `duration` seconds then release."""
    key = action.strip().upper()
    btn = _BTN_MAP.get(key)
    if btn is None:
        print(f"[Controller] Unknown action: {action}")
        return
    pad = _get_gamepad()
    pad.press_button(button=btn)
    pad.update()
    time.sleep(duration)
    pad.release_button(button=btn)
    pad.update()


def sequence(actions: list, delay: float = 0.15):
    """Press each button in order with `delay` between presses."""
    pad = _get_gamepad()
    for action in actions:
        key = action.strip().upper()
        btn = _BTN_MAP.get(key)
        if btn is None:
            print(f"[Controller] Unknown action: {action}")
            continue
        pad.press_button(button=btn)
        pad.update()
        time.sleep(0.08)
        pad.release_button(button=btn)
        pad.update()
        time.sleep(delay)


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
def test_input():
    print("[Controller] Initialising virtual gamepad...")
    pad = _get_gamepad()
    print("[Controller] Sending DOWN in 2 seconds — watch the game...")
    time.sleep(2)
    press("DOWN")
    time.sleep(0.4)
    print("[Controller] Sending A...")
    press("A")
    print("[Controller] Done — did anything move or respond?")


if __name__ == "__main__":
    test_input()

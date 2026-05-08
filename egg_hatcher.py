# ============================================================
#  egg_hatcher.py — Automatic egg hatching loop
#
#  Records your movement pattern once, then loops it forever.
#
#  SETUP:
#    pip install pynput
#
#  HOW TO USE:
#    1. Run: python egg_hatcher.py
#    2. Get into position in-game (on your bike/walking route)
#    3. Press F8 to START recording
#    4. Do your egg hatching route once (e.g. ride left, ride right)
#    5. Press F8 again to STOP recording & START looping
#    6. The bot loops your route automatically
#    7. Press F8 again (or Ctrl+C) to STOP
#
#  CONTROLS:
#    F8            = Start recording / Stop+Loop / Stop
#    Hold F8 1.5s  = Force re-record
#    Ctrl+C        = Exit
# ============================================================

import time
import threading
import json
import os
import signal
import sys
from pynput import keyboard

try:
    from controller import press, hold, sequence, focus_retroarch, _get_gamepad
except ImportError:
    print("ERROR: controller.py not found. Run from the bot folder.")
    sys.exit(1)

# Initialise the virtual gamepad NOW — RetroArch must be opened AFTER this point
print("[Hatcher] Initialising virtual gamepad...")
_get_gamepad()
print("[Hatcher] Virtual gamepad ready. Make sure RetroArch is open NOW.")

ROUTE_SAVE_FILE = os.path.join(os.path.dirname(__file__), "egg_hatcher_route.json")

# ── Trigger key — change this if F8 conflicts with something ──
# Options: keyboard.Key.f8, keyboard.Key.f9, keyboard.Key.scroll_lock, etc.
TRIGGER_KEY = keyboard.Key.f8

# ── Key → Gamepad button mapping ─────────────────────────────
# Maps keyboard keys to the gamepad buttons used in controller.py
KEY_MAP = {
    keyboard.Key.up:    "UP",
    keyboard.Key.down:  "DOWN",
    keyboard.Key.left:  "LEFT",
    keyboard.Key.right: "RIGHT",
    keyboard.KeyCode.from_char('x'): "A",
    keyboard.KeyCode.from_char('z'): "B",
    keyboard.Key.enter: "START",
    keyboard.Key.shift: "SELECT",
    keyboard.KeyCode.from_char('q'): "L",
    keyboard.KeyCode.from_char('w'): "R",
}

# ── State ─────────────────────────────────────────────────────
STATE_IDLE      = "idle"
STATE_RECORDING = "recording"
STATE_LOOPING   = "looping"

state         = STATE_IDLE
recording     = []       # list of (action, key_name, timestamp)
record_start  = 0.0
loop_thread   = None
stop_loop     = threading.Event()
exit_event    = threading.Event()


def save_route(events: list):
    with open(ROUTE_SAVE_FILE, "w") as f:
        json.dump(events, f)
    print(f"[Hatcher] Route saved to egg_hatcher_route.json ({len(events)} events)")


def load_route() -> list:
    if os.path.isfile(ROUTE_SAVE_FILE):
        with open(ROUTE_SAVE_FILE) as f:
            return json.load(f)
    return []


# ── Playback ──────────────────────────────────────────────────

def playback_loop(events: list, total_duration: float):
    """
    Loop the recorded event sequence until stop_loop is set.
    Each iteration replays events with the same relative timing.
    """
    focus_retroarch()   # make sure RetroArch has focus before sending inputs
    print(f"[Hatcher] Looping {len(events)} events over {total_duration:.1f}s per cycle...")
    cycle = 0
    while not stop_loop.is_set():
        cycle += 1
        print(f"[Hatcher] Cycle {cycle}", end="\r", flush=True)
        loop_start = time.time()
        for action, btn, t in events:
            if stop_loop.is_set():
                break
            # Wait until it's time for this event
            target = loop_start + t
            now    = time.time()
            if target > now:
                time.sleep(target - now)
            if stop_loop.is_set():
                break
            # Execute
            press(btn)
        # Wait any remaining time before next cycle
        elapsed = time.time() - loop_start
        if not stop_loop.is_set() and elapsed < total_duration:
            time.sleep(total_duration - elapsed)

    print(f"\n[Hatcher] Stopped after {cycle} cycles.")


# ── Trigger handler ───────────────────────────────────────────

_trigger_press_time = 0.0

def _handle_trigger(long_press: bool):
    """Called when the trigger key is pressed. Handles all state transitions."""
    global state, recording, record_start, loop_thread

    # Long press (1.5s) → force re-record
    if long_press and state in (STATE_IDLE, STATE_LOOPING):
        if state == STATE_LOOPING:
            stop_loop.set()
        state        = STATE_RECORDING
        recording    = []
        record_start = time.time()
        print("\n[Hatcher] 🔴 RE-RECORDING — do your route now...")
        print("          Press F8 again to stop and loop.")
        return

    if state == STATE_IDLE:
        if recording:
            # Route exists — start looping
            total_duration = recording[-1][2] if recording else 1.0
            print(f"\n[Hatcher] 🔁 LOOPING ({len(recording)} events)...")
            print("          Press F8 to stop.")
            state = STATE_LOOPING
            stop_loop.clear()
            loop_thread = threading.Thread(
                target=playback_loop,
                args=(list(recording), total_duration),
                daemon=True,
            )
            loop_thread.start()
        else:
            # No route yet — start recording
            state        = STATE_RECORDING
            recording    = []
            record_start = time.time()
            print("\n[Hatcher] 🔴 RECORDING — do your route now...")
            print("          Press F8 again to stop and loop.")

    elif state == STATE_RECORDING:
        total_duration = time.time() - record_start
        if not recording:
            print("[Hatcher] Nothing recorded — try again.")
            state = STATE_IDLE
            return
        print(f"\n[Hatcher] ✓ Recorded {len(recording)} events over {total_duration:.1f}s")
        save_route([[a, b, c] for a, b, c in recording])
        print("[Hatcher] 🔁 LOOPING — press F8 to stop.")
        state = STATE_LOOPING
        stop_loop.clear()
        loop_thread = threading.Thread(
            target=playback_loop,
            args=(list(recording), total_duration),
            daemon=True,
        )
        loop_thread.start()

    elif state == STATE_LOOPING:
        print("\n[Hatcher] ■ Stopping...")
        stop_loop.set()
        if loop_thread:
            loop_thread.join(timeout=3)
        state = STATE_IDLE
        print("[Hatcher] Paused. Press F8 to loop again. Hold F8 1.5s to re-record.")


def on_key_press(key):
    global _trigger_press_time
    if key == TRIGGER_KEY:
        _trigger_press_time = time.time()
        return  # wait for release
    if state != STATE_RECORDING:
        return
    btn = KEY_MAP.get(key)
    if btn:
        t = time.time() - record_start
        recording.append(("press", btn, t))


def on_key_release(key):
    if key == TRIGGER_KEY:
        held = time.time() - _trigger_press_time
        _handle_trigger(long_press=held >= 1.5)
        return
    if state != STATE_RECORDING:
        return
    btn = KEY_MAP.get(key)
    if btn:
        t = time.time() - record_start
        recording.append(("release", btn, t))


# ── Main ──────────────────────────────────────────────────────

def main():
    global recording

    print("╔══════════════════════════════════════════════════╗")
    print("║         Pokémon Unbound — Egg Hatcher            ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  F8           = Record / Loop / Stop             ║")
    print("║  Hold F8 1.5s = Force re-record                  ║")
    print("║  Ctrl+C       = Exit                             ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # Load saved route if one exists
    saved = load_route()
    if saved:
        recording = [(a, b, c) for a, b, c in saved]
        print(f"  ✓ Loaded saved route ({len(recording)} events from egg_hatcher_route.json)")
        print("  Press F8 to start looping it, or hold F8 1.5s to re-record.")
    else:
        print("  Waiting... Press F8 to start recording.")
    print()

    # Handle Ctrl+C cleanly
    def handle_sigint(sig, frame):
        print("\n[Hatcher] Ctrl+C — exiting.")
        stop_loop.set()
        exit_event.set()

    signal.signal(signal.SIGINT, handle_sigint)

    # Listen to keyboard (for recording movement keys)
    kb_listener = keyboard.Listener(
        on_press=on_key_press,
        on_release=on_key_release,
        suppress=False,
    )
    kb_listener.start()

    # Main thread just waits for exit signal
    exit_event.wait()
    stop_loop.set()
    kb_listener.stop()
    print("[Hatcher] Goodbye.")


if __name__ == "__main__":
    main()

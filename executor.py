# ============================================================
#  executor.py — parses bot responses and executes actions
# ============================================================
#
#  Standard action tags:
#    <<PRESS:A>>              — press a single button
#    <<SEQ:UP,UP,A,START>>    — press a sequence of buttons
#    <<HOLD:LEFT:0.8>>        — hold a button for N seconds
#    <<WAIT:0.5>>             — pause for N seconds
#
#  Scripted compound actions:
#    <<FLY>>                  — open START menu, go to Pokémon,
#                               select first party member, choose Fly.
#                               Leaves you on the region map to pick destination.
#    <<SURF>>                 — same flow but selects Surf (2nd HM slot)
#
#  These tags are stripped from the display text and executed.
# ============================================================

import re
import time
import json
import os
from controller import press, hold, sequence

# ---------------------------------------------------------------------------
# Fly map — grid coordinates of each town on the region map
# ---------------------------------------------------------------------------
_FLY_MAP_PATH = os.path.join(os.path.dirname(__file__), "fly_map.json")

def _load_fly_map() -> dict:
    try:
        with open(_FLY_MAP_PATH, "r") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_") and v is not None}
    except Exception:
        return {}

def _navigate_fly_map(current_location: str, destination: str) -> list[str]:
    """
    Calculate the cursor button sequence to get from current_location
    to destination on the region map.
    Returns a list of button names to press in order.
    """
    fly_map = _load_fly_map()
    src = fly_map.get(current_location)
    dst = fly_map.get(destination)

    if src is None or dst is None:
        print(f"[FlyMap] Missing coords — src={current_location}:{src}, dst={destination}:{dst}")
        return []

    dx = dst[0] - src[0]
    dy = dst[1] - src[1]

    buttons = []
    h_btn = "RIGHT" if dx > 0 else "LEFT"
    v_btn = "DOWN"  if dy > 0 else "UP"
    buttons.extend([h_btn] * abs(dx))
    buttons.extend([v_btn] * abs(dy))
    return buttons

# Regex patterns for each tag type
_RE_PRESS = re.compile(r'<<PRESS:([A-Za-z0-9_]+)>>',        re.IGNORECASE)
_RE_SEQ   = re.compile(r'<<SEQ:([A-Za-z0-9_, ]+)>>',        re.IGNORECASE)
_RE_HOLD  = re.compile(r'<<HOLD:([A-Za-z0-9_]+):([\d.]+)>>', re.IGNORECASE)
_RE_WAIT  = re.compile(r'<<WAIT:([\d.]+)>>',                 re.IGNORECASE)
_RE_FLY   = re.compile(r'<<FLY(?::([^>]+))?>>',              re.IGNORECASE)
_RE_SURF  = re.compile(r'<<SURF>>',                          re.IGNORECASE)


# ---------------------------------------------------------------------------
# Scripted HM sequences
#
# Pokémon Unbound party submenu order:
#   Summary → [HM moves the Pokémon can use] → Switch → Item → Cancel
#
# So the first HM (usually Fly) is always at DOWN×1 from the top.
# If the target HM is second (e.g. there are two HMs), use DOWN×2.
# ---------------------------------------------------------------------------

def _open_party_submenu():
    """
    From the overworld: open START menu → navigate to Pokémon → open party
    → select the first party slot.
    Ends with the party submenu (Summary / HMs / Switch / Item / Cancel) open.
    """
    press("START");    time.sleep(0.5)   # Open main menu
    press("DOWN");     time.sleep(0.2)   # Cursor → Pokémon (2nd option)
    press("A");        time.sleep(0.6)   # Open party screen
    press("A");        time.sleep(0.4)   # Select first Pokémon → submenu opens


def use_fly():
    """
    Full Fly sequence: gets from overworld to the region map.
    Party submenu order: Summary(0) → Fly(1) → ...
    After this call the region map is open — agent navigates to destination.
    """
    _open_party_submenu()
    press("DOWN");     time.sleep(0.2)   # Move past Summary → Fly
    press("A");        time.sleep(0.8)   # Select Fly → region map opens


def use_surf():
    """
    Surf sequence. Assumes Surf is the first HM available (same slot as Fly).
    If both Fly and Surf are available on the same Pokémon, Surf may be DOWN×2.
    """
    _open_party_submenu()
    press("DOWN");     time.sleep(0.2)   # Move past Summary → first HM (Surf)
    press("A");        time.sleep(0.8)   # Select Surf


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

# Current location — set by agent before each step so FLY knows where we are
_current_location: str = ""

def set_current_location(location: str):
    global _current_location
    _current_location = location


def parse_and_execute(response: str, execute: bool = True) -> tuple[str, list[str]]:
    """
    Scan a bot response for action tags, execute them, and return
    the cleaned display text plus a log of actions taken.

    Args:
        response: raw bot response text (may contain <<...>> tags)
        execute:  if False, just parse and return log without running anything

    Returns:
        (clean_text, action_log)
    """
    action_log = []
    clean = response

    # --- <<FLY>> or <<FLY:Destination>> ---
    for match in _RE_FLY.finditer(response):
        destination = (match.group(1) or "").strip()
        if destination:
            action_log.append(f"FLY to {destination} (scripted)")
        else:
            action_log.append("FLY (scripted: opens region map)")
        if execute:
            use_fly()
            if destination and _current_location:
                nav = _navigate_fly_map(_current_location, destination)
                if nav:
                    time.sleep(0.8)   # wait for region map to fully open
                    sequence(nav, delay=0.12)
                    time.sleep(0.2)
                    press("A")        # confirm destination
                    action_log[-1] += f" — {len(nav)} moves → A"
                else:
                    action_log[-1] += " — ⚠ no coords, navigate map manually"
    clean = _RE_FLY.sub('', clean)

    # --- <<SURF>> ---
    if _RE_SURF.search(response):
        action_log.append("SURF (scripted: START→Pokémon→Surf)")
        if execute:
            use_surf()
    clean = _RE_SURF.sub('', clean)

    # --- <<PRESS:X>> ---
    for match in _RE_PRESS.finditer(response):
        btn = match.group(1).upper()
        action_log.append(f"PRESS {btn}")
        if execute:
            press(btn)
    clean = _RE_PRESS.sub('', clean)

    # --- <<SEQ:A,B,C>> ---
    for match in _RE_SEQ.finditer(response):
        buttons = [b.strip().upper() for b in match.group(1).split(',')]
        action_log.append(f"SEQ [{', '.join(buttons)}]")
        if execute:
            sequence(buttons)
    clean = _RE_SEQ.sub('', clean)

    # --- <<HOLD:X:0.5>> ---
    for match in _RE_HOLD.finditer(response):
        btn      = match.group(1).upper()
        duration = float(match.group(2))
        action_log.append(f"HOLD {btn} {duration}s")
        if execute:
            hold(btn, duration)
    clean = _RE_HOLD.sub('', clean)

    # --- <<WAIT:0.5>> ---
    for match in _RE_WAIT.finditer(response):
        secs = float(match.group(1))
        action_log.append(f"WAIT {secs}s")
        if execute:
            time.sleep(secs)
    clean = _RE_WAIT.sub('', clean)

    # Clean up any leftover whitespace artifacts
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()

    return clean, action_log


def has_actions(response: str) -> bool:
    """Return True if the response contains any action tags."""
    return bool(
        _RE_FLY.search(response)   or
        _RE_SURF.search(response)  or
        _RE_PRESS.search(response) or
        _RE_SEQ.search(response)   or
        _RE_HOLD.search(response)  or
        _RE_WAIT.search(response)
    )

# ============================================================
#  game_state.py — game state manager
#  Now powered by live RAM reading via ram_reader.py
# ============================================================

import json
import os

STATE_FILE = os.path.join(os.path.dirname(__file__), "game_state.json")

DEFAULT_STATE = {
    "location":     "Unknown",
    "map_bank":     0,
    "map_number":   0,
    "player_x":     0,
    "player_y":     0,
    "badges":       [],
    "team":         [],
    "in_battle":    False,
    "is_trainer":   False,
    "is_double":    False,
    "active_goal":  None,
    "notes":        [],
    # HMs the player has obtained — used by agent planning phase.
    # Update with: "set hms: Fly, Surf, Cut"
    "hms_obtained": [],
}


def load_state() -> dict:
    """Load last-known state from disk."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                for key, val in DEFAULT_STATE.items():
                    data.setdefault(key, val)
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_STATE.copy()


def save_state(state: dict):
    """Persist state to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def refresh_from_ram(state: dict) -> dict:
    """
    Pull live data from RetroArch RAM and merge into state.
    Preserves active_goal and notes (those are user-managed).
    Returns updated state dict.
    """
    try:
        from ram_reader import read_game_state, register_map_name
        live = read_game_state()
        if live is None:
            return state  # RetroArch unreachable, keep last known state

        # Merge RAM data, preserving user-managed fields
        state["location"]   = live["location"]
        state["map_bank"]   = live["map_bank"]
        state["map_number"] = live["map_number"]
        state["player_x"]   = live["player_x"]
        state["player_y"]   = live["player_y"]
        state["badges"]     = live["badges"]
        state["team"]       = live["team"]
        state["in_battle"]  = live.get("in_battle", False)
        state["is_trainer"] = live.get("is_trainer", False)
        state["is_double"]  = live.get("is_double", False)
        # active_goal and notes stay as-is

    except Exception as e:
        print(f"[GameState] RAM read failed: {e}")

    return state


def format_state_for_prompt(state: dict) -> str:
    """Format game state as readable text for the system prompt."""
    badges = ", ".join(state["badges"]) if state["badges"] else "None"
    goal   = state["active_goal"] or "None"
    notes  = "\n  - " + "\n  - ".join(state["notes"]) if state["notes"] else "  None"

    team_lines = []
    for p in state.get("team", []):
        hp_str = f"{p.get('hp','?')}/{p.get('max_hp','?')} HP"
        status = p.get("status", "Healthy")
        status_str = f" [{status}]" if status != "Healthy" else ""
        team_lines.append(
            f"  - {p['name']} (Lv.{p.get('level','?')}) | {hp_str}{status_str}"
        )
    team_str = "\n".join(team_lines) if team_lines else "  Not available"

    location = state.get("location", "Unknown")
    coords   = ""
    if state.get("player_x") or state.get("player_y"):
        coords = f" [x:{state.get('player_x',0)}, y:{state.get('player_y',0)}]"

    # Battle status — explicit so the agent never has to guess
    if state.get("in_battle"):
        battle_type = []
        if state.get("is_trainer"): battle_type.append("Trainer")
        if state.get("is_double"):  battle_type.append("Double")
        if not battle_type:         battle_type.append("Wild")
        battle_str = f"⚔ IN BATTLE ({' '.join(battle_type)} Battle)"
    else:
        battle_str = "🗺 OVERWORLD (not in battle)"

    return f"""
=== CURRENT GAME STATE (LIVE FROM RAM) ===
Status:      {battle_str}
Location:    {location}{coords}
Badges:      {badges}
Active Goal: {goal}

Team:
{team_str}

Notes:
{notes}
==========================================
"""


def update_state_from_message(state: dict, message: str) -> dict:
    """Handle manual state commands typed by the user."""
    msg = message.strip().lower()

    if msg.startswith("set goal:"):
        state["active_goal"] = message.split(":", 1)[1].strip()
    elif msg.startswith("set location:"):
        # Also register this name in the map lookup so RAM reader knows it
        name = message.split(":", 1)[1].strip()
        state["location"] = name
        try:
            from ram_reader import register_map_name
            register_map_name(
                state.get("map_bank", 0),
                state.get("map_number", 0),
                name
            )
            print(f"[GameState] Registered map {state.get('map_bank',0)}:{state.get('map_number',0)} = {name}")
        except Exception:
            pass
    elif msg.startswith("add note:"):
        state["notes"].append(message.split(":", 1)[1].strip())
    elif msg.startswith("clear notes"):
        state["notes"] = []
    elif msg.startswith("clear goal"):
        state["active_goal"] = None
    elif msg.startswith("set hms:"):
        raw = message.split(":", 1)[1].strip()
        state["hms_obtained"] = [h.strip() for h in raw.split(",") if h.strip()]
        print(f"[GameState] HMs set: {state['hms_obtained']}")

    return state

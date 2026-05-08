# ============================================================
#  nav_memory.py — navigation path memory
#
#  Records successful routes between locations.
#  The agent can replay recorded paths instead of guessing.
# ============================================================

import json
import os
import time

NAV_FILE = os.path.join(os.path.dirname(__file__), "nav_memory.json")


def _load() -> dict:
    if os.path.isfile(NAV_FILE):
        try:
            with open(NAV_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    with open(NAV_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _route_key(from_loc: str, to_loc: str) -> str:
    return f"{from_loc.lower().strip()} → {to_loc.lower().strip()}"


# ── Recording a path ────────────────────────────────────────

class PathRecorder:
    """
    Context manager that records a navigation path.

    Usage:
        recorder = PathRecorder("Dehara City", "Dehara Gym")
        recorder.step("UP")
        recorder.step("UP")
        recorder.step("A")
        recorder.save()  # saves if successful
    """
    def __init__(self, from_loc: str, to_loc: str):
        self.from_loc  = from_loc
        self.to_loc    = to_loc
        self.steps:    list[str] = []
        self.start_ts: float = time.time()

    def step(self, action: str):
        self.steps.append(action)

    def save(self, notes: str = ""):
        if not self.steps:
            return
        data   = _load()
        key    = _route_key(self.from_loc, self.to_loc)
        entry  = {
            "from":      self.from_loc,
            "to":        self.to_loc,
            "steps":     self.steps,
            "duration":  round(time.time() - self.start_ts, 1),
            "notes":     notes,
            "recorded":  time.strftime("%Y-%m-%d %H:%M"),
        }
        # Keep the most recent recording for each route
        data[key] = entry
        _save(data)
        print(f"[NavMemory] Saved route: {self.from_loc} → {self.to_loc} ({len(self.steps)} steps)")
        return entry


# ── Replaying a path ────────────────────────────────────────

def get_route(from_loc: str, to_loc: str) -> dict | None:
    """Return a saved route dict, or None if not recorded."""
    data = _load()
    return data.get(_route_key(from_loc, to_loc))


def replay_route(from_loc: str, to_loc: str, delay: float = 0.15) -> bool:
    """
    Replay a recorded route by executing its steps.
    Returns True if route was found and executed, False otherwise.
    """
    route = get_route(from_loc, to_loc)
    if not route:
        return False

    from controller import sequence
    print(f"[NavMemory] Replaying: {from_loc} → {to_loc} ({len(route['steps'])} steps)")
    sequence(route["steps"], delay=delay)
    return True


def list_routes() -> list[str]:
    """Return all known routes as human-readable strings."""
    data = _load()
    return [f"{v['from']} → {v['to']} ({len(v['steps'])} steps)" for v in data.values()]


def get_routes_from(location: str) -> list[dict]:
    """Return all routes that start from a given location."""
    data  = _load()
    loc_l = location.lower().strip()
    return [v for v in data.values() if v["from"].lower() == loc_l]


def format_routes_for_prompt(location: str) -> str:
    """Return known routes from current location as prompt text."""
    routes = get_routes_from(location)
    if not routes:
        return ""
    lines = [f"=== KNOWN ROUTES FROM {location.upper()} ==="]
    for r in routes:
        lines.append(f"  → {r['to']}: {len(r['steps'])} steps recorded (just say 'go to {r['to']}')")
    return "\n".join(lines)

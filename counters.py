# ============================================================
#  counters.py — persistent counters (steps, encounters, custom)
# ============================================================

import json
import os

COUNTERS_FILE = os.path.join(os.path.dirname(__file__), "counters.json")

DEFAULT_COUNTERS = {
    "steps":       0,
    "encounters":  0,
    "custom":      []   # list of {"name": "Shiny Hunt: Ralts", "value": 0}
}

# Shiny odds denominator (base rate without shiny charm)
SHINY_ODDS_BASE = 4096


def load_counters() -> dict:
    if os.path.isfile(COUNTERS_FILE):
        try:
            with open(COUNTERS_FILE, "r") as f:
                data = json.load(f)
                for k, v in DEFAULT_COUNTERS.items():
                    data.setdefault(k, v)
                return data
        except Exception:
            pass
    return DEFAULT_COUNTERS.copy()


def save_counters(counters: dict):
    with open(COUNTERS_FILE, "w") as f:
        json.dump(counters, f, indent=2)


def get_shiny_odds(encounters: int) -> str:
    """Return a human-readable shiny probability string."""
    if encounters == 0:
        return f"1/{SHINY_ODDS_BASE}"
    # Each encounter is an independent 1/4096 chance
    # Probability of NOT getting shiny after N encounters: ((4095/4096)^N)
    # Probability of at least one: 1 - (4095/4096)^N
    prob = 1 - ((SHINY_ODDS_BASE - 1) / SHINY_ODDS_BASE) ** encounters
    pct = prob * 100
    if pct < 0.1:
        return f"{pct:.3f}%"
    elif pct < 1:
        return f"{pct:.2f}%"
    else:
        return f"{pct:.1f}%"

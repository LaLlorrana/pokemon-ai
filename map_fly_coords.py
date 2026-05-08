# ============================================================
#  map_fly_coords.py — Interactive Fly map coordinate builder
#
#  HOW TO USE:
#    1. In Pokémon Unbound, open Fly:
#       START → Pokémon → any party member → Fly
#    2. The fly map should now be open on screen.
#    3. Run this script in a terminal: python map_fly_coords.py
#    4. The script will home the cursor to the top-left corner.
#    5. Use arrow keys HERE (in the terminal) to move the cursor.
#       The cursor moves in-game at the same time.
#    6. When the cursor is on a town, press SPACE.
#       Type the town name (or enough to match it) and press Enter.
#    7. Repeat for every town. Press Q when done.
#
#  The coordinates are saved to fly_map.json automatically.
# ============================================================

import msvcrt
import json
import os
import time
import sys

try:
    from controller import press, sequence
except ImportError:
    print("ERROR: controller.py not found. Run this from the bot folder.")
    sys.exit(1)

FLY_MAP_PATH = os.path.join(os.path.dirname(__file__), "fly_map.json")

# ── helpers ─────────────────────────────────────────────────

def load_fly_map() -> dict:
    with open(FLY_MAP_PATH, "r") as f:
        return json.load(f)

def save_fly_map(data: dict):
    with open(FLY_MAP_PATH, "w") as f:
        json.dump(data, f, indent=2)

def status_line(x: int, y: int, fly_map: dict):
    done  = sum(1 for k, v in fly_map.items() if not k.startswith("_") and v is not None)
    total = sum(1 for k in fly_map if not k.startswith("_"))
    remaining = [k for k, v in fly_map.items() if not k.startswith("_") and v is None]
    rem_str = ", ".join(remaining) if remaining else "All done!"
    print(f"\r  Position [{x:3d}, {y:3d}]  |  {done}/{total} mapped  |  Remaining: {rem_str[:60]}   ",
          end="", flush=True)

def fuzzy_match(name: str, fly_map: dict) -> list[str]:
    """Return town keys that start with the given string (case-insensitive)."""
    name_l = name.lower().strip()
    return [k for k in fly_map if not k.startswith("_") and k.lower().startswith(name_l)]

# ── main ─────────────────────────────────────────────────────

def main():
    fly_map = load_fly_map()

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║       Pokémon Unbound — Fly Map Mapper           ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Make sure the Fly region map is OPEN in-game.   ║")
    print("║                                                   ║")
    print("║  Controls (in this terminal window):              ║")
    print("║    Arrow keys → move cursor in-game              ║")
    print("║    SPACE      → mark current town                ║")
    print("║    Q          → quit and save                    ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    input("  Press Enter when the fly map is open and ready...")
    print()

    # ── Home the cursor to top-left corner ──────────────────
    print("  Homing cursor to top-left corner (pressing UP×20, LEFT×20)...")
    print("  (The cursor will hit the map edge and stop — that's correct)")
    time.sleep(0.5)
    for _ in range(20):
        press("UP");   time.sleep(0.08)
    for _ in range(20):
        press("LEFT"); time.sleep(0.08)
    time.sleep(0.3)
    print("  Done! Cursor should be at the top-left of the map.")
    print()
    print("  Now use ARROW KEYS to navigate. Press SPACE when on a town.")
    print()

    x, y = 0, 0
    status_line(x, y, fly_map)

    while True:
        ch = msvcrt.getch()

        # ── Arrow keys (Windows sends 0xe0 then the keycode) ──
        if ch == b'\xe0':
            ch2 = msvcrt.getch()
            if   ch2 == b'H':  press("UP");    y -= 1   # up
            elif ch2 == b'P':  press("DOWN");  y += 1   # down
            elif ch2 == b'K':  press("LEFT");  x -= 1   # left
            elif ch2 == b'M':  press("RIGHT"); x += 1   # right
            # Clamp — map can't go negative
            x = max(x, 0)
            y = max(y, 0)
            status_line(x, y, fly_map)
            continue

        # ── SPACE — mark a town ──────────────────────────────
        if ch == b' ':
            print()
            print(f"\n  --- Marking town at position [{x}, {y}] ---")

            # Show what's already mapped and what's left
            unmapped = [k for k, v in fly_map.items() if not k.startswith("_") and v is None]
            if unmapped:
                print(f"  Towns still needed: {', '.join(unmapped)}")

            raw = input("  Town name (or partial, e.g. 'deh'): ").strip()
            if not raw:
                print("  Skipped.")
            else:
                matches = fuzzy_match(raw, fly_map)
                if len(matches) == 1:
                    fly_map[matches[0]] = [x, y]
                    save_fly_map(fly_map)
                    print(f"  ✓ Saved: {matches[0]} = [{x}, {y}]")
                elif len(matches) > 1:
                    print(f"  Multiple matches: {', '.join(matches)}")
                    exact = input("  Type exact name: ").strip()
                    if exact in fly_map:
                        fly_map[exact] = [x, y]
                        save_fly_map(fly_map)
                        print(f"  ✓ Saved: {exact} = [{x}, {y}]")
                    else:
                        print(f"  '{exact}' not found — skipped.")
                else:
                    print(f"  No match for '{raw}'. Available: {', '.join(unmapped[:5])}")

            print()
            status_line(x, y, fly_map)
            continue

        # ── Q — quit ─────────────────────────────────────────
        if ch in (b'q', b'Q'):
            print()
            print()
            print("  Quitting...")
            break

    # ── Summary ──────────────────────────────────────────────
    print()
    print("  ══ Final fly_map.json ══")
    for k, v in fly_map.items():
        if k.startswith("_"):
            continue
        status = f"[{v[0]}, {v[1]}]" if v is not None else "NOT MAPPED"
        print(f"    {k:<20} {status}")

    unmapped = [k for k, v in fly_map.items() if not k.startswith("_") and v is None]
    if unmapped:
        print()
        print(f"  ⚠ Still missing: {', '.join(unmapped)}")
        print("  Run this script again to fill in the rest.")
    else:
        print()
        print("  ✓ All towns mapped! <<FLY:Destination>> is fully operational.")


if __name__ == "__main__":
    main()

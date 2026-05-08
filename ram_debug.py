# ============================================================
#  ram_debug.py — RAM address diagnostic tool
#
#  Run this while RetroArch + Pokémon Unbound is open to
#  verify/find the correct addresses for your game version.
#
#  Usage:
#    python ram_debug.py           — full diagnostic
#    python ram_debug.py coords    — scan for player coordinates
#    python ram_debug.py badges    — scan for badge address
#    python ram_debug.py battle    — test battle detection
#    python ram_debug.py watch     — live-updating state dump
# ============================================================

import sys
import time
import struct
from ram_reader import (
    read_u8, read_u16, read_u32, read_memory,
    ADDR_MAP_BANK, ADDR_MAP_NUMBER,
    ADDR_PLAYER_X, ADDR_PLAYER_Y,
    ADDR_SAVEBLOCK1_PTR, BADGES_OFFSET, BADGES_FALLBACK_ADDRS,
    ADDR_BATTLE_FLAGS,
    ADDR_PARTY_COUNT, ADDR_PARTY_START,
    read_game_state, read_battle_state, _read_badges,
)


def separator(title=""):
    print(f"\n{'─'*50}")
    if title:
        print(f"  {title}")
        print(f"{'─'*50}")


def full_diagnostic():
    """Run all checks and print a summary."""
    separator("RETROARCH CONNECTION")
    val = read_u8(ADDR_MAP_BANK)
    if val is None:
        print("  ✗ Cannot connect to RetroArch!")
        print("    Make sure RetroArch is running with a game loaded")
        print("    and Network Commands are ON (Settings → Network → Network Commands)")
        return
    print(f"  ✓ Connected — map bank byte: {val} (0x{val:02X})")

    separator("MAP / LOCATION")
    bank   = read_u8(ADDR_MAP_BANK)   or 0
    number = read_u8(ADDR_MAP_NUMBER) or 0
    print(f"  Map bank:    {bank}  (addr 0x{ADDR_MAP_BANK:08X})")
    print(f"  Map number:  {number}  (addr 0x{ADDR_MAP_NUMBER:08X})")
    print(f"  Key:         {bank}:{number}")
    print("  → If this matches your known location key, map reading is CORRECT")

    separator("PLAYER COORDINATES")
    x = read_u16(ADDR_PLAYER_X)
    y = read_u16(ADDR_PLAYER_Y)
    print(f"  Player X:  {x}  (addr 0x{ADDR_PLAYER_X:08X})")
    print(f"  Player Y:  {y}  (addr 0x{ADDR_PLAYER_Y:08X})")
    if x == 0 and y == 0:
        print("  ⚠ Both are 0 — addresses might still be wrong. Run: python ram_debug.py coords")
    else:
        print("  ✓ Non-zero values — looking good!")

    separator("BADGES")
    ptr = read_u32(ADDR_SAVEBLOCK1_PTR)
    print(f"  SaveBlock1 pointer: 0x{ptr:08X}" if ptr else "  SaveBlock1 pointer: failed")
    badge_byte = _read_badges()
    print(f"  Badge bitfield: 0b{badge_byte:08b}  (decimal {badge_byte})")
    # Verified from unboundwiki.com — gym order and badge names
    badge_names = [
        "Leaf",    # Gym 1 — Mirskle (Dresco Town, Grass/Fairy)
        "Vision",  # Gym 2 — Véga (Crater Town, Dark)
        "Wings",   # Gym 3 — Alice (Blizzard City, Flying)
        "Fall",    # Gym 4 — Mel (Fallshore City, Normal/Inverse)
        "Battery", # Gym 5 — Galavan (Dehara City, Electric+Steel)
        "Ring",    # Gym 6 — Big Mo (Antisis City, Fighting)
        "Swamp",   # Gym 7 — Tessy (Polder Town, Water)
        "Time",    # Gym 8 — Benjamin (Redwood Village, Bug)
    ]
    earned = [badge_names[i] for i in range(8) if badge_byte & (1 << i)]
    print(f"  Earned badges: {earned if earned else 'None (or address wrong)'}")
    if badge_byte == 0:
        print("  ⚠ 0 badges — either you have none, or the address is wrong.")
        print("    Run: python ram_debug.py badges")

    separator("BATTLE STATE")
    battle = read_battle_state()
    print(f"  Battle flags: 0x{battle['battle_flags']:08X}")
    if battle["in_battle"]:
        btype = []
        if battle["is_trainer"]: btype.append("Trainer")
        if battle["is_double"]:  btype.append("Double")
        if not btype:            btype.append("Wild")
        print(f"  ⚔ IN BATTLE — type: {' '.join(btype)}")
    else:
        print("  🗺 Not in battle (overworld)")
    print("  → Enter a battle and re-run to verify detection works")

    separator("PARTY")
    count = read_u8(ADDR_PARTY_COUNT) or 0
    print(f"  Party count: {count}")
    if count == 0:
        print("  ⚠ 0 Pokémon — party reading may be broken")
    else:
        print(f"  ✓ {count} Pokémon detected")

    separator("FULL STATE")
    state = read_game_state()
    if state:
        import json
        print(json.dumps(state, indent=2))
    else:
        print("  Failed to read full state")


def scan_coords():
    """
    Scan a range of addresses around the expected location for
    plausible X/Y coordinate values.
    Run this while standing somewhere you know your coordinates
    (e.g. in front of Dehara City Pokémon Center).
    """
    print("\nScanning for player coordinates...")
    print("Stand somewhere you know your tile X/Y position.")
    print("In Pokémon Unbound, you can use the Debug menu or a FAQ to find coords.\n")

    base = 0x02036E38   # start of gObjectEvents
    print(f"Scanning 64 bytes starting at 0x{base:08X} (gObjectEvents[0]):\n")

    data = read_memory(base, 64)
    if not data:
        print("Failed to read memory. Is RetroArch running?")
        return

    print("Offset  | Value (u16 LE) | Value (u8)")
    print("--------|----------------|----------")
    for offset in range(0, 64, 2):
        u16 = struct.unpack_from('<H', data, offset)[0]
        u8  = data[offset]
        marker = " ← current X/Y candidate" if offset in (0x10, 0x12) else ""
        print(f"  +0x{offset:02X}  | {u16:5d} (0x{u16:04X}) | {u8:3d}  {marker}")

    print(f"\nCurrently configured:")
    print(f"  ADDR_PLAYER_X = 0x{ADDR_PLAYER_X:08X} → value: {read_u16(ADDR_PLAYER_X)}")
    print(f"  ADDR_PLAYER_Y = 0x{ADDR_PLAYER_Y:08X} → value: {read_u16(ADDR_PLAYER_Y)}")


def scan_badges():
    """
    Scan multiple candidate addresses for a plausible badge byte.
    Run this when you have at least 1 badge.
    """
    print("\nScanning for badge address...")
    print("This works best if you have 1-7 badges (not 0, not 8).\n")

    candidates = [
        ("SaveBlock1 ptr + offset", None),  # computed below
        ("0x02025044 (FireRed default)",     0x02025044),
        ("0x020250A4",                       0x020250A4),
        ("0x02025134",                       0x02025134),
        ("0x02025790 (SaveBlock1+0x5C alt)", 0x02025790),
        ("0x02024F44",                       0x02024F44),
    ]

    ptr = read_u32(ADDR_SAVEBLOCK1_PTR)
    if ptr and 0x02000000 <= ptr <= 0x02040000:
        candidates[0] = (f"SaveBlock1(0x{ptr:08X}) + 0x{BADGES_OFFSET:02X}", ptr + BADGES_OFFSET)
    else:
        candidates[0] = ("SaveBlock1 ptr (failed)", None)

    print(f"{'Address':<45} | {'Value':>5} | {'Badges'}")
    print(f"{'─'*45}-+-------+{'-'*20}")
    for label, addr in candidates:
        if addr is None:
            print(f"  {label:<43} | {'N/A':>5} | N/A")
            continue
        val = read_u8(addr)
        if val is None:
            print(f"  {label:<43} | {'ERR':>5} | read error")
        else:
            earned = [str(i+1) for i in range(8) if val & (1 << i)]
            print(f"  {label:<43} | {val:>5} | badges: {','.join(earned) if earned else 'none'}")

    print("\nThe correct address should show a value that matches your actual badge count.")
    print("If you have 2 badges (gym 1 + gym 2), the value should be 0b00000011 = 3")
    print("\nScanning ±16 bytes around the pointer result for 'all 8 badges' value (0xFF = 255):")
    ptr = read_u32(ADDR_SAVEBLOCK1_PTR)
    if ptr and 0x02000000 <= ptr <= 0x02040000:
        for delta in range(-16, 24, 1):
            addr = ptr + BADGES_OFFSET + delta
            val  = read_u8(addr)
            bits = bin(val).count('1') if val is not None else 0
            marker = " ←" if val == 0xFF else (f" ← {bits} bits set" if val and bits >= 6 else "")
            if val is not None and (bits >= 6 or val == 0):
                print(f"    0x{addr:08X} (base+0x{BADGES_OFFSET+delta:02X}): {val:3d} = {bin(val)}{marker}")


def scan_battle():
    """Test battle detection — run inside and outside a battle."""
    print("\nBattle detection test")
    print("Run this once on the overworld, once inside a battle.\n")
    flags = read_u32(ADDR_BATTLE_FLAGS)
    print(f"  gBattleTypeFlags (0x{ADDR_BATTLE_FLAGS:08X}): 0x{flags:08X} = {flags}")
    if flags == 0:
        print("  → NOT in battle (flags = 0)")
    else:
        print(f"  → IN BATTLE (flags non-zero: {flags})")
        if flags & 0x08: print("    Trainer battle")
        if flags & 0x01: print("    Double battle")
        if not (flags & 0x08): print("    Wild battle")

    print(f"\n  Also scanning nearby addresses for battle indicators:")
    for offset in range(-8, 32, 4):
        addr = ADDR_BATTLE_FLAGS + offset
        val = read_u32(addr)
        marker = " ← configured" if offset == 0 else ""
        print(f"    0x{addr:08X}: 0x{val:08X}{marker}" if val is not None else f"    0x{addr:08X}: read error")


def watch_state():
    """Live-updating state dump — Ctrl+C to stop."""
    print("Live state watch (Ctrl+C to stop)...\n")
    try:
        while True:
            state = read_game_state()
            if state:
                battle_str = "⚔ IN BATTLE" if state.get("in_battle") else "🗺 Overworld"
                coords = f"x={state.get('player_x',0)}, y={state.get('player_y',0)}"
                badges = len(state.get("badges", []))
                team   = ", ".join(
                    f"{p['name']} Lv{p['level']} {p['hp']}HP"
                    for p in state.get("team", [])
                )
                line = f"[{battle_str}] {state['location']} ({coords}) | {badges} badges | {team}"
            else:
                line = "RetroArch unreachable..."
            # Clear line then print (works in both cmd and PowerShell)
            print(f"\r{' ' * 120}\r{line}", end="", flush=True)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    {
        "full":   full_diagnostic,
        "coords": scan_coords,
        "badges": scan_badges,
        "battle": scan_battle,
        "watch":  watch_state,
    }.get(mode, full_diagnostic)()

# ============================================================
#  ram_reader.py — reads live game state from RetroArch memory
#  Uses RetroArch's Network Command interface (UDP)
# ============================================================

import socket
import struct
import os
import json

# --- Connection ---
RETROARCH_HOST = "127.0.0.1"
RETROARCH_PORT = 55355
TIMEOUT        = 2.0

# ---------------------------------------------------------------
# GBA memory addresses — confirmed working for Pokémon Unbound
# (FireRed-based ROM hack — most addresses match FireRed decomp)
# ---------------------------------------------------------------

# Current map — CONFIRMED WORKING
ADDR_MAP_BANK   = 0x02036DFD   # 1 byte — map bank (area group)
ADDR_MAP_NUMBER = 0x02036DFC   # 1 byte — map number within bank

# Player position — gObjectEvents[0].currentCoords (object event struct, 0x10/0x12 offset)
# gObjectEvents array starts at 0x02036E38; player is always object 0
# Previous wrong values were 0x02036E34/36 (before the struct)
ADDR_PLAYER_X   = 0x02036E48   # 2 bytes LE — gObjectEvents[0] + 0x10
ADDR_PLAYER_Y   = 0x02036E4A   # 2 bytes LE — gObjectEvents[0] + 0x12

# Party — CONFIRMED WORKING
ADDR_PARTY_COUNT = 0x02024029  # 1 byte — number of Pokémon in party (0-6)
ADDR_PARTY_START = 0x02024284  # Party data — each Pokémon is 100 bytes

# Badges — read through SaveBlock1 pointer for Unbound compatibility
# Unbound expanded SaveBlock1 so the vanilla FireRed hardcoded address (0x02025044) is wrong
# gSaveBlock1Ptr lives in IWRAM at 0x03005008; badges are at SaveBlock1 + BADGES_OFFSET
ADDR_SAVEBLOCK1_PTR = 0x03005008  # IWRAM pointer → SaveBlock1 base address
BADGES_OFFSET       = 0x51        # bytes into SaveBlock1 where the badge bitfield lives
                                   # (0x5C is vanilla FireRed — Unbound shifted it to 0x51)
# Fallback candidates if pointer read fails (try in order):
BADGES_FALLBACK_ADDRS = [0x02025044, 0x020250A4, 0x02025734 + 0x5C]

# Battle state — gBattleTypeFlags (non-zero = in battle)
# 0 = overworld/menu, >0 = battle active (flags indicate wild/trainer/double etc.)
ADDR_BATTLE_FLAGS   = 0x02022B4C  # 4 bytes (u32)
BATTLE_TYPE_TRAINER = 0x08        # bit 3 = trainer battle
BATTLE_TYPE_DOUBLE  = 0x01        # bit 0 = double battle

# Pokémon struct offsets (within each 100-byte party slot)
# Layout: 0x00–0x4F = BoxPokemon (header + 4 encrypted substructs)
#         0x50–0x63 = BattleStats (unencrypted — safe to read directly)
OFFSET_NICKNAME  = 0x08   # 10 bytes, GBA text encoding (unencrypted header)
OFFSET_SPECIES   = 0x20   # 2 bytes, little-endian (encrypted — works when PID%24 puts Growth first)
OFFSET_STATUS    = 0x50   # 4 bytes, status condition (0 = healthy) — unencrypted
OFFSET_LEVEL     = 0x54   # 1 byte, current level — unencrypted
OFFSET_HP        = 0x56   # 2 bytes, current HP — unencrypted (was wrongly 0x38, inside encrypted section)
OFFSET_MAX_HP    = 0x58   # 2 bytes, max HP — unencrypted
OFFSET_MOVE1     = 0x28   # 2 bytes, move ID (encrypted)
OFFSET_MOVE2     = 0x2A
OFFSET_MOVE3     = 0x2C
OFFSET_MOVE4     = 0x2E

# Pokémon size in party array
POKEMON_SIZE     = 100

# Map lookup file (built up as you play)
MAP_LOOKUP_FILE  = os.path.join(os.path.dirname(__file__), "map_lookup.json")

# ---------------------------------------------------------------
# GBA text encoding → readable string
# ---------------------------------------------------------------

GBA_CHARSET = {
    0xBB: 'A', 0xBC: 'B', 0xBD: 'C', 0xBE: 'D', 0xBF: 'E',
    0xC0: 'F', 0xC1: 'G', 0xC2: 'H', 0xC3: 'I', 0xC4: 'J',
    0xC5: 'K', 0xC6: 'L', 0xC7: 'M', 0xC8: 'N', 0xC9: 'O',
    0xCA: 'P', 0xCB: 'Q', 0xCC: 'R', 0xCD: 'S', 0xCE: 'T',
    0xCF: 'U', 0xD0: 'V', 0xD1: 'W', 0xD2: 'X', 0xD3: 'Y',
    0xD4: 'Z',
    0xD5: 'a', 0xD6: 'b', 0xD7: 'c', 0xD8: 'd', 0xD9: 'e',
    0xDA: 'f', 0xDB: 'g', 0xDC: 'h', 0xDD: 'i', 0xDE: 'j',
    0xDF: 'k', 0xE0: 'l', 0xE1: 'm', 0xE2: 'n', 0xE3: 'o',
    0xE4: 'p', 0xE5: 'q', 0xE6: 'r', 0xE7: 's', 0xE8: 't',
    0xE9: 'u', 0xEA: 'v', 0xEB: 'w', 0xEC: 'x', 0xED: 'y',
    0xEE: 'z',
    0xA1: '0', 0xA2: '1', 0xA3: '2', 0xA4: '3', 0xA5: '4',
    0xA6: ' 5', 0xA7: '6', 0xA8: '7', 0xA9: '8', 0xAA: '9',
    0x00: ' ', 0xFF: '',  # terminator
}

def decode_gba_string(data: bytes) -> str:
    result = []
    for byte in data:
        if byte == 0xFF:
            break
        result.append(GBA_CHARSET.get(byte, '?'))
    return ''.join(result).strip()


# ---------------------------------------------------------------
# RetroArch network command helpers
# ---------------------------------------------------------------

def _send_command(cmd: str) -> bytes:
    """Send a command to RetroArch and return the raw response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(TIMEOUT)
    try:
        s.sendto(cmd.encode(), (RETROARCH_HOST, RETROARCH_PORT))
        data, _ = s.recvfrom(4096)
        return data
    except socket.timeout:
        return b""
    except Exception:
        return b""
    finally:
        s.close()


def read_memory(address: int, num_bytes: int) -> bytes | None:
    """
    Read `num_bytes` bytes from GBA memory at `address`.
    Returns raw bytes or None on failure.
    """
    cmd = f"READ_CORE_MEMORY {address:#010x} {num_bytes}"
    response = _send_command(cmd)
    if not response:
        return None
    # Response format: "READ_CORE_MEMORY <addr> <hex bytes space-separated>"
    try:
        parts = response.decode().strip().split()
        # parts[0] = "READ_CORE_MEMORY", parts[1] = addr, parts[2:] = hex values
        hex_values = parts[2:]
        return bytes(int(h, 16) for h in hex_values)
    except Exception:
        return None


def read_u8(address: int) -> int | None:
    data = read_memory(address, 1)
    return data[0] if data else None


def read_u16(address: int) -> int | None:
    data = read_memory(address, 2)
    return struct.unpack_from('<H', data)[0] if data and len(data) >= 2 else None


def read_u32(address: int) -> int | None:
    data = read_memory(address, 4)
    return struct.unpack_from('<I', data)[0] if data and len(data) >= 4 else None


# ---------------------------------------------------------------
# Map name lookup
# ---------------------------------------------------------------

def _load_map_lookup() -> dict:
    if os.path.isfile(MAP_LOOKUP_FILE):
        with open(MAP_LOOKUP_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_map_lookup(lookup: dict):
    with open(MAP_LOOKUP_FILE, 'w') as f:
        json.dump(lookup, f, indent=2)


def get_map_name(bank: int, number: int, lookup: dict) -> str:
    key = f"{bank}:{number}"
    return lookup.get(key, f"Map {bank}-{number} (unknown — type 'set location: NAME' to name it)")


def register_map_name(bank: int, number: int, name: str):
    """Save a human-readable name for a map ID."""
    lookup = _load_map_lookup()
    lookup[f"{bank}:{number}"] = name
    _save_map_lookup(lookup)
    return name


# ---------------------------------------------------------------
# Species name lookup (National Dex number → name)
# Built-in for Gens 1-8 common Pokémon
# ---------------------------------------------------------------

SPECIES_NAMES = {
    1:'Bulbasaur',2:'Ivysaur',3:'Venusaur',4:'Charmander',5:'Charmeleon',
    6:'Charizard',7:'Squirtle',8:'Wartortle',9:'Blastoise',25:'Pikachu',
    26:'Raichu',133:'Eevee',134:'Vaporeon',135:'Jolteon',136:'Flareon',
    149:'Dragonite',150:'Mewtwo',151:'Mew',152:'Chikorita',155:'Cyndaquil',
    158:'Totodile',175:'Togepi',196:'Espeon',197:'Umbreon',
    246:'Larvitar',247:'Pupitar',248:'Tyranitar',
    252:'Treecko',255:'Torchic',258:'Mudkip',
    282:'Gardevoir',
    304:'Aron',305:'Lairon',306:'Aggron',
    334:'Altaria',
    350:'Milotic',
    373:'Salamence',376:'Metagross',
    380:'Latias',381:'Latios',
    382:'Kyogre',383:'Groudon',384:'Rayquaza',
    385:'Jirachi',386:'Deoxys',
    387:'Turtwig',390:'Chimchar',393:'Piplup',
    420:'Cherubi',430:'Honchkrow',
    431:'Glameow',445:'Garchomp',
    448:'Lucario',460:'Abomasnow',
    461:'Weavile',462:'Magnezone',
    470:'Leafeon',471:'Glaceon',
    474:'Porygon-Z',
    480:'Uxie',481:'Mesprit',482:'Azelf',
    483:'Dialga',484:'Palkia',487:'Giratina',
    491:'Darkrai',493:'Arceus',
    495:'Snivy',498:'Tepig',501:'Oshawott',
    529:'Drilbur',530:'Excadrill',
    569:'Garbodor',570:'Zorua',571:'Zoroark',
    610:'Axew',612:'Haxorus',
    621:'Druddigon',633:'Deino',635:'Hydreigon',
    643:'Reshiram',644:'Zekrom',646:'Kyurem',
    650:'Chespin',653:'Fennekin',656:'Froakie',
    670:'Floette',671:'Florges',
    700:'Sylveon',701:'Hawlucha',
    706:'Goodra',
    716:'Xerneas',717:'Yveltal',718:'Zygarde',
    720:'Hoopa',721:'Volcanion',
    722:'Rowlet',725:'Litten',728:'Popplio',
    740:'Crabominable',
    745:'Lycanroc',746:'Wishiwashi',
    774:'Minior',778:'Mimikyu',
    785:'Tapu Koko',786:'Tapu Lele',787:'Tapu Bulu',788:'Tapu Fini',
    789:'Cosmog',791:'Solgaleo',792:'Lunala',
    800:'Necrozma',801:'Magearna',802:'Marshadow',
    807:'Zeraora',
}

def get_species_name(species_id: int) -> str:
    return SPECIES_NAMES.get(species_id, f"Pokémon #{species_id}")


# ---------------------------------------------------------------
# Badge reader — follows SaveBlock1 pointer for Unbound compat
# ---------------------------------------------------------------

def _read_badges() -> int:
    """
    Read the badge bitfield, following the SaveBlock1 pointer.
    Falls back to hardcoded addresses if the pointer read fails.
    Returns 0 if nothing works.
    """
    # Try pointer approach first (most reliable for Unbound)
    ptr = read_u32(ADDR_SAVEBLOCK1_PTR)
    if ptr and 0x02000000 <= ptr <= 0x02040000:
        badge_byte = read_u8(ptr + BADGES_OFFSET)
        if badge_byte is not None:
            return badge_byte

    # Fallback: try known candidate addresses
    for addr in BADGES_FALLBACK_ADDRS:
        badge_byte = read_u8(addr)
        if badge_byte is not None and badge_byte != 0xFF:
            return badge_byte

    return 0


# ---------------------------------------------------------------
# Battle state detector
# ---------------------------------------------------------------

def read_battle_state() -> dict:
    """
    Read whether a battle is currently active.
    Returns a dict with:
      in_battle:      bool
      is_trainer:     bool
      is_double:      bool
      battle_flags:   raw int (0 = not in battle)
    """
    flags = read_u32(ADDR_BATTLE_FLAGS) or 0
    return {
        "in_battle":    flags != 0,
        "is_trainer":   bool(flags & BATTLE_TYPE_TRAINER),
        "is_double":    bool(flags & BATTLE_TYPE_DOUBLE),
        "battle_flags": flags,
    }


# ---------------------------------------------------------------
# High-level game state reader
# ---------------------------------------------------------------

def read_game_state() -> dict | None:
    """
    Read the full current game state from RAM.
    Returns a dict, or None if RetroArch is unreachable.
    """
    # Quick connectivity check
    if read_u8(ADDR_MAP_BANK) is None:
        return None

    lookup = _load_map_lookup()

    # --- Location ---
    map_bank   = read_u8(ADDR_MAP_BANK)   or 0
    map_number = read_u8(ADDR_MAP_NUMBER) or 0
    location   = get_map_name(map_bank, map_number, lookup)
    player_x   = read_u16(ADDR_PLAYER_X) or 0
    player_y   = read_u16(ADDR_PLAYER_Y) or 0

    # --- Badges ---
    badge_byte = _read_badges()
    # Borrius region badge names — verified from unboundwiki.com
    # Gym order: Dresco → Crater → Blizzard → Fallshore → Dehara → Antisis → Polder → Redwood
    badge_names = [
        "Leaf Badge",    # Gym 1 — Mirskle (Dresco Town, Grass/Fairy)
        "Vision Badge",  # Gym 2 — Véga (Crater Town, Dark)
        "Wings Badge",   # Gym 3 — Alice (Blizzard City, Flying)
        "Fall Badge",    # Gym 4 — Mel (Fallshore City, Normal/Inverse)
        "Battery Badge", # Gym 5 — Galavan (Dehara City, Electric+Steel)
        "Ring Badge",    # Gym 6 — Big Mo (Antisis City, Fighting)
        "Swamp Badge",   # Gym 7 — Tessy (Polder Town, Water)
        "Time Badge",    # Gym 8 — Benjamin (Redwood Village, Bug)
    ]
    badges = [badge_names[i] for i in range(8) if badge_byte & (1 << i)]

    # --- Party ---
    party_count = read_u8(ADDR_PARTY_COUNT) or 0
    party_count = min(party_count, 6)
    team = []

    for i in range(party_count):
        base = ADDR_PARTY_START + i * POKEMON_SIZE
        slot_data = read_memory(base, POKEMON_SIZE)
        if not slot_data or len(slot_data) < POKEMON_SIZE:
            continue

        species  = struct.unpack_from('<H', slot_data, OFFSET_SPECIES)[0]
        level    = slot_data[OFFSET_LEVEL]
        hp       = struct.unpack_from('<H', slot_data, OFFSET_HP)[0]
        max_hp   = struct.unpack_from('<H', slot_data, OFFSET_MAX_HP)[0]
        status   = struct.unpack_from('<I', slot_data, OFFSET_STATUS)[0]
        nickname = decode_gba_string(slot_data[OFFSET_NICKNAME:OFFSET_NICKNAME+10])

        status_str = "Healthy"
        if hp == 0:           status_str = "Fainted"
        elif status & 0x07:   status_str = "Asleep"
        elif status & 0x08:   status_str = "Poisoned"
        elif status & 0x40:   status_str = "Badly Poisoned"
        elif status & 0x80:   status_str = "Burned"
        elif status & 0x100:  status_str = "Frozen"
        elif status & 0x200:  status_str = "Paralyzed"

        # Egg detection — nickname "Egg" + level <= 2 is the reliable signal.
        # The personality bit-30 approach produced false positives on real Pokémon.
        nick_lower = nickname.lower().strip()
        is_egg     = nick_lower in ("egg", "タマゴ") and level <= 2

        if is_egg:
            name = "Egg"
            status_str = "Egg"
        else:
            name = nickname if nickname and '?' not in nickname else get_species_name(species)

        team.append({
            "name":    name,
            "species": "Egg" if is_egg else get_species_name(species),
            "level":   level,
            "hp":      hp,
            "max_hp":  max_hp,
            "status":  status_str,
            "is_egg":  is_egg,
        })

    battle = read_battle_state()

    return {
        "location":    location,
        "map_bank":    map_bank,
        "map_number":  map_number,
        "player_x":    player_x,
        "player_y":    player_y,
        "badges":      badges,
        "team":        team,
        "in_battle":   battle["in_battle"],
        "is_trainer":  battle["is_trainer"],
        "is_double":   battle["is_double"],
        "active_goal": None,
        "notes":       [],
    }


if __name__ == "__main__":
    print("Reading game state from RetroArch...")
    state = read_game_state()
    if state is None:
        print("Could not connect to RetroArch. Is it running with Network Commands enabled?")
    else:
        import json
        print(json.dumps(state, indent=2))

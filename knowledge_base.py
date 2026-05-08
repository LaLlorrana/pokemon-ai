# ============================================================
#  knowledge_base.py — Pokémon Unbound knowledge base
#  ALL data sourced from unboundwiki.com wiki files.
#  Zero hallucination policy — if uncertain, it's not here.
# ============================================================

UNBOUND_KNOWLEDGE = """
=== POKÉMON UNBOUND — VERIFIED KNOWLEDGE BASE ===
Source: unboundwiki.com

--- OVERVIEW ---
Pokémon Unbound is a fan-made GBA ROM hack of Pokémon FireRed by Skeli789.
Region: Borrius (custom region, split into West Borrius and East Borrius).
Pokémon from Generations 1–8 are obtainable (Gen 8 requires post-game activation).
The art style resembles FireRed because Unbound uses FireRed's engine — the content is different.

--- STARTERS (NOT Fire/Water/Grass) ---
You choose one of three Pokémon from a crate in Shadow Base at the start:
  - Beldum (Lv.10) — if you pick Beldum, rival takes Gible
  - Gible  (Lv.10) — if you pick Gible, rival takes Larvitar
  - Larvitar (Lv.10) — if you pick Larvitar, rival takes Beldum

--- KEY CHARACTERS ---
- Professor Log: your mentor, located in Frozen Heights. Researches Pokémon stats.
- Rival: Jax — red-haired boy, your rival throughout the game.
- The Shadow: the main antagonist organization (NOT "the Shadows").
  They capture legendary Pokémon and seek to unleash a dark power in Borrius.
- Shadow Boss: Zeph
- Shadow Admins include: Ivory, Marlon

--- STARTING AREA ---
The game begins in Shadow Base (enemy headquarters).
After escaping, you arrive in Frozen Heights — your hometown.
Frozen Heights has: Professor Log's lab, your house, your rival's house.
Route 1 leads south from Frozen Heights to Bellin Town.

--- DIFFICULTY MODES ---
- Vanilla: standard balanced difficulty (recommended for first playthroughs)
- Difficult: stronger trainers, accessible from Vanilla at any point
- Expert: even harder; only available at game start
- Insane: hardest mode; only available at game start
Note: You CANNOT switch from Vanilla to harder modes to farm Exp and switch back.

--- KEY GAME MECHANICS ---
UNIVERSAL HMs (CRITICAL — unique to Unbound):
  ANY Pokémon in your party can use any HM field move without being taught it.
  No HM slaves needed. Your whole party can be battle-ready.
  To use a field move: START → Pokémon → select any party member → choose move.

THE CUBE (replaces the Bag):
  There is no traditional "Bag" in Pokémon Unbound.
  The Cube is your personal assistant and digital item storage device.
  Components include: Mission Log, battle items storage, Pokédex, more.

POKÉMON STORAGE:
  Pokémon are stored via Porygon NPCs found in Pokémon Centers and some buildings.
  Look for a Porygon to access your PC box.

DAY/NIGHT CYCLE:
  Day:   5:00am – 7:59pm
  Night: 8:00pm – 4:59am
  Wild Pokémon availability can differ between day and night.

EXP SHARE:
  Gen 6 style — applies Exp to your whole team by default.
  Can be toggled off in game settings.

REUSABLE TMs:
  All TMs are reusable (120 TMs + 8 HMs total).

MEGA EVOLUTION:
  Obtained during Tarmigan Mansion story event (Part 16 of walkthrough).
  Requires the Mega Keystone.

Gen 8 Pokémon:
  Not available in the wild by default.
  Activate by registering a Galar Pokémon via trade or Mystery Gift.
  Mystery Gift requires defeating the Elite Four first.

MOTORCYCLE:
  Obtained in Crater Town (KBT Expressway story event).
  Replaces the bicycle for faster overworld movement.

--- GYM ORDER & LEADERS (VERIFIED) ---
Gym 1:  Dresco Town Gym    — Leader: Mirskle — Type: Grass/Fairy mix — Badge: Leaf Badge
        TM reward: TM86 Grass Knot.  Gym has fog (bring Defog).
Gym 2:  Crater Town Gym    — Leader: Véga    — Type: Dark           — Badge: Vision Badge
        TM reward: TM46 Thief.  Vision Badge unlocks Cut usage outside battle.
Gym 3:  Blizzard City Gym  — Leader: Alice   — Type: Flying         — Badge: Wings Badge
        TM reward: TM40 Aerial Ace.  Wings Badge unlocks Rock Smash usage.
Gym 4:  Fallshore City Gym — Leader: Mel     — Type: Normal (Inverse Battle rules) — Badge: Fall Badge
        TM reward: TM42 Facade.  Mel gives HM02 Fly outside gym after you defeat him.
        IMPORTANT: Fallshore Gym uses INVERSE battle rules — type effectiveness is reversed!
        Do NOT use Fighting-type moves — they will be ineffective under inverse rules.
Gym 5:  Dehara City Gym    — Leader: Galavan — Type: Electric + Steel mix — Badge: Battery Badge
        TM reward: TM92 Volt Switch.  Battery Badge unlocks Surf usage.
        IMPORTANT: Galavan's gym uses both Electric AND Steel types.
Gym 6:  Antisis City Gym   — Leader: Big Mo  — Type: Fighting       — Badge: Ring Badge
        TM reward: TM60 Drain Punch.
Gym 7:  Polder Town Gym    — Leader: Tessy   — Type: Water          — Badge: Swamp Badge
        Reward: HM07 Waterfall.  Swamp Badge unlocks Max Potion in shops.
Gym 8:  Redwood Village Gym — Leader: Benjamin — Type: Bug          — Badge: Time Badge
        TM reward: TM49 Leech Fang.  Time Badge unlocks Full Restore in shops.

--- GYM LEADER TEAMS (VANILLA DIFFICULTY, KEY PARTY MEMBERS) ---
Mirskle (Gym 1, Lv.15-16): Flabebe, Gloom
Véga    (Gym 2, Lv.21-23): Liepard, Absol, Sneasel
Alice   (Gym 3, Lv.28-30): Doduo, Gliscor, Minior
Mel     (Gym 4, Lv.33-34): Helioptile, Miltank, Lopunny (all under Inverse rules)
Galavan (Gym 5, Lv.42-44): Golem, Eelektross, Magneton, Mega Manectric
Big Mo  (Gym 6, Lv.51-52): Mienshao, Mega Lucario, Pangoro, Hariyama
Tessy   (Gym 7, Lv.54-56): Toxapex, Mega Gyarados, Armaldo, Seismitoad
Benjamin (Gym 8, Lv.59-61): Araquanid, Drapion, Mega Scizor, Butterfree

--- ELITE FOUR & CHAMPION (VERIFIED) ---
Elite Four Moleman  — Ground type. Double battle with Vicious Sandstorm field effect.
  Party: Excadrill, Flygon, Sandslash, Quagsire, Gliscor. Has 2 Full Restores.
Elite Four Elias    — Ghost type. Shadowy Veil field effect.
  Party: Mimikyu, Aegislash, Trevenant, Chandelure, Mega Banette. Has 1 Full Restore.
Elite Four Arabella — Fairy type. Permanent Misty Terrain.
  Party: Ribombee, Sylveon, Togekiss, Azumarill, Mega Mawile. Has 2 Full Restores.
Elite Four Penny    — Dragon type. Double-rainbow battle.
  Party: Goodra, Tyrantrum, Kommo-o, Hydreigon, Mega Sceptile. Has 2 Full Restores.
Final — Rival Jax (Double battle):
  Party: Mega Salamence, Hitmontop, Magnezone, Gastrodon, Pyroar, Staraptor.
  Has 3 Full Restores.

--- HM LOCATIONS & BADGE REQUIREMENTS (VERIFIED) ---
HM01 Cut       — KBT Expressway (given by mountain climber NPC after a story cutscene).
                 Requires Vision Badge (Crater Town Gym) to use outside battle.
HM02 Fly       — Given by Mel outside Fallshore City Gym after defeating him.
                 No badge required — usable immediately after receiving it.
HM03 Surf      — Route 12 (given by Rival Jax after you gain Mega Evolution ability).
                 Requires Battery Badge (Dehara City Gym) to use outside battle.
HM04 Strength  — Epidimy Town, west-most house (NPC gift).
HM05 Dive      — Post-game only. Buy ADM from Captain Davy's Shipyard in Seaport City
                 for 250,000 Pokémon Dollars; he gives HM Dive too.
HM06 Rock Smash — Blizzard City, north-most house (Mountain Climber NPC).
                 Requires Wings Badge (Blizzard City Gym) to use outside battle.
HM07 Waterfall — Reward for defeating Tessy at Polder Town Gym.
HM08 Rock Climb — Route 17 (construction worker NPC).

--- HOW TO USE FLY ---
Fly is given by Mel after defeating him at Fallshore City Gym (Gym 4).
To use Fly: START → Pokémon → select any party member → Fly → region map opens.
Use arrow keys to move cursor to the destination town, press A to fly there.
You can only fly to towns you have previously visited.
ALWAYS use Fly when the destination is far away.

--- LOCATION PROGRESSION (VERIFIED ORDER) ---
Shadow Base → Frozen Heights → Route 1 → Bellin Town → Icicle Cave →
Route 2 → Dresco Town [Gym 1] → Route 3 → Grim Woods → Route 4 →
Cinder Volcano → Route 5 → Pokémon Day Care → Crater Town [Gym 2] →
KBT Expressway → Valley Cave → Route 6 → Route 7 → Frost Mountain →
Route 8 → Frozen Forest → Blizzard City [Gym 3] → Route 9 → Underground Pass →
Tehl Town → Route 10 → Fallshore City [Gym 4] → Route 11 → Epidimy Town →
Thundercap Mountain → Cliff Cave → Tarmigan Town → Tarmigan Mansion →
Route 12 → Dehara City [Gym 5] → Great Desert → Gurun Town → Auburn Waterway →
Lost Tunnel → Ruins of Void → Vivill Woods → Vivill Town → Vivill Warehouse →
Routes 13-16 → Antisis City [Gym 6] → Antisis Port → Antisis Sewers →
Route 17 → Seaport City → (boat to East Borrius) →
Polder Town [Gym 7] → Safari Zone → Cootes Bog → Magnolia Town →
Magnolia Fields → Redwood Village [Gym 8] → Redwood Forest → Cube Corp →
Crystal Peak → Route 18 → Victory Road → Pokémon League

--- KEY LOCATION NOTES ---
KBT Expressway: Major underground expressway connecting most cities/towns in Borrius.
  Think of it as the game's highway system. Many story events occur here.
Dehara City: Large city with Department Store (sells expensive TMs), Game Corner (coins).
Fallshore City: Has Mission HQ (where you accept and turn in side missions).
Seaport City: Port city. Has Battle Frontier, SS Marine. Boat to East Borrius.
Ruins of Void: Major story location. Multiple basement floors. Connected to Hoopa.
Tarmigan Town: Has Dream Research Lab. Tarmigan Mansion is where you get Mega Evolution.
Dresco Town: Islands connected by bridges. Home to Trainer House (grinding spot).
Battle Frontier: Post-game facility in Seaport City area. Has Battle Tower.
Crystal Peak: Cave system. Connected to Cube Corp and Redwood Forest.

--- SHOP UNLOCK PROGRESSION ---
Items unlock in Pokémon Marts as you earn gym badges:
  Start:           Poké Ball, Potion, Antidote, Paralyze Heal, Ice Heal, Escape Rope, Repel
  Leaf Badge:      Super Potion, Awakening, Burn Heal
  Vision Badge:    Great Ball, Super Repel
  Wings Badge:     Revive
  Fall Badge:      Ultra Ball
  Battery Badge:   Hyper Potion, Max Repel, Full Heal
  Swamp Badge:     Max Potion
  Time Badge:      Full Restore

--- BATTLE STRATEGY PRINCIPLES ---
- Always consider type matchups before selecting a move.
- STAB (Same Type Attack Bonus) = 1.5× damage.
- Fallshore Gym (Gym 4) uses INVERSE rules — check this carefully.
- In Expert/Insane modes: AI uses held items, smart movesets, and switches well.
- Status moves (Thunder Wave, Will-O-Wisp, Toxic) are very effective.
- Priority moves (Quick Attack, Aqua Jet, Bullet Punch, Mach Punch, Sucker Punch) are key.
- Entry hazards (Stealth Rock, Spikes) matter in longer fights.
- Setup sweepers (Dragon Dance, Swords Dance, Calm Mind) can win games if unanswered.

--- TYPE MATCHUP CHART (Attacking → Defending) ---
Normal:   no strengths; weak to Fighting; immune to Ghost.
Fire:     strong vs Grass, Ice, Bug, Steel; weak to Water, Rock, Ground.
Water:    strong vs Fire, Ground, Rock; weak to Electric, Grass.
Electric: strong vs Water, Flying; weak to Ground only; Ground-type Pokémon are immune.
Grass:    strong vs Water, Ground, Rock; weak to Fire, Ice, Poison, Flying, Bug.
Ice:      strong vs Grass, Ground, Flying, Dragon; weak to Fire, Fighting, Rock, Steel.
Fighting: strong vs Normal, Ice, Rock, Dark, Steel; weak to Flying, Psychic, Fairy.
Poison:   strong vs Grass, Fairy; weak to Ground, Psychic.
Ground:   strong vs Fire, Electric, Poison, Rock, Steel; weak to Water, Grass, Ice; immune to Electric.
Flying:   strong vs Grass, Fighting, Bug; weak to Electric, Ice, Rock; immune to Ground.
Psychic:  strong vs Fighting, Poison; weak to Bug, Ghost, Dark.
Bug:      strong vs Grass, Psychic, Dark; weak to Fire, Flying, Rock.
Rock:     strong vs Fire, Ice, Flying, Bug; weak to Water, Grass, Fighting, Ground, Steel.
Ghost:    strong vs Ghost, Psychic; weak to Ghost, Dark; immune to Normal, Fighting.
Dragon:   strong vs Dragon; weak to Ice, Dragon, Fairy; Fairy-type Pokémon are immune.
Dark:     strong vs Ghost, Psychic; weak to Fighting, Bug, Fairy; immune to Psychic.
Steel:    strong vs Ice, Rock, Fairy; weak to Fire, Fighting, Ground; immune to Poison.
Fairy:    strong vs Fighting, Dragon, Dark; weak to Poison, Steel; immune to Dragon.

--- HELD ITEMS TO KNOW ---
Choice Band/Specs/Scarf: lock into one move; boost Atk / SpAtk / Speed respectively.
Life Orb:    1.3× damage at cost of 10% HP per move used.
Leftovers:   restore 1/16 HP per turn — great for tanky Pokémon.
Rocky Helmet: damages physical attackers on contact.
Eviolite:    boosts Def and SpDef by 1.5× for unevolved Pokémon.
Focus Sash:  survive one hit from full HP.
Assault Vest: boosts SpDef by 1.5× but prevents non-damaging moves.

--- USEFUL MOVES ---
Stealth Rock:  entry hazard that deals type-based damage to switching Pokémon.
U-turn / Volt Switch: deal damage and switch out — excellent for momentum.
Knock Off:     removes held item and deals extra damage — one of the best moves.
Will-O-Wisp:   burns target, halving physical Attack.
Toxic:         badly poisons; damage increases each turn.
Defog:         removes entry hazards and lowers evasion. Useful in Dresco Gym (fog).
Roost / Recover / Moonlight: healing moves for stall strategies.
Dragon Dance / Swords Dance / Calm Mind: setup moves; answer them quickly.

--- MISSIONS (SIDE QUESTS) ---
84 side missions available. Tracked in the Mission Log (Cube).
Mission HQ is in Fallshore City.
Completing 20 missions rewards Type: Null from Mission HQ.
Completing 45 missions and talking to Mission HQ NPC begins Latias/Latios roaming.
Some missions reward rare Pokémon, TMs, or items.
Notable early missions: "The Food Thief" (Bellin Town), "The Black Emboar" (Crater Town).

--- USEFUL NPCs ---
IV Changer:      West of Seaport City port. Costs Bottle Caps.
EV Changer:      Battle Frontier east stall. Costs Battle Points.
Nature Changers: Tehl Town (house SW of Pokémon Center) or Battle Frontier.
Move Relearner:  South of Crater Town Pokémon Center. Costs Heart Scale.
Move Deleter:    NW of Epidimy Town Pokémon Center.
Egg Move Tutor:  West stall of Battle Frontier entrance. Costs Battle Points.
Name Rater:      South-most house in Tehl Town.
Trainer House:   Dresco Town. Battle 4 trainers repeatedly for grinding.

--- LEGENDARY POKÉMON (KEY ONES) ---
Articuno:  Frozen Heights (post-game)
Zapdos:    Thundercap Mountain peak (post-game)
Moltres:   Cinder Volcano peak (post-game)
Entei/Raikou: Roaming after interacting with portal in Tomb of Borrius
Suicune:   Ruins of Void (after catching Entei and Raikou)
Hoopa:     Crystal Peak (obtained as part of main story)
Kyurem:    Victory Road snow area (Kyurem Cave)
Groudon:   Cinder Volcano B2F (post-game, needs Red Orb)
Kyogre:    Vivill Warehouse underwater (needs Blue Orb)
Rayquaza:  Crystal Peak post-game (needs Jade Orb)
Giratina:  Distortion World (post-game, via Rift Cave)
Latias/Latios: Roaming (after 45 missions + Mission HQ NPC)
Zygarde:   Dresco Town (mission: "The Powerhouse of the Cell")
Type: Null: Reward for completing 20 missions at Mission HQ Fallshore City.
Heatran:   Cinder Volcano 1F (needs Magma Stone)
Darkrai:   Newmoon Island (post-game, via Tarmigan Town)
Cresselia: Fullmoon Island (post-game)
Regigigas: Icy Hole B1F (needs Regirock, Regice, Registeel caught first)
Cosmog:    Found in a bag on Route 12 beach. Evolves into Solgaleo (day) or Lunala (night).
"""


def get_knowledge() -> str:
    """Return the full Unbound knowledge base string."""
    return UNBOUND_KNOWLEDGE

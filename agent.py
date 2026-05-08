# ============================================================
#  agent.py — PokeBot autonomous agent loop
#
#  Usage:
#    agent = PokeAgent(game_state_ref, log_callback)
#    agent.start("Grind my team to level 35")
#    agent.stop()
# ============================================================

import time
import threading
from vision import capture_screen, ask_llava, image_to_base64
from executor import parse_and_execute, has_actions, set_current_location
from game_state import refresh_from_ram, save_state

try:
    from data_collector import DataCollector
    DATA_COLLECTOR_AVAILABLE = True
except ImportError:
    DATA_COLLECTOR_AVAILABLE = False

try:
    from experience import log_experience, log_battle_win, log_battle_loss, log_navigation
    EXPERIENCE_AVAILABLE = True
except ImportError:
    EXPERIENCE_AVAILABLE = False

try:
    from nav_memory import get_route
    NAV_MEMORY_AVAILABLE = True
except ImportError:
    NAV_MEMORY_AVAILABLE = False

try:
    from location_validator import validate_llm_response
    LOCATION_VALIDATOR_AVAILABLE = True
except ImportError:
    LOCATION_VALIDATOR_AVAILABLE = False

# How long to wait between loop iterations (seconds)
# Long enough for most animations/dialogue to finish
LOOP_DELAY    = 2.0
# Shorter delay after a simple button press (dialogue advance)
FAST_DELAY    = 0.6
# Max consecutive loops with no actions before pausing
MAX_IDLE      = 5

PLANNING_PROMPT = """\
You are planning the best strategy to achieve a goal in Pokémon Unbound.

GOAL: {goal}
CURRENT LOCATION: {location}
BADGES EARNED: {badges}
HMs OBTAINED: {hms}

TEAM:
{team}

Pokémon Unbound rules you MUST apply:
- HMs are UNIVERSAL — any party Pokémon can use any HM field move without being taught it.
- To use Fly: START → Pokémon → select any party member → Fly → region map → pick destination.
- Fly only works for towns you have already visited.
- If the destination is in a different city/town and Fly is available, ALWAYS use Fly as step 1.
- If Fly is not available or the destination is nearby, walk/navigate directly.

Write a SHORT numbered plan (max 6 steps) to reach the goal efficiently.
Be specific — name directions, menus, and moves.
If you would Fly somewhere, say exactly where.
"""

AGENT_PROMPT = """\
You are autonomously playing Pokémon Unbound toward the following goal:
GOAL: {goal}

Current game state:
{state_summary}

YOUR PLAN (follow this step by step):
{plan}

WHAT YOU JUST DID (last {history_len} steps — use this to reason forward):
{history}

IMPORTANT — Your current situation is: {situation}

Look at the screenshot AND your recent action history, then decide what single action to take RIGHT NOW.

{situation_rules}

General rules:
- Use your action history to understand where you are in a multi-step sequence.
- Do NOT repeat an action that clearly didn't work — try something different.
- If you just opened a menu, navigate it — do NOT open it again.
- If there is dialogue or a text box on screen: press A to advance it.
- If the goal appears complete, say: GOAL_COMPLETE
- If you are stuck or unsure, say: STUCK — then briefly explain why.

Respond with action tags (e.g. <<PRESS:A>> or <<SEQ:UP,A>>) plus a ONE LINE explanation.
Keep it short. Speed matters.
"""

BATTLE_RULES = """\
YOU ARE IN A BATTLE. Focus entirely on winning:
- Select the most effective move for the enemy you can see.
- Use type advantages. Check your team's HP and statuses above.
- If a Pokémon has fainted, switch immediately.
- Do NOT try to navigate or use items unless critical."""

OVERWORLD_RULES = """\
YOU ARE ON THE OVERWORLD (no battle active).

TO USE FLY — use the scripted tag, do NOT try to navigate manually:
  <<FLY>>
  This handles everything automatically. After it runs, you will be on the
  region map. Use arrow keys to move the cursor to the destination, then A.

TO USE SURF — use the scripted tag:
  <<SURF>>

MENU NAVIGATION (if a menu is already open):
- NEVER press START if a menu is already visible — that closes it.
- START menu order (top→bottom): Pokédex, Pokémon, Bag, Player Card, Save, Options
- Party submenu order: Summary → [HM moves] → Switch → Item → Cancel
- Navigate with UP/DOWN, confirm with A, go back with B.

REGION MAP (after <<FLY>>):
- Use UP/DOWN/LEFT/RIGHT to move cursor to destination town.
- Press A to confirm and fly there.

OVERWORLD MOVEMENT:
- Navigate with directional inputs.
- Dialogue/text box on screen → press A to advance. Do NOT press START.
- To enter a building, walk up to the door and press A or walk in.
- Only open START when you genuinely need it."""


def _format_history(history: list) -> str:
    """Format recent step history for injection into the agent prompt."""
    if not history:
        return "  (no actions taken yet — this is the first step)"
    lines = []
    for entry in history:
        actions = " → ".join(entry["actions"]) if entry["actions"] else "(no action)"
        lines.append(f"  [Step {entry['step']}] {entry['summary']}  ▶  {actions}")
    return "\n".join(lines)


def _summarise_state(game_state: dict) -> str:
    location = game_state.get("location", "Unknown")
    badges   = ", ".join(game_state.get("badges", [])) or "None"
    team     = game_state.get("team", [])
    team_str = "  " + "\n  ".join(
        f"{p['name']} Lv.{p.get('level','?')} — {p.get('hp',0)}/{p.get('max_hp',1)} HP [{p.get('status','Healthy')}]"
        for p in team
    ) if team else "  (unknown)"
    return f"Location: {location}\nBadges: {badges}\nTeam:\n{team_str}"


class PokeAgent:
    def __init__(self, game_state: dict, log_fn=None, state_update_fn=None):
        """
        game_state:      shared dict (will be mutated by RAM reads)
        log_fn:          callback(message: str) for UI logging
        state_update_fn: callback() to refresh UI after state changes
        """
        self.game_state     = game_state
        self.log            = log_fn or print
        self.state_update   = state_update_fn or (lambda: None)
        self._thread        = None
        self._stop_event    = threading.Event()
        self.running        = False
        self.goal           = ""
        self.step_count     = 0
        self.idle_count     = 0
        self._plan          = ""   # high-level plan generated before loop starts
        self._history       = []   # rolling window of recent steps for context
        self._history_max   = 8    # how many steps to keep in context
        # Self-improvement systems
        self._last_location = ""
        self.collector      = DataCollector() if DATA_COLLECTOR_AVAILABLE else None

    # ── Public API ─────────────────────────────────────────

    def start(self, goal: str):
        if self.running:
            self.stop()
        self.goal           = goal
        self.step_count     = 0
        self.idle_count     = 0
        self._history       = []
        self._last_location = self.game_state.get("location", "")
        self._stop_event.clear()
        self.running        = True
        if self.collector:
            self.collector.start(self.game_state)
            self.log(f"[DataCollector] Recording started — {self.collector.sample_count} existing samples")
        # Focus RetroArch now — PokeBot is WS_EX_NOACTIVATE so it won't steal it back
        try:
            from controller import focus_retroarch
            if focus_retroarch():
                self.log("🎮 RetroArch focused — inputs ready")
            else:
                self.log("⚠ Could not focus RetroArch — inputs may not work")
        except Exception:
            pass
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log(f"▶ Agent started — Goal: {goal} (planning in background...)")

    def stop(self):
        self._stop_event.set()
        self.running = False
        if self.collector:
            self.collector.stop()
        self.log("■ Agent stopped.")

    # ── Pre-loop planning ──────────────────────────────────

    def _make_plan(self) -> str:
        """
        Ask the model to generate a high-level route plan before the action loop.
        Considers Fly, HMs, and current location.
        """
        try:
            img = capture_screen()
            hms = self.game_state.get("hms_obtained", [])
            hms_str = ", ".join(hms) if hms else "Unknown (assume common HMs available)"
            prompt = PLANNING_PROMPT.format(
                goal=self.goal,
                location=self.game_state.get("location", "Unknown"),
                badges=", ".join(self.game_state.get("badges", [])) or "None",
                hms=hms_str,
                team=_summarise_state(self.game_state),
            )
            plan = ask_llava(
                user_message=prompt,
                img=img,
                game_state=self.game_state,
            ).strip()
            return plan
        except Exception as e:
            return f"(Planning failed: {e}) — navigate directly to goal."

    # ── Stuck recovery ─────────────────────────────────────

    def _try_recover(self, stuck_count: int) -> str:
        """
        Attempt to get unstuck based on how many times we've been stuck.
        Returns a description of what was tried, or "" if nothing was done.
        """
        try:
            from controller import press, sequence
        except ImportError:
            return ""

        team = self.game_state.get("team", [])
        all_fainted = team and all(p.get("hp", 1) == 0 for p in team)

        # All Pokémon fainted — open menu and use a revive/potion
        if all_fainted:
            self.log("⚠ Entire team fainted — opening menu to heal")
            sequence(["START", "DOWN", "DOWN", "A"])  # Open bag (rough navigation)
            return "Team fully fainted — opened menu"

        # Attempt 1: press B to back out of whatever we're in
        if stuck_count == 1:
            press("B")
            return "Pressed B (back out of menu/dialogue)"

        # Attempt 2: press B again, then try A
        if stuck_count == 2:
            sequence(["B", "B", "A"])
            return "Pressed B×2 then A"

        # Attempt 3: random directional nudge — try walking in a random direction
        if stuck_count == 3:
            import random
            directions = ["UP", "DOWN", "LEFT", "RIGHT"]
            chosen = random.choice(directions)
            sequence([chosen, chosen, chosen])
            return f"Random movement: {chosen}×3"

        # Attempt 4: more aggressive — try a different random direction
        if stuck_count == 4:
            import random
            directions = ["UP", "DOWN", "LEFT", "RIGHT"]
            chosen = random.choice(directions)
            sequence([chosen] * 5)
            return f"Aggressive nudge: {chosen}×5"

        return ""

    # ── Main loop ──────────────────────────────────────────

    def _loop(self):
        # Generate plan on the background thread — UI stays responsive
        self.log("🧠 Planning route...")
        self._plan = self._make_plan()
        self.log(f"📋 Plan:\n{self._plan}")

        while not self._stop_event.is_set():
            try:
                delay = self._step()
            except Exception as e:
                self.log(f"⚠ Agent error: {e}")
                delay = LOOP_DELAY * 2
            time.sleep(delay)
        self.running = False

    def _step(self) -> float:
        """
        One iteration of the agent loop.
        Returns the delay (seconds) to wait before the next step.
        """
        self.step_count += 1

        # Refresh game state from RAM
        updated = refresh_from_ram(self.game_state)
        self.game_state.update(updated)
        save_state(self.game_state)
        self.state_update()

        # Track location changes for nav experience logging
        current_location = self.game_state.get("location", "")
        if (EXPERIENCE_AVAILABLE
                and self._last_location
                and current_location
                and current_location != "Unknown"
                and current_location != self._last_location):
            log_navigation(self._last_location, current_location,
                           f"Navigated via agent (step {self.step_count})")
            self.log(f"[NavLog] {self._last_location} → {current_location}")
        if current_location and current_location != "Unknown":
            self._last_location = current_location

        # Capture screen
        img = capture_screen()

        # Tell executor where we are so <<FLY:Destination>> can navigate correctly
        set_current_location(self.game_state.get("location", ""))

        # Build prompt — inject battle vs overworld context from RAM
        in_battle = self.game_state.get("in_battle", False)
        if in_battle:
            battle_parts = []
            if self.game_state.get("is_trainer"): battle_parts.append("Trainer")
            if self.game_state.get("is_double"):  battle_parts.append("Double")
            if not battle_parts:                  battle_parts.append("Wild")
            situation      = f"⚔ IN A {' '.join(battle_parts).upper()} BATTLE"
            situation_rules = BATTLE_RULES
        else:
            situation       = "🗺 ON THE OVERWORLD (not in battle)"
            situation_rules = OVERWORLD_RULES

        prompt = AGENT_PROMPT.format(
            goal=self.goal,
            state_summary=_summarise_state(self.game_state),
            plan=self._plan or "No plan — navigate directly to goal.",
            history=_format_history(self._history),
            history_len=len(self._history),
            situation=situation,
            situation_rules=situation_rules,
        )

        # Ask gemma
        response = ask_llava(
            user_message=prompt,
            img=img,
            game_state=self.game_state,
        ).strip()

        # Handle special responses
        if "GOAL_COMPLETE" in response:
            self.log("✅ Goal complete!")
            # Log the completed goal as a strategy experience
            if EXPERIENCE_AVAILABLE:
                location = self.game_state.get("location", "")
                log_experience(
                    category="strategy",
                    situation=f"Goal: {self.goal}",
                    outcome=f"Completed in {self.step_count} steps",
                    location=location,
                    tags=["goal_complete", "agent"],
                )
                self.log(f"[Experience] Logged goal completion: {self.goal[:50]}")
            if self.collector:
                self.collector.record(img, prompt, response, ["GOAL_COMPLETE"])
            self.stop()
            return 0

        if response.startswith("STUCK"):
            self.idle_count += 1
            self.log(f"⚠ Stuck ({self.idle_count}/{MAX_IDLE}): {response}")
            self._history.append({
                "step":    self.step_count,
                "summary": response[:80],
                "actions": ["STUCK"],
            })
            if len(self._history) > self._history_max:
                self._history.pop(0)
            if self.collector:
                self.collector.record(img, prompt, response, ["STUCK"])

            # Attempt recovery before giving up
            recovery_action = self._try_recover(self.idle_count)
            if recovery_action:
                self.log(f"↩ Recovery attempt {self.idle_count}: {recovery_action}")

            if self.idle_count >= MAX_IDLE:
                if EXPERIENCE_AVAILABLE:
                    location = self.game_state.get("location", "")
                    log_experience(
                        category="navigation",
                        situation=f"Goal: {self.goal} — got stuck",
                        outcome=response[:200],
                        location=location,
                        tags=["stuck", "agent"],
                    )
                self.log("■ Agent paused — too many stuck states. Check the game.")
                self.stop()
            return LOOP_DELAY * 2

        # Parse and execute actions
        if has_actions(response):
            # Validate locations before executing
            if LOCATION_VALIDATOR_AVAILABLE:
                is_valid, fakes = validate_llm_response(response)
                if not is_valid:
                    fake_list = ", ".join(fakes)
                    self.log(f"⚠️ HALLUCINATION DETECTED: {fake_list}")
                    self.log(f"❌ Rejecting action — LLM invented fake locations")
                    self.idle_count += 1
                    return LOOP_DELAY * 2
            clean, action_log = parse_and_execute(response, execute=True)
            log_line = clean.strip().split("\n")[0][:80] if clean.strip() else ""
            actions_str = " → ".join(action_log)
            self.log(f"[{self.step_count}] {log_line}  ▶ {actions_str}")
            self.idle_count = 0
            # Append to rolling history
            self._history.append({
                "step":    self.step_count,
                "summary": log_line or "(action)",
                "actions": action_log,
            })
            if len(self._history) > self._history_max:
                self._history.pop(0)
            # Record this step in the fine-tuning dataset
            if self.collector:
                self.collector.record(img, prompt, response, action_log)
            # Use fast delay for simple single-button presses (dialogue)
            if len(action_log) == 1 and action_log[0].startswith("PRESS"):
                return FAST_DELAY
            return LOOP_DELAY
        else:
            # No actions — bot gave a text response
            self.idle_count += 1
            snippet = response[:100].replace("\n", " ")
            self.log(f"[{self.step_count}] (no action) {snippet}")
            # Still record in history so agent knows it stalled here
            self._history.append({
                "step":    self.step_count,
                "summary": snippet,
                "actions": [],
            })
            if len(self._history) > self._history_max:
                self._history.pop(0)
            if self.collector:
                self.collector.record(img, prompt, response, [])
            return LOOP_DELAY

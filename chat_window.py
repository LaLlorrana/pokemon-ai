# ============================================================
#  chat_window.py — PokeBot UI (dark & sleek redesign)
# ============================================================

import tkinter as tk
from tkinter import scrolledtext, simpledialog
import threading
from vision import capture_screen, ask_llava
from config import AUTO_WATCH_INTERVAL
from game_state import load_state, save_state, update_state_from_message, refresh_from_ram
from executor import parse_and_execute, has_actions
from counters import load_counters, save_counters, get_shiny_odds
from agent import PokeAgent

# ── Palette ────────────────────────────────────────────────
BG          = "#0e0e0f"
BG_PANEL    = "#141416"
BG_INPUT    = "#1c1c1f"
BG_CARD     = "#1a1a1d"
BORDER      = "#2a2a2e"
ACCENT      = "#e94560"
ACCENT_DIM  = "#7c1f30"
CYAN        = "#4fc3f7"
GREEN       = "#4caf50"
YELLOW      = "#ffc107"
RED         = "#f44336"
TEXT        = "#e8e8ea"
TEXT_DIM    = "#606068"
TEXT_MID    = "#9999a8"

FONT_MONO   = ("Consolas",   11)
FONT_MONO_S = ("Consolas",   10)
FONT_UI     = ("Segoe UI",   10)
FONT_UI_S   = ("Segoe UI",    9)
FONT_UI_B   = ("Segoe UI",   10, "bold")
FONT_TITLE  = ("Segoe UI",   13, "bold")
FONT_TINY   = ("Segoe UI",    8)

MAX_HISTORY = 20
RAM_POLL_MS = 3000   # how often to poll RAM (ms)


def hp_color(hp: int, max_hp: int) -> str:
    if max_hp == 0:
        return RED
    pct = hp / max_hp
    if pct > 0.5:  return GREEN
    if pct > 0.25: return YELLOW
    return RED


class ChatWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PokeBot — Pokémon Unbound")
        self.root.configure(bg=BG)
        self.root.geometry("1050x700")
        self.root.minsize(800, 550)

        self.history:     list[dict] = []
        self.game_state:  dict       = load_state()
        self.counters:    dict       = load_counters()
        self.auto_watch_active       = False
        self.auto_watch_job          = None
        self._ram_poll_job           = None
        self._last_map_key           = None
        self._custom_counter_widgets = []
        self.agent                   = PokeAgent(
            self.game_state,
            log_fn=lambda msg: self.root.after(0, self._append_agent_log, msg),
            state_update_fn=lambda: self.root.after(0, self._refresh_sidebar),
        )

        self._build_ui()
        self._start_ram_polling()

    # ═══════════════════════════════════════════════════════
    # UI BUILD
    # ═══════════════════════════════════════════════════════

    def _build_ui(self):
        # ── Top bar ────────────────────────────────────────
        top = tk.Frame(self.root, bg=BG, pady=6)
        top.pack(fill="x", padx=14)

        tk.Label(top, text="◉ PokeBot", font=FONT_TITLE,
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(top, text="Pokémon Unbound AI",
                 font=FONT_UI, fg=TEXT_DIM, bg=BG).pack(side="left", padx=10)

        # Quick buttons (top right)
        for txt, cmd in [("👁 See", self._quick_see),
                         ("⚔ Battle", self._quick_battle),
                         ("📍 Where", self._quick_location)]:
            tk.Button(top, text=txt, command=cmd,
                      bg=BG_INPUT, fg=TEXT, font=FONT_UI_S,
                      relief="flat", padx=8, pady=3,
                      activebackground=ACCENT_DIM,
                      cursor="hand2").pack(side="right", padx=3)

        # Thin separator
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # ── Main layout: chat | sidebar ────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # Chat column
        chat_frame = tk.Frame(body, bg=BG)
        chat_frame.pack(side="left", fill="both", expand=True)

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, state="disabled",
            bg=BG, fg=TEXT, font=FONT_MONO,
            insertbackground=ACCENT, relief="flat",
            padx=14, pady=12, bd=0,
            selectbackground=ACCENT_DIM,
        )
        self.chat_display.pack(fill="both", expand=True)
        self._configure_chat_tags()

        # Thin vertical divider
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y")

        # Sidebar
        self.sidebar = tk.Frame(body, bg=BG_PANEL, width=240)
        self.sidebar.pack(side="right", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # ── Bottom bar ─────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        bottom = tk.Frame(self.root, bg=BG_PANEL, pady=8)
        bottom.pack(fill="x", padx=0)

        # Toggles
        toggle_frame = tk.Frame(bottom, bg=BG_PANEL)
        toggle_frame.pack(side="left", padx=10)

        self.execute_var = tk.BooleanVar(value=True)
        self._toggle_btn(toggle_frame, "Execute", self.execute_var).pack(side="left", padx=2)

        self.auto_watch_var = tk.BooleanVar(value=False)
        self._toggle_btn(toggle_frame, "Auto-watch", self.auto_watch_var,
                         cmd=self._toggle_auto_watch).pack(side="left", padx=2)

        self._hist_btn = tk.Button(toggle_frame, text="Clear history",
                                   command=self._clear_history,
                                   bg=BG_INPUT, fg=TEXT_DIM, font=FONT_UI_S,
                                   relief="flat", padx=6, pady=2,
                                   activebackground=BORDER, cursor="hand2")
        self._hist_btn.pack(side="left", padx=6)

        # Input
        self.input_field = tk.Entry(bottom, bg=BG_INPUT, fg=TEXT,
                                    font=FONT_UI, relief="flat",
                                    insertbackground=TEXT,
                                    highlightthickness=1,
                                    highlightcolor=ACCENT,
                                    highlightbackground=BORDER)
        self.input_field.pack(side="left", fill="x", expand=True, padx=(4, 6), ipady=7)
        self.input_field.bind("<Return>", lambda e: self._send_message())

        self.send_btn = tk.Button(bottom, text="Send", command=self._send_message,
                                  bg=ACCENT, fg="white", font=FONT_UI_B,
                                  relief="flat", padx=16, pady=7,
                                  activebackground=ACCENT_DIM, cursor="hand2")
        self.send_btn.pack(side="right", padx=10)

        # Status
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var,
                 font=FONT_TINY, fg=TEXT_DIM, bg=BG).pack(side="bottom", pady=2)

        self._append_bot("PokeBot online. Wiki loaded. RAM connected. What do you need?")

    def _toggle_btn(self, parent, label, var, cmd=None):
        def toggle():
            var.set(not var.get())
            btn.config(bg=ACCENT if var.get() else BG_INPUT,
                       fg="white" if var.get() else TEXT_DIM)
            if cmd:
                cmd()
        btn = tk.Button(parent, text=label, command=toggle,
                        bg=ACCENT if var.get() else BG_INPUT,
                        fg="white" if var.get() else TEXT_DIM,
                        font=FONT_UI_S, relief="flat", padx=8, pady=2,
                        cursor="hand2")
        return btn

    # ═══════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════

    def _build_sidebar(self):
        sb = self.sidebar

        # ── Location card ──────────────────────────────────
        self._section_label(sb, "📍  LOCATION")
        loc_card = tk.Frame(sb, bg=BG_CARD, padx=10, pady=8)
        loc_card.pack(fill="x", padx=8, pady=(0, 8))
        self.loc_name_var = tk.StringVar(value="Unknown")
        self.loc_coord_var = tk.StringVar(value="")
        tk.Label(loc_card, textvariable=self.loc_name_var,
                 font=FONT_UI_B, fg=CYAN, bg=BG_CARD,
                 wraplength=200, justify="left").pack(anchor="w")
        tk.Label(loc_card, textvariable=self.loc_coord_var,
                 font=FONT_UI_S, fg=TEXT_DIM, bg=BG_CARD).pack(anchor="w")

        # ── Team card ──────────────────────────────────────
        self._section_label(sb, "🐾  TEAM")
        self.team_card = tk.Frame(sb, bg=BG_CARD, padx=10, pady=8)
        self.team_card.pack(fill="x", padx=8, pady=(0, 8))
        self.team_slot_frames = []
        for _ in range(6):
            slot = self._build_team_slot(self.team_card)
            self.team_slot_frames.append(slot)

        # ── Counters ───────────────────────────────────────
        self._section_label(sb, "📊  COUNTERS")
        counters_card = tk.Frame(sb, bg=BG_CARD, padx=10, pady=8)
        counters_card.pack(fill="x", padx=8, pady=(0, 8))

        # Steps
        step_row = tk.Frame(counters_card, bg=BG_CARD)
        step_row.pack(fill="x", pady=2)
        tk.Label(step_row, text="Steps", font=FONT_UI_S, fg=TEXT_MID, bg=BG_CARD).pack(side="left")
        self.step_var = tk.StringVar(value=str(self.counters.get("steps", 0)))
        tk.Label(step_row, textvariable=self.step_var,
                 font=FONT_UI_B, fg=TEXT, bg=BG_CARD).pack(side="left", padx=6)
        tk.Button(step_row, text="+", command=self._inc_steps,
                  bg=BG_INPUT, fg=TEXT, font=FONT_UI_S,
                  relief="flat", padx=5, pady=0, cursor="hand2").pack(side="right")
        tk.Button(step_row, text="↺", command=self._reset_steps,
                  bg=BG_INPUT, fg=TEXT_DIM, font=FONT_UI_S,
                  relief="flat", padx=5, pady=0, cursor="hand2").pack(side="right", padx=2)

        # Encounters + shiny odds
        enc_row = tk.Frame(counters_card, bg=BG_CARD)
        enc_row.pack(fill="x", pady=2)
        tk.Label(enc_row, text="Encounters", font=FONT_UI_S, fg=TEXT_MID, bg=BG_CARD).pack(side="left")
        self.enc_var = tk.StringVar(value=str(self.counters.get("encounters", 0)))
        tk.Label(enc_row, textvariable=self.enc_var,
                 font=FONT_UI_B, fg=TEXT, bg=BG_CARD).pack(side="left", padx=6)
        tk.Button(enc_row, text="+", command=self._inc_encounters,
                  bg=BG_INPUT, fg=TEXT, font=FONT_UI_S,
                  relief="flat", padx=5, pady=0, cursor="hand2").pack(side="right")
        tk.Button(enc_row, text="↺", command=self._reset_encounters,
                  bg=BG_INPUT, fg=TEXT_DIM, font=FONT_UI_S,
                  relief="flat", padx=5, pady=0, cursor="hand2").pack(side="right", padx=2)

        shiny_row = tk.Frame(counters_card, bg=BG_CARD)
        shiny_row.pack(fill="x", pady=(0, 6))
        tk.Label(shiny_row, text="✨ Shiny chance",
                 font=FONT_UI_S, fg=TEXT_DIM, bg=BG_CARD).pack(side="left")
        self.shiny_var = tk.StringVar(value=get_shiny_odds(self.counters.get("encounters", 0)))
        tk.Label(shiny_row, textvariable=self.shiny_var,
                 font=FONT_UI_S, fg=YELLOW, bg=BG_CARD).pack(side="right")

        tk.Frame(counters_card, bg=BORDER, height=1).pack(fill="x", pady=4)

        # Custom counters
        self.custom_frame = tk.Frame(counters_card, bg=BG_CARD)
        self.custom_frame.pack(fill="x")
        self._rebuild_custom_counters()

        tk.Button(counters_card, text="+ Add counter",
                  command=self._add_custom_counter,
                  bg=BG_INPUT, fg=TEXT_DIM, font=FONT_UI_S,
                  relief="flat", pady=4, cursor="hand2").pack(fill="x", pady=(6, 0))

        # ── Goal ───────────────────────────────────────────
        self._section_label(sb, "🎯  GOAL")
        goal_card = tk.Frame(sb, bg=BG_CARD, padx=10, pady=8)
        goal_card.pack(fill="x", padx=8, pady=(0, 8))
        self.goal_var = tk.StringVar(value="None")
        tk.Label(goal_card, textvariable=self.goal_var,
                 font=FONT_UI_S, fg=TEXT_MID, bg=BG_CARD,
                 wraplength=200, justify="left").pack(anchor="w")

        # ── Auto Play ──────────────────────────────────────
        self._section_label(sb, "🤖  AUTO PLAY")
        ap_card = tk.Frame(sb, bg=BG_CARD, padx=10, pady=8)
        ap_card.pack(fill="x", padx=8, pady=(0, 8))

        self.agent_goal_entry = tk.Entry(ap_card, bg=BG_INPUT, fg=TEXT,
                                          font=FONT_UI_S, relief="flat",
                                          insertbackground=TEXT)
        self.agent_goal_entry.insert(0, "e.g. grind to level 35")
        self.agent_goal_entry.config(fg=TEXT_DIM)
        self.agent_goal_entry.bind("<FocusIn>",  self._ap_entry_focus_in)
        self.agent_goal_entry.bind("<FocusOut>", self._ap_entry_focus_out)
        self.agent_goal_entry.bind("<Return>",   lambda e: self._toggle_agent())
        self.agent_goal_entry.pack(fill="x", pady=(0, 6), ipady=4)

        self.ap_btn = tk.Button(ap_card, text="▶  Start Auto Play",
                                command=self._toggle_agent,
                                bg=GREEN, fg="white", font=FONT_UI_B,
                                relief="flat", pady=6, cursor="hand2")
        self.ap_btn.pack(fill="x")

        # Agent log (scrollable, compact)
        tk.Frame(ap_card, bg=BORDER, height=1).pack(fill="x", pady=(8, 4))
        self.agent_log = tk.Text(ap_card, height=6, wrap=tk.WORD,
                                  bg=BG, fg=TEXT_DIM, font=FONT_TINY,
                                  relief="flat", state="disabled",
                                  padx=4, pady=4)
        self.agent_log.pack(fill="x")

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI", 8, "bold"),
                 fg=TEXT_DIM, bg=BG_PANEL, padx=10, pady=4).pack(anchor="w")

    def _build_team_slot(self, parent) -> dict:
        frame = tk.Frame(parent, bg=BG_CARD)
        frame.pack(fill="x", pady=2)
        frame.pack_forget()  # hidden by default

        name_var   = tk.StringVar()
        hp_var     = tk.StringVar()
        status_var = tk.StringVar()

        top_row = tk.Frame(frame, bg=BG_CARD)
        top_row.pack(fill="x")
        name_lbl = tk.Label(top_row, textvariable=name_var,
                             font=FONT_UI_B, fg=TEXT, bg=BG_CARD)
        name_lbl.pack(side="left")
        hp_lbl = tk.Label(top_row, textvariable=hp_var,
                           font=FONT_UI_S, fg=TEXT_DIM, bg=BG_CARD)
        hp_lbl.pack(side="right")

        # HP bar
        bar_bg = tk.Frame(frame, bg=BORDER, height=4)
        bar_bg.pack(fill="x", pady=(1, 0))
        bar_fg = tk.Frame(bar_bg, bg=GREEN, height=4)
        bar_fg.place(x=0, y=0, relheight=1.0, relwidth=1.0)

        status_lbl = tk.Label(frame, textvariable=status_var,
                               font=FONT_TINY, fg=RED, bg=BG_CARD)

        return {
            "frame":      frame,
            "name_var":   name_var,
            "hp_var":     hp_var,
            "status_var": status_var,
            "bar_fg":     bar_fg,
            "status_lbl": status_lbl,
            "name_lbl":   name_lbl,
        }

    # ═══════════════════════════════════════════════════════
    # SIDEBAR REFRESH
    # ═══════════════════════════════════════════════════════

    def _refresh_sidebar(self):
        gs = self.game_state

        # Location
        self.loc_name_var.set(gs.get("location", "Unknown"))
        x, y = gs.get("player_x", 0), gs.get("player_y", 0)
        self.loc_coord_var.set(f"x:{x}  y:{y}" if (x or y) else "")

        # Team
        team = gs.get("team", [])
        for i, slot in enumerate(self.team_slot_frames):
            if i < len(team):
                p      = team[i]
                hp     = p.get("hp", 0)
                max_hp = p.get("max_hp", 1) or 1
                status = p.get("status", "Healthy")
                pct    = max(0, min(1, hp / max_hp))
                color  = hp_color(hp, max_hp)

                slot["name_var"].set(f"{p['name']}  Lv.{p.get('level','?')}")
                slot["hp_var"].set(f"{hp}/{max_hp}")
                slot["bar_fg"].config(bg=color)
                slot["bar_fg"].place(relwidth=pct)
                if status != "Healthy":
                    slot["status_var"].set(status)
                    slot["status_lbl"].pack(anchor="w")
                else:
                    slot["status_lbl"].pack_forget()
                slot["frame"].pack(fill="x", pady=2)
            else:
                slot["frame"].pack_forget()

        # Goal
        self.goal_var.set(gs.get("active_goal") or "None")

        # Shiny odds
        self.shiny_var.set(get_shiny_odds(self.counters.get("encounters", 0)))

    def _rebuild_custom_counters(self):
        for w in self.custom_frame.winfo_children():
            w.destroy()
        self._custom_counter_widgets = []
        for i, c in enumerate(self.counters.get("custom", [])):
            self._build_custom_counter_row(i, c)

    def _build_custom_counter_row(self, idx: int, counter: dict):
        row = tk.Frame(self.custom_frame, bg=BG_CARD)
        row.pack(fill="x", pady=1)

        name_lbl = tk.Label(row, text=counter["name"],
                             font=FONT_UI_S, fg=TEXT_MID, bg=BG_CARD)
        name_lbl.pack(side="left")

        val_var = tk.StringVar(value=str(counter["value"]))
        tk.Label(row, textvariable=val_var,
                 font=FONT_UI_B, fg=TEXT, bg=BG_CARD).pack(side="left", padx=4)

        def inc(i=idx, v=val_var):
            self.counters["custom"][i]["value"] += 1
            v.set(str(self.counters["custom"][i]["value"]))
            save_counters(self.counters)

        def reset(i=idx, v=val_var):
            self.counters["custom"][i]["value"] = 0
            v.set("0")
            save_counters(self.counters)

        def remove(i=idx):
            self.counters["custom"].pop(i)
            save_counters(self.counters)
            self._rebuild_custom_counters()

        tk.Button(row, text="+", command=inc,
                  bg=BG_INPUT, fg=TEXT, font=FONT_UI_S,
                  relief="flat", padx=5, cursor="hand2").pack(side="right")
        tk.Button(row, text="↺", command=reset,
                  bg=BG_INPUT, fg=TEXT_DIM, font=FONT_UI_S,
                  relief="flat", padx=4, cursor="hand2").pack(side="right", padx=1)
        tk.Button(row, text="✕", command=remove,
                  bg=BG_CARD, fg=TEXT_DIM, font=FONT_TINY,
                  relief="flat", padx=2, cursor="hand2").pack(side="right")

    # ═══════════════════════════════════════════════════════
    # COUNTERS
    # ═══════════════════════════════════════════════════════

    def _inc_steps(self):
        self.counters["steps"] = self.counters.get("steps", 0) + 1
        self.step_var.set(str(self.counters["steps"]))
        save_counters(self.counters)

    def _reset_steps(self):
        self.counters["steps"] = 0
        self.step_var.set("0")
        save_counters(self.counters)

    def _inc_encounters(self):
        self.counters["encounters"] = self.counters.get("encounters", 0) + 1
        self.enc_var.set(str(self.counters["encounters"]))
        self.shiny_var.set(get_shiny_odds(self.counters["encounters"]))
        save_counters(self.counters)

    def _reset_encounters(self):
        self.counters["encounters"] = 0
        self.enc_var.set("0")
        self.shiny_var.set(get_shiny_odds(0))
        save_counters(self.counters)

    def _add_custom_counter(self):
        name = simpledialog.askstring("New Counter", "Counter name:",
                                      parent=self.root)
        if name and name.strip():
            self.counters.setdefault("custom", []).append({"name": name.strip(), "value": 0})
            save_counters(self.counters)
            self._rebuild_custom_counters()

    # ═══════════════════════════════════════════════════════
    # CHAT HELPERS
    # ═══════════════════════════════════════════════════════

    def _configure_chat_tags(self):
        self.chat_display.tag_config("you",      foreground=ACCENT,  font=("Consolas", 11, "bold"))
        self.chat_display.tag_config("bot",      foreground=CYAN,    font=("Consolas", 11, "bold"))
        self.chat_display.tag_config("system",   foreground=TEXT_DIM,font=("Consolas", 10, "italic"))
        self.chat_display.tag_config("actions",  foreground=YELLOW,  font=("Consolas", 10, "italic"))
        self.chat_display.tag_config("body",     foreground=TEXT)

    def _append_bot(self, text: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", "\nPokeBot: ", "bot")
        self.chat_display.insert("end", text + "\n", "body")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _append_you(self, text: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", f"\nYou: ", "you")
        self.chat_display.insert("end", text + "\n", "body")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _append_system(self, text: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", f"\n{text}\n", "system")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _append_actions(self, text: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", f"{text}\n", "actions")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _start_bot_label(self):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", "\nPokeBot: ", "bot")
        self.chat_display.config(state="disabled")

    def _append_chunk(self, chunk: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", chunk, "body")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _end_bot_turn(self):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", "\n", "body")
        self.chat_display.config(state="disabled")

    def _set_busy(self, busy: bool):
        state = "disabled" if busy else "normal"
        self.send_btn.config(state=state)
        self.input_field.config(state=state)
        self.status_var.set("Thinking…" if busy else "Ready")

    def _add_to_history(self, role: str, content: str, img_b64: str = None):
        msg = {"role": role, "content": content}
        if img_b64 and role == "user":
            msg["images"] = [img_b64]
        self.history.append(msg)
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    def _clear_history(self):
        self.history = []
        self._append_system("— history cleared —")

    # ═══════════════════════════════════════════════════════
    # MESSAGE HANDLING
    # ═══════════════════════════════════════════════════════

    def _send_message(self):
        text = self.input_field.get().strip()
        if not text:
            return
        self.input_field.delete(0, "end")

        updated = update_state_from_message(self.game_state, text)
        self.game_state = updated
        save_state(self.game_state)
        self.root.after(0, self._refresh_sidebar)

        self._append_you(text)
        threading.Thread(target=self._process_message, args=(text,), daemon=True).start()

    def _process_message(self, text: str):
        self.root.after(0, self._set_busy, True)

        from vision import image_to_base64
        img    = capture_screen()
        img_b64 = image_to_base64(img)
        self._add_to_history("user", text, img_b64)

        self.root.after(0, self._start_bot_label)

        response = ask_llava(
            user_message=text,
            img=img,
            history=self.history[:-1],
            game_state=self.game_state,
            stream_callback=lambda c: self.root.after(0, self._append_chunk, c),
        )

        self.root.after(0, self._end_bot_turn)

        # Execute any action tags
        should_execute = self.execute_var.get()
        if has_actions(response):
            clean, action_log = parse_and_execute(response, execute=should_execute)
            if action_log:
                status = "Executing" if should_execute else "Dry run"
                self.root.after(0, self._append_actions,
                                f"  ▶ [{status}] {' → '.join(action_log)}")
            self._add_to_history("assistant", clean)
        else:
            self._add_to_history("assistant", response)

        self.root.after(0, self._set_busy, False)

    # ═══════════════════════════════════════════════════════
    # QUICK ACTIONS
    # ═══════════════════════════════════════════════════════

    def _quick_see(self):
        self._append_you("What do I see?")
        threading.Thread(target=self._process_message,
                         args=("What do I see? Describe the screen accurately using Pokémon Unbound / Borrius region context.",),
                         daemon=True).start()

    def _quick_battle(self):
        self._append_you("Battle advice")
        threading.Thread(target=self._process_message,
                         args=("We're in a battle. Analyse the situation and give me the best move and why.",),
                         daemon=True).start()

    def _quick_location(self):
        self._append_you("Where am I?")
        threading.Thread(target=self._process_message,
                         args=("Where am I in Pokémon Unbound? What area is this in the Borrius region?",),
                         daemon=True).start()

    # ═══════════════════════════════════════════════════════
    # RAM POLLING + MAP AUTO-NAMING
    # ═══════════════════════════════════════════════════════

    def _start_ram_polling(self):
        self._poll_ram()

    def _poll_ram(self):
        threading.Thread(target=self._do_ram_poll, daemon=True).start()

    def _do_ram_poll(self):
        updated = refresh_from_ram(self.game_state)
        self.game_state = updated
        save_state(self.game_state)

        # Check for unknown map
        bank   = updated.get("map_bank", 0)
        number = updated.get("map_number", 0)
        key    = f"{bank}:{number}"

        if (key != self._last_map_key and
                "unknown" in updated.get("location", "").lower()):
            self._last_map_key = key
            self.root.after(0, self._prompt_map_name, bank, number)
        else:
            self._last_map_key = key

        self.root.after(0, self._refresh_sidebar)
        self._ram_poll_job = self.root.after(RAM_POLL_MS, self._poll_ram)

    def _prompt_map_name(self, bank: int, number: int):
        """
        Ask the user to name an unknown map.
        First takes a screenshot and asks gemma to guess the location name,
        then pre-fills the dialog so the user just confirms or corrects it.
        Leave blank to skip (unnamed buildings etc).
        """
        # Try to get a guess from gemma first
        guess = ""
        try:
            img = capture_screen()
            guess = ask_llava(
                "Look at this screenshot from Pokémon Unbound. "
                "What specific location or building is this? "
                "Reply with ONLY the location name (e.g. 'Dehara City Pokémon Center', "
                "'Dehara City Gym', 'Route 4'). "
                "If you genuinely cannot tell, reply with exactly: UNKNOWN",
                img,
                game_state=self.game_state,
            ).strip()
            if guess.upper() == "UNKNOWN" or len(guess) > 60:
                guess = ""
        except Exception:
            guess = ""

        prompt_text = (
            f"New area detected (map {bank}-{number}).\n"
            f"What's this location called?\n"
            f"(Leave blank to skip unnamed areas)"
        )
        name = simpledialog.askstring(
            "New Location",
            prompt_text,
            initialvalue=guess,
            parent=self.root
        )
        if name and name.strip():
            from ram_reader import register_map_name
            register_map_name(bank, number, name.strip())
            self.game_state["location"] = name.strip()
            save_state(self.game_state)
            self.root.after(0, self._refresh_sidebar)
            self._append_system(f"✓ Saved: map {bank}-{number} = {name.strip()}")

    # ═══════════════════════════════════════════════════════
    # AUTO PLAY
    # ═══════════════════════════════════════════════════════

    def _ap_entry_focus_in(self, _):
        if self.agent_goal_entry.get() == "e.g. grind to level 35":
            self.agent_goal_entry.delete(0, "end")
            self.agent_goal_entry.config(fg=TEXT)

    def _ap_entry_focus_out(self, _):
        if not self.agent_goal_entry.get().strip():
            self.agent_goal_entry.insert(0, "e.g. grind to level 35")
            self.agent_goal_entry.config(fg=TEXT_DIM)

    def _toggle_agent(self):
        if self.agent.running:
            self.agent.stop()
            self.ap_btn.config(text="▶  Start Auto Play", bg=GREEN)
        else:
            goal = self.agent_goal_entry.get().strip()
            if not goal or goal == "e.g. grind to level 35":
                self._append_agent_log("⚠ Enter a goal first.")
                return
            # Update shared game state goal
            self.game_state["active_goal"] = goal
            save_state(self.game_state)
            self._refresh_sidebar()
            self.agent.game_state = self.game_state
            self.agent.start(goal)
            self.ap_btn.config(text="■  Stop Auto Play", bg=RED)

    def _append_agent_log(self, msg: str):
        self.agent_log.config(state="normal")
        self.agent_log.insert("end", msg + "\n")
        self.agent_log.see("end")
        self.agent_log.config(state="disabled")
        # Also echo to main chat so nothing is hidden
        self._append_system(f"[Agent] {msg}")

    # ═══════════════════════════════════════════════════════
    # AUTO-WATCH
    # ═══════════════════════════════════════════════════════

    def _toggle_auto_watch(self):
        self.auto_watch_active = self.auto_watch_var.get()
        if self.auto_watch_active:
            self._append_system("Auto-watch enabled.")
            self._schedule_auto_watch()
        else:
            self._append_system("Auto-watch disabled.")
            if self.auto_watch_job:
                self.root.after_cancel(self.auto_watch_job)

    def _schedule_auto_watch(self):
        if not self.auto_watch_active:
            return
        self.auto_watch_job = self.root.after(
            AUTO_WATCH_INTERVAL * 1000, self._run_auto_watch)

    def _run_auto_watch(self):
        if not self.auto_watch_active:
            return
        threading.Thread(target=self._auto_watch_check, daemon=True).start()

    def _auto_watch_check(self):
        img = capture_screen()
        response = ask_llava(
            "Silently observe. Only respond if something important is happening "
            "(battle started, level up, story event, low HP, boss). "
            "If nothing noteworthy: reply exactly NOTHING_TO_REPORT",
            img, game_state=self.game_state
        )
        if response.strip() != "NOTHING_TO_REPORT":
            self.root.after(0, self._append_bot, f"[Auto] {response}")
        self._schedule_auto_watch()

# ============================================================
#  experience.py — strategy memory & experience log
#
#  Saves successful strategies, battle outcomes, and key
#  decisions so the bot can reference past experiences.
#  Grows automatically as you play.
# ============================================================

import json
import os
import time
from datetime import datetime

EXPERIENCE_FILE = os.path.join(os.path.dirname(__file__), "experience.json")
MAX_EXPERIENCES = 500   # cap to avoid bloating the prompt
MAX_INJECT_CHARS = 2000  # max chars to inject per prompt

CATEGORIES = ["battle", "navigation", "item", "strategy", "general"]


def _load() -> list:
    if os.path.isfile(EXPERIENCE_FILE):
        try:
            with open(EXPERIENCE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save(experiences: list):
    with open(EXPERIENCE_FILE, "w") as f:
        json.dump(experiences[-MAX_EXPERIENCES:], f, indent=2)


def log_experience(category: str, situation: str, outcome: str,
                   location: str = "", tags: list = None):
    """
    Save a notable experience for future reference.

    category:  one of CATEGORIES
    situation: what was happening (e.g. "Fighting gym leader Big Mo's Lucario")
    outcome:   what worked / what happened (e.g. "Used Psychic, swept easily")
    location:  where this happened
    tags:      searchable keywords (e.g. ["gym", "fighting", "Big Mo"])
    """
    experiences = _load()
    entry = {
        "ts":        time.time(),
        "date":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "category":  category,
        "location":  location,
        "situation": situation,
        "outcome":   outcome,
        "tags":      tags or [],
    }
    experiences.append(entry)
    _save(experiences)
    return entry


def search_experiences(query: str, category: str = None, max_results: int = 5) -> list:
    """
    Find past experiences relevant to the current situation.
    Matches against situation, outcome, location, and tags.
    """
    experiences = _load()
    if not experiences:
        return []

    keywords = set(query.lower().split())
    keywords -= {"the", "a", "an", "in", "of", "and", "or", "i", "my"}

    scored = []
    for exp in experiences:
        if category and exp.get("category") != category:
            continue
        text = " ".join([
            exp.get("situation", ""),
            exp.get("outcome", ""),
            exp.get("location", ""),
            " ".join(exp.get("tags", [])),
        ]).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, exp))

    scored.sort(reverse=True)
    return [exp for _, exp in scored[:max_results]]


def get_relevant_experiences(situation: str, location: str = "") -> str:
    """
    Return formatted past experiences relevant to the current situation.
    Returns empty string if nothing relevant found.
    """
    query = f"{situation} {location}"
    results = search_experiences(query)
    if not results:
        return ""

    lines = ["=== PAST EXPERIENCES (what worked before) ==="]
    total = 0
    for exp in results:
        entry = (
            f"[{exp['date']} | {exp['category']} | {exp.get('location','')}]\n"
            f"  Situation: {exp['situation']}\n"
            f"  Outcome:   {exp['outcome']}\n"
        )
        if total + len(entry) > MAX_INJECT_CHARS:
            break
        lines.append(entry)
        total += len(entry)

    return "\n".join(lines) if len(lines) > 1 else ""


def log_battle_win(enemy: str, location: str, strategy: str):
    log_experience("battle", f"Fighting {enemy}", f"Won — {strategy}",
                   location=location, tags=["battle", "win", enemy.lower()])


def log_battle_loss(enemy: str, location: str, notes: str):
    log_experience("battle", f"Fighting {enemy}", f"Lost — {notes}",
                   location=location, tags=["battle", "loss", enemy.lower()])


def log_navigation(from_loc: str, to_loc: str, method: str):
    log_experience("navigation", f"Getting from {from_loc} to {to_loc}",
                   method, location=from_loc,
                   tags=["navigation", from_loc.lower(), to_loc.lower()])


def get_experience_summary() -> str:
    """Quick stats about the experience log."""
    exps = _load()
    if not exps:
        return "No experiences logged yet."
    cats = {}
    for e in exps:
        cats[e.get("category", "general")] = cats.get(e.get("category", "general"), 0) + 1
    parts = [f"{v} {k}" for k, v in cats.items()]
    return f"{len(exps)} total experiences: {', '.join(parts)}"

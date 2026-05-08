# ============================================================
#  wiki_search.py — searches downloaded wiki files
#  Called automatically by vision.py before each prompt.
# ============================================================

import os
import re
import json

WIKI_DIR   = os.path.join(os.path.dirname(__file__), "wiki_data")
INDEX_FILE = os.path.join(WIKI_DIR, "_index.json")

MAX_INJECT_CHARS = 4000
MAX_PAGES = 3

BASE_PAGES = [
    "walkthrough",
    "locations",
    "gyms",
]


def wiki_available() -> bool:
    return os.path.isdir(WIKI_DIR) and os.path.isfile(INDEX_FILE)


def _load_index() -> dict:
    if not os.path.isfile(INDEX_FILE):
        return {}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_page(filename: str) -> str:
    path = os.path.join(WIKI_DIR, filename)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def search(query: str, max_pages: int = MAX_PAGES) -> str:
    if not wiki_available():
        return ""
    index    = _load_index()
    keywords = set(re.findall(r'\w+', query.lower()))
    keywords -= {"the", "a", "an", "is", "in", "of", "and", "or", "to", "for", "my", "i"}
    scores = []
    for filename, title in index.items():
        title_lower = title.lower()
        score = sum(1 for kw in keywords if kw in title_lower)
        if score > 0:
            scores.append((score, filename, title))
    scores.sort(reverse=True)
    top = scores[:max_pages]
    if not top:
        return ""
    parts = []
    total_chars = 0
    for _, filename, title in top:
        content = _read_page(filename)
        if not content:
            continue
        available = MAX_INJECT_CHARS - total_chars
        if available <= 0:
            break
        snippet = content[:available]
        parts.append(f"=== Wiki: {title} ===\n{snippet}")
        total_chars += len(snippet)
    return "\n\n".join(parts)


def extract_facts(content: str, title: str) -> str:
    """Parse Location, Type, Evolution out of a wiki page into a short factual summary."""
    facts = [f"Pokémon Unbound wiki — {title}:"]
    lines = content.splitlines()
    i = 0
    found = set()
    while i < len(lines):
        line  = lines[i].strip()
        label = line.lower()
        if label == "location" and "location" not in found:
            val_lines = []
            j = i + 1
            while j < len(lines) and j < i + 4:
                v = lines[j].strip()
                if v and v.lower() not in ("type", "abilities", "evolution", "egg groups"):
                    val_lines.append(v)
                    j += 1
                else:
                    break
            if val_lines:
                facts.append(f"  Location in Pokémon Unbound: {' '.join(val_lines)}")
                found.add("location")
        elif label == "type" and "type" not in found:
            j = i + 1
            if j < len(lines):
                val = lines[j].strip()
                if val:
                    facts.append(f"  Type: {val}")
                    found.add("type")
        elif label in ("evolution line", "evolution") and "evolution" not in found:
            j = i + 1
            if j < len(lines):
                val = lines[j].strip()
                if val:
                    facts.append(f"  Evolution: {val}")
                    found.add("evolution")
        i += 1
    return "\n".join(facts) if len(facts) > 1 else ""


def search_with_facts(query: str) -> tuple:
    """Search wiki and return (raw_content, extracted_facts) for the top hit."""
    if not wiki_available():
        return "", ""
    index    = _load_index()
    keywords = set(re.findall(r'\w+', query.lower()))
    keywords -= {"the", "a", "an", "is", "in", "of", "and", "or", "to", "for", "my", "i",
                 "where", "what", "who", "how", "find", "get", "catch", "located"}
    scores = []
    for filename, title in index.items():
        title_lower = title.lower()
        score = sum(1 for kw in keywords if kw in title_lower)
        if score > 0:
            scores.append((score, filename, title))
    scores.sort(reverse=True)
    if not scores:
        return "", ""
    _, top_file, top_title = scores[0]
    content = _read_page(top_file)
    facts   = extract_facts(content, top_title) if content else ""
    raw     = search(query)
    return raw, facts


def get_base_content() -> str:
    if not wiki_available():
        return ""
    index = _load_index()
    parts = []
    total_chars = 0
    budget = 2000
    for filename, title in index.items():
        title_lower = title.lower()
        if any(kw in title_lower for kw in BASE_PAGES):
            content = _read_page(filename)
            if not content:
                continue
            available = budget - total_chars
            if available <= 0:
                break
            snippet = content[:available]
            parts.append(f"=== Wiki: {title} ===\n{snippet}")
            total_chars += len(snippet)
    return "\n\n".join(parts)


def search_for_state(game_state: dict) -> str:
    base = get_base_content()
    query_parts = []
    if game_state.get("location") and game_state["location"] != "Unknown":
        query_parts.append(game_state["location"])
    if game_state.get("active_goal"):
        query_parts.append(game_state["active_goal"])
    specific = search(" ".join(query_parts)) if query_parts else ""
    combined = "\n\n".join(filter(None, [base, specific]))
    return combined[:MAX_INJECT_CHARS]

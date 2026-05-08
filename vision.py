# ============================================================
#  vision.py — screen capture + Ollama chat API integration
# ============================================================

import base64
import io
import json
import time
import ctypes
import ctypes.wintypes
import requests
import mss
from PIL import Image

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False

from config import OLLAMA_URL, MODEL_NAME, SYSTEM_PROMPT_BASE, SCREENSHOT_FORMAT, RETROARCH_WINDOW_TITLE
from knowledge_base import get_knowledge
from game_state import format_state_for_prompt
from wiki_search import search, search_for_state, get_base_content, wiki_available, search_with_facts

try:
    from experience import get_relevant_experiences
    EXPERIENCE_AVAILABLE = True
except ImportError:
    EXPERIENCE_AVAILABLE = False

try:
    from nav_memory import format_routes_for_prompt
    NAV_MEMORY_AVAILABLE = True
except ImportError:
    NAV_MEMORY_AVAILABLE = False

# Title bar height to crop from the top of the RetroArch window (pixels)
TITLE_BAR_HEIGHT = 32

# Title of the PokeBot window — made invisible during capture (no minimize/flicker)
POKEBOT_WINDOW_TITLE = "PokeBot"

# Windows API constants
_GWL_EXSTYLE   = -20
_WS_EX_LAYERED = 0x00080000
_LWA_ALPHA     = 0x2
_user32        = ctypes.windll.user32


# ---------------------------------------------------------------
# Window alpha helpers (ctypes only — no extra packages needed)
# ---------------------------------------------------------------

def _find_hwnd(title_partial: str):
    """Return the HWND of the first window whose title contains title_partial."""
    result = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def _cb(hwnd, _):
        length = _user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_partial.lower() in buf.value.lower():
                result.append(hwnd)
        return True

    _user32.EnumWindows(EnumProc(_cb), 0)
    return result[0] if result else None


def _set_alpha(hwnd, alpha: int):
    """Set window transparency (0 = invisible, 255 = fully opaque). Instant, no focus change."""
    if hwnd is None:
        return
    style = _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    _user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style | _WS_EX_LAYERED)
    _user32.SetLayeredWindowAttributes(hwnd, 0, alpha, _LWA_ALPHA)


# ---------------------------------------------------------------
# Screen capture
# ---------------------------------------------------------------

def find_retroarch_window():
    """Return the bounding box of the RetroArch window, or None if not found."""
    if not PYGETWINDOW_AVAILABLE:
        return None
    windows = gw.getWindowsWithTitle(RETROARCH_WINDOW_TITLE)
    if not windows:
        return None
    win = windows[0]
    return {
        "left":   win.left,
        "top":    win.top,
        "width":  win.width,
        "height": win.height,
    }


def _capture_hwnd_printwindow(hwnd: int) -> Image.Image | None:
    """
    Capture a window's content using PrintWindow (PW_RENDERFULLCONTENT).
    Works on GPU-rendered windows (RetroArch OpenGL/Vulkan) on Windows 10+.
    No focus change, no flash, no transparency tricks.
    Returns PIL Image or None on failure.
    """
    # Get client rect (excludes title bar)
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
    w = rect.right  - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None

    # Create an in-memory DC + compatible bitmap
    hdc_src = ctypes.windll.user32.GetDC(hwnd)
    hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_src)
    hbm     = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_src, w, h)
    ctypes.windll.gdi32.SelectObject(hdc_mem, hbm)

    # PW_RENDERFULLCONTENT (0x2) — captures GPU-composited frame
    PW_RENDERFULLCONTENT = 0x00000002
    ctypes.windll.user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)

    # Pull pixel data out via GetDIBits
    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize",          ctypes.c_uint32),
            ("biWidth",         ctypes.c_int32),
            ("biHeight",        ctypes.c_int32),
            ("biPlanes",        ctypes.c_uint16),
            ("biBitCount",      ctypes.c_uint16),
            ("biCompression",   ctypes.c_uint32),
            ("biSizeImage",     ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed",       ctypes.c_uint32),
            ("biClrImportant",  ctypes.c_uint32),
        ]

    bmi           = _BITMAPINFOHEADER()
    bmi.biSize    = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.biWidth   = w
    bmi.biHeight  = -h   # negative → top-down row order
    bmi.biPlanes  = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0  # BI_RGB

    buf = (ctypes.c_char * (w * h * 4))()
    ctypes.windll.gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bmi), 0)

    # Cleanup GDI objects
    ctypes.windll.gdi32.DeleteObject(hbm)
    ctypes.windll.gdi32.DeleteDC(hdc_mem)
    ctypes.windll.user32.ReleaseDC(hwnd, hdc_src)

    img = Image.frombytes("RGBA", (w, h), bytes(buf), "raw", "BGRA")
    return img.convert("RGB")


def capture_screen() -> Image.Image:
    """
    Capture the RetroArch game window with zero flash.
    Uses PrintWindow (no focus change, no transparency tricks).
    Falls back to mss screen-region capture if PrintWindow returns a black frame.
    """
    # --- Primary: PrintWindow ---
    ra_hwnd = _find_hwnd(RETROARCH_WINDOW_TITLE)
    if ra_hwnd:
        img = _capture_hwnd_printwindow(ra_hwnd)
        if img is not None:
            # Sanity-check: reject pure-black frames (PrintWindow failed silently)
            extrema = img.convert("L").getextrema()
            if extrema[1] > 10:   # at least some non-black pixels
                return img

    # --- Fallback: mss region capture (no PokeBot hiding needed if it's off to side) ---
    bbox = find_retroarch_window()
    with mss.mss() as sct:
        if bbox and bbox["width"] > 0 and bbox["height"] > 0:
            region = {
                "left":   bbox["left"],
                "top":    bbox["top"] + TITLE_BAR_HEIGHT,
                "width":  bbox["width"],
                "height": max(1, bbox["height"] - TITLE_BAR_HEIGHT),
            }
        else:
            region = sct.monitors[1]
        raw = sct.grab(region)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def image_to_base64(img: Image.Image) -> str:
    """Convert a PIL image to a base64-encoded PNG string."""
    buffer = io.BytesIO()
    img.save(buffer, format=SCREENSHOT_FORMAT)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ---------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------

def build_system_prompt(game_state: dict = None, user_message: str = "") -> str:
    """Assemble the full system prompt: base + knowledge base + wiki + game state."""
    parts = [SYSTEM_PROMPT_BASE, get_knowledge()]

    # Inject wiki content — base pages + location-specific + user query
    if wiki_available():
        if game_state:
            wiki_content = search_for_state(game_state)
        else:
            wiki_content = get_base_content()
        # Always search by user message and append — don't gate on budget
        if user_message:
            extra = search(user_message)
            if extra and extra not in wiki_content:
                wiki_content = (wiki_content + "\n\n" + extra)[:6000]
        if wiki_content:
            parts.append("=== POKÉMON UNBOUND WIKI REFERENCE ===\n" + wiki_content)
    else:
        parts.append(
            "NOTE: The Pokémon Unbound wiki has not been downloaded yet. "
            "Run wiki_scraper.py once to give me full game knowledge."
        )

    if game_state:
        parts.append(format_state_for_prompt(game_state))

    # Inject known navigation routes from current location
    if NAV_MEMORY_AVAILABLE and game_state:
        location = game_state.get("location", "")
        if location and location != "Unknown":
            routes = format_routes_for_prompt(location)
            if routes:
                parts.append(routes)

    # Inject relevant past experiences
    if EXPERIENCE_AVAILABLE and game_state:
        location = game_state.get("location", "")
        situation = user_message[:200] if user_message else ""
        experiences = get_relevant_experiences(situation, location)
        if experiences:
            parts.append(experiences)

    return "\n\n".join(parts)


# ---------------------------------------------------------------
# Ollama chat API
# ---------------------------------------------------------------

def ask_llava(
    user_message: str,
    img: Image.Image = None,
    history: list = None,
    game_state: dict = None,
    stream_callback=None,
) -> str:
    """
    Send a message to gemma3 via the Ollama /api/chat endpoint.

    - user_message: the text the user typed
    - img: optional PIL screenshot to attach
    - history: list of {"role": "user"/"assistant", "content": "...", "images": [...]} dicts
    - game_state: current game state dict (injected into system prompt)
    - stream_callback: called with each text chunk as it arrives

    Returns the full response string.
    """
    if history is None:
        history = []

    # Prepend a hard RAM data block before every user message.
    # The model must trust RAM over visual guesses — pixel art is ambiguous,
    # RAM is ground truth. State this explicitly every single time.
    if game_state and game_state.get("location") and game_state["location"] != "Unknown":
        location     = game_state["location"]
        badges_count = len(game_state.get("badges", []))
        team_names   = ", ".join(p["name"] for p in game_state.get("team", []))
        ram_block = (
            f"[RAM DATA — GROUND TRUTH]\n"
            f"Current location : {location} (Borrius region, Pokémon Unbound)\n"
            f"Badges earned    : {badges_count}/8\n"
            f"Team             : {team_names}\n"
            f"This is read directly from game memory — always trust this over visual guesses.\n"
            f"If asked where you are, the answer is: {location}.\n"
            f"[END RAM DATA]\n\n"
            f"You also have full Pokémon Unbound wiki knowledge and general Pokémon knowledge — "
            f"use all of it to answer questions beyond just the RAM data above.\n\n"
        )
    else:
        ram_block = (
            f"[CONTEXT: Pokémon Unbound — Borrius region ROM hack. "
            f"NOT FireRed or any mainline game.]\n\n"
        )

    # Search wiki and inject pre-extracted facts directly into the user message.
    # Facts (location, type, etc.) are parsed out and stated explicitly so the
    # model cannot override them with its general Pokémon training knowledge.
    wiki_hit = ""
    if wiki_available() and user_message:
        try:
            raw, facts = search_with_facts(user_message)
            if facts:
                wiki_hit = (
                    f"[POKÉMON UNBOUND WIKI — CONFIRMED FACTS — DO NOT CONTRADICT]\n"
                    f"{facts}\n"
                    f"These facts are specific to Pokémon Unbound. "
                    f"They override anything you know from other Pokémon games.\n"
                    f"[END FACTS]\n\n"
                )
            elif raw:
                wiki_hit = (
                    f"[POKÉMON UNBOUND WIKI REFERENCE]\n"
                    f"{raw[:1200]}\n"
                    f"[END WIKI]\n\n"
                )
        except Exception:
            pass

    full_message = ram_block + wiki_hit + user_message

    # Build the new user message
    user_msg = {"role": "user", "content": full_message}
    if img is not None:
        user_msg["images"] = [image_to_base64(img)]

    messages = list(history) + [user_msg]

    payload = {
        "model":    MODEL_NAME,
        "system":   build_system_prompt(game_state, user_message),
        "messages": messages,
        "stream":   True,
    }

    full_response = []
    try:
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    full_response.append(chunk)
                    if stream_callback:
                        stream_callback(chunk)
                if data.get("done"):
                    break
    except requests.exceptions.ConnectionError:
        msg = "[Error] Could not connect to Ollama. Is it running?"
        if stream_callback:
            stream_callback(msg)
        return msg
    except Exception as e:
        msg = f"[Error] {e}"
        if stream_callback:
            stream_callback(msg)
        return msg

    return "".join(full_response)

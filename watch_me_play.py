# ============================================================
#  watch_me_play.py — passive recording while YOU play
#
#  Run this alongside main.py while you're playing normally.
#  Every N seconds it captures a screenshot + game state and
#  saves them to the training dataset — no AI control at all.
#
#  Usage:
#    python watch_me_play.py
#    python watch_me_play.py --interval 5   (capture every 5s)
# ============================================================

import time
import json
import os
from PIL import Image
import argparse
from datetime import datetime
from vision import capture_screen, image_to_base64
from game_state import load_state, refresh_from_ram

DATASET_FILE     = os.path.join(os.path.dirname(__file__), "training_data", "human_play.jsonl")
INTERVAL_DEFAULT = 8    # seconds between captures
CAPTURE_SIZE     = (480, 320)  # resize all frames to this before saving — consistent regardless of window size

os.makedirs(os.path.dirname(DATASET_FILE), exist_ok=True)


def record_frame(game_state: dict) -> dict:
    """Capture one frame and return the record."""
    img     = capture_screen()
    img     = img.resize(CAPTURE_SIZE, Image.Resampling.LANCZOS)
    img_b64 = image_to_base64(img)
    state_snap = {
        "location":  game_state.get("location", "Unknown"),
        "badges":    game_state.get("badges", []),
        "in_battle": game_state.get("in_battle", False),
        "team": [
            {
                "name":    p.get("name"),
                "level":   p.get("level"),
                "hp":      p.get("hp"),
                "max_hp":  p.get("max_hp"),
                "status":  p.get("status"),
            }
            for p in game_state.get("team", [])
        ],
    }
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "source":    "human_play",
        "state":     state_snap,
        "image_b64": img_b64,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=INTERVAL_DEFAULT,
                        help="Seconds between captures (default: 8)")
    args = parser.parse_args()

    print(f"[WatchMePlay] Recording every {args.interval}s → {DATASET_FILE}")
    print(f"[WatchMePlay] Press Ctrl+C to stop.\n")

    game_state = load_state()
    count = 0

    try:
        while True:
            # Pull fresh RAM state
            updated = refresh_from_ram(game_state)
            game_state.update(updated)

            record = record_frame(game_state)
            with open(DATASET_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

            count += 1
            location = game_state.get("location", "Unknown")
            battle   = "⚔ BATTLE" if game_state.get("in_battle") else "🗺 overworld"
            print(f"[{count:04d}] {location} | {battle} | captured")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n[WatchMePlay] Stopped. {count} frames recorded to {DATASET_FILE}")


if __name__ == "__main__":
    main()

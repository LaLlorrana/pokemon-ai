# ============================================================
#  data_collector.py — passive fine-tuning dataset recorder
#
#  Runs in the background while you play.
#  Records: screenshot + RAM state + action taken + outcome.
#  Saves to training_data/ as JSONL — ready for fine-tuning.
#
#  To start collecting: DataCollector.start()
#  To stop:             DataCollector.stop()
#  Dataset location:    training_data/dataset.jsonl
# ============================================================

import os
import json
import time
import base64
import threading
import io
from datetime import datetime
from PIL import Image

TRAINING_DIR  = os.path.join(os.path.dirname(__file__), "training_data")
DATASET_FILE  = os.path.join(TRAINING_DIR, "dataset.jsonl")
STATS_FILE    = os.path.join(TRAINING_DIR, "stats.json")

# Collect a sample every N seconds during auto-play
COLLECT_INTERVAL = 3.0

# Max image size for training (keep files manageable)
MAX_IMG_SIZE = (320, 240)


def _img_to_b64(img: Image.Image) -> str:
    img_small = img.copy()
    img_small.thumbnail(MAX_IMG_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img_small.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _load_stats() -> dict:
    if os.path.isfile(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_samples": 0, "started": datetime.now().isoformat()}


def _save_stats(stats: dict):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def save_sample(screenshot: Image.Image, game_state: dict,
                prompt: str, response: str, actions: list[str]):
    """
    Save one training sample to the dataset.

    screenshot:  PIL image of the game
    game_state:  current RAM-read state
    prompt:      what was asked of the model
    response:    what the model said
    actions:     list of actions executed (e.g. ["PRESS A", "SEQ UP,A"])
    """
    os.makedirs(TRAINING_DIR, exist_ok=True)

    sample = {
        "timestamp":  time.time(),
        "date":       datetime.now().isoformat(),
        "image":      _img_to_b64(screenshot),
        "game_state": {
            "location":  game_state.get("location", "Unknown"),
            "map_bank":  game_state.get("map_bank", 0),
            "map_number":game_state.get("map_number", 0),
            "badges":    game_state.get("badges", []),
            "team":      [
                {
                    "name":   p.get("name"),
                    "level":  p.get("level"),
                    "hp":     p.get("hp"),
                    "max_hp": p.get("max_hp"),
                    "status": p.get("status"),
                }
                for p in game_state.get("team", [])
            ],
        },
        "prompt":   prompt,
        "response": response,
        "actions":  actions,
        # Format suitable for instruction fine-tuning
        "instruction": prompt,
        "output":      response,
    }

    with open(DATASET_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(sample) + "\n")

    stats = _load_stats()
    stats["total_samples"] = stats.get("total_samples", 0) + 1
    stats["last_saved"] = datetime.now().isoformat()
    _save_stats(stats)

    return stats["total_samples"]


class DataCollector:
    """
    Passive background collector.
    Attach to the agent loop to record samples automatically.
    """
    def __init__(self):
        self.active     = False
        self._thread    = None
        self._stop      = threading.Event()
        self.game_state = {}
        self.sample_count = _load_stats().get("total_samples", 0)

    def start(self, game_state_ref: dict):
        self.game_state = game_state_ref
        self.active     = True
        self._stop.clear()
        print(f"[DataCollector] Started. Dataset: {DATASET_FILE}")
        print(f"[DataCollector] Existing samples: {self.sample_count}")

    def stop(self):
        self.active = False
        self._stop.set()
        print(f"[DataCollector] Stopped. Total samples: {self.sample_count}")

    def record(self, screenshot: Image.Image, prompt: str,
               response: str, actions: list[str]):
        """Call this after each agent step to record the sample."""
        if not self.active:
            return
        try:
            n = save_sample(screenshot, self.game_state, prompt, response, actions)
            self.sample_count = n
        except Exception as e:
            print(f"[DataCollector] Failed to save sample: {e}")

    def get_status(self) -> str:
        stats = _load_stats()
        return (
            f"Dataset: {stats.get('total_samples', 0)} samples | "
            f"Last saved: {stats.get('last_saved', 'never')} | "
            f"File: {DATASET_FILE}"
        )


# ── Fine-tuning prep script ─────────────────────────────────

def export_for_finetuning(output_file: str = None):
    """
    Export dataset in a format ready for fine-tuning with unsloth/transformers.
    Outputs a clean JSONL with 'instruction', 'input' (base64 image), 'output'.
    """
    if output_file is None:
        output_file = os.path.join(TRAINING_DIR, "finetune_ready.jsonl")

    if not os.path.isfile(DATASET_FILE):
        print("No dataset found. Play the game with data collection enabled first.")
        return

    count = 0
    with open(DATASET_FILE, "r") as fin, open(output_file, "w") as fout:
        for line in fin:
            try:
                sample = json.loads(line)
                # Skip samples with no actions (bot was stuck)
                if not sample.get("actions"):
                    continue
                export = {
                    "instruction": sample["instruction"],
                    "input":       sample["image"],   # base64 image
                    "output":      sample["output"],
                    "metadata": {
                        "location": sample["game_state"].get("location"),
                        "date":     sample["date"],
                    }
                }
                fout.write(json.dumps(export) + "\n")
                count += 1
            except Exception:
                continue

    print(f"Exported {count} samples to {output_file}")
    print("Ready for fine-tuning with unsloth or HuggingFace transformers.")
    return count


if __name__ == "__main__":
    stats = _load_stats()
    print(f"Dataset stats:")
    print(f"  Total samples: {stats.get('total_samples', 0)}")
    print(f"  Started:       {stats.get('started', 'unknown')}")
    print(f"  Last saved:    {stats.get('last_saved', 'never')}")
    print(f"  File:          {DATASET_FILE}")

    if os.path.isfile(DATASET_FILE):
        size_mb = os.path.getsize(DATASET_FILE) / (1024 * 1024)
        print(f"  File size:     {size_mb:.1f} MB")

        ans = input("\nExport for fine-tuning? (y/n): ")
        if ans.lower() == "y":
            export_for_finetuning()

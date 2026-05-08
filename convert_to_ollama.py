# ============================================================
#  convert_to_ollama.py — Convert fine-tuned model → Ollama
#
#  Run this after finetune.py to make your model available
#  as a drop-in replacement for gemma3:12b.
#
#  Usage:
#    python convert_to_ollama.py
#
#  What it does:
#    1. Merges LoRA adapter weights into the base model
#    2. Exports to GGUF (Q4_K_M quantization — best quality/size)
#    3. Creates an Ollama Modelfile
#    4. Runs: ollama create pokebot-unbound
#
#  After that, in config.py change:
#    MODEL_NAME = "pokebot-unbound"
# ============================================================

import os
import sys
import subprocess
from pathlib import Path

OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "finetune_output")
GGUF_PATH     = os.path.join(OUTPUT_DIR, "pokebot_unbound.gguf")
MODELFILE     = os.path.join(OUTPUT_DIR, "Modelfile")
OLLAMA_NAME   = "pokebot-unbound"


def check_ollama() -> bool:
    """Check that Ollama is installed and running."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_checkpoint() -> bool:
    """Check that a fine-tuning checkpoint exists."""
    config_file = os.path.join(OUTPUT_DIR, "adapter_config.json")
    return os.path.isfile(config_file)


def merge_and_export():
    """Merge LoRA weights and export to GGUF via unsloth."""
    print("Loading fine-tuned model from checkpoint...")
    try:
        from unsloth import FastVisionModel
        import torch

        model, tokenizer = FastVisionModel.from_pretrained(
            OUTPUT_DIR,
            load_in_4bit=False,   # merge at full precision
        )

        print(f"Exporting to GGUF (Q4_K_M) — this takes ~10–15 min...")
        model.save_pretrained_gguf(
            GGUF_PATH,
            tokenizer=tokenizer,
            quantization_method="q4_k_m",
        )
        print(f"✅ GGUF saved: {GGUF_PATH}")
        return True

    except ImportError:
        print("[Error] unsloth not installed. Run: pip install -r requirements_finetune.txt")
        return False
    except Exception as e:
        print(f"[Error] Export failed: {e}")
        return False


def write_modelfile():
    """Write the Ollama Modelfile."""
    content = f"""FROM {GGUF_PATH}

SYSTEM \"\"\"
You are an AI playing Pokémon Unbound, a GBA ROM hack set in the Borrius region.
You observe screenshots and decide actions using tags like <<PRESS:A>>, <<SEQ:UP,A>>, <<HOLD:LEFT:0.8>>.
Be decisive and efficient.
\"\"\"

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER repeat_penalty 1.1
"""
    with open(MODELFILE, "w") as f:
        f.write(content)
    print(f"Modelfile written: {MODELFILE}")


def register_with_ollama():
    """Run ollama create to register the model."""
    print(f"\nRegistering '{OLLAMA_NAME}' with Ollama...")
    try:
        result = subprocess.run(
            ["ollama", "create", OLLAMA_NAME, "-f", MODELFILE],
            capture_output=False,
            timeout=300,
        )
        if result.returncode == 0:
            print(f"\n✅ Model registered as '{OLLAMA_NAME}'")
            return True
        else:
            print(f"[Error] ollama create failed (return code {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print("[Error] Timed out waiting for ollama create")
        return False
    except FileNotFoundError:
        print("[Error] 'ollama' command not found. Is Ollama installed?")
        return False


def print_next_steps():
    print("\n" + "=" * 50)
    print("  Your fine-tuned model is ready!")
    print("=" * 50)
    print(f"\n  Model name: {OLLAMA_NAME}")
    print("\n  To use it in the bot, open config.py and change:")
    print(f'    MODEL_NAME = "{OLLAMA_NAME}"')
    print("\n  To test it manually:")
    print(f"    ollama run {OLLAMA_NAME}")
    print("\n  To switch back to gemma3 if needed:")
    print('    MODEL_NAME = "gemma3:12b"  (in config.py)')
    print()


def main():
    print("=" * 50)
    print("  PokeBot → Ollama Conversion")
    print("=" * 50)

    # ── Pre-flight checks ────────────────────────────────────
    if not check_checkpoint():
        print(f"\n[Error] No fine-tuned checkpoint found at {OUTPUT_DIR}")
        print("Run finetune.py first to train the model.")
        sys.exit(1)

    if not check_ollama():
        print("\n[Warning] Ollama doesn't appear to be running.")
        print("The GGUF will still be exported, but you'll need to")
        print("run 'ollama create' manually when Ollama is available.")

    # ── Already have GGUF? ───────────────────────────────────
    if os.path.isfile(GGUF_PATH):
        size_gb = os.path.getsize(GGUF_PATH) / 1e9
        print(f"\nFound existing GGUF ({size_gb:.1f} GB): {GGUF_PATH}")
        ans = input("Re-export from checkpoint? (y/n, default n): ").strip().lower()
        if ans != "y":
            print("Skipping export, using existing GGUF.")
        else:
            if not merge_and_export():
                sys.exit(1)
    else:
        if not merge_and_export():
            sys.exit(1)

    # ── Write Modelfile and register ────────────────────────
    write_modelfile()

    if check_ollama():
        register_with_ollama()
        print_next_steps()
    else:
        print("\nOllama not running — skipping registration.")
        print("When Ollama is running, register manually with:")
        print(f"  ollama create {OLLAMA_NAME} -f {MODELFILE}")


if __name__ == "__main__":
    main()

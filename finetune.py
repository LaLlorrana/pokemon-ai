# ============================================================
#  finetune.py — LoRA fine-tune a vision model on your gameplay
#
#  Model:   Qwen/Qwen2-VL-7B-Instruct  (best pixel-art vision)
#  Method:  QLoRA (4-bit base + LoRA adapters) via unsloth
#  Hardware: RTX 4080 Super (16 GB VRAM) — fits comfortably
#
#  Usage:
#    python finetune.py                     # train with defaults
#    python finetune.py --epochs 5          # more epochs
#    python finetune.py --min_samples 500   # lower threshold
#    python finetune.py --export            # export to GGUF after training
#
#  Output:
#    finetune_output/   — LoRA adapter checkpoint
#    finetune_output/pokebot_unbound.gguf  — (if --export)
# ============================================================

import os
import json
import base64
import argparse
import io
from pathlib import Path

TRAINING_DIR  = os.path.join(os.path.dirname(__file__), "training_data")
DATASET_FILE  = os.path.join(TRAINING_DIR, "dataset.jsonl")
OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "finetune_output")

BASE_MODEL    = "Qwen/Qwen2-VL-7B-Instruct"
LORA_RANK     = 16        # 16 = good balance of quality vs speed
LORA_ALPHA    = 32        # typically 2× rank
LORA_DROPOUT  = 0.05
MAX_SEQ_LEN   = 2048

# Training hyperparams — tuned for 4080 Super 16GB
BATCH_SIZE         = 2     # per device
GRAD_ACCUM_STEPS   = 4     # effective batch = 8
LEARNING_RATE      = 2e-4
WARMUP_RATIO       = 0.05
LR_SCHEDULER       = "cosine"
WEIGHT_DECAY       = 0.01
MAX_GRAD_NORM      = 1.0


# ── Dataset loader ──────────────────────────────────────────

def load_dataset(min_samples: int = 100) -> list:
    """Load and validate the collected gameplay dataset."""
    if not os.path.isfile(DATASET_FILE):
        raise FileNotFoundError(
            f"No dataset found at {DATASET_FILE}\n"
            "Play with the bot running (Auto Play mode) to collect data first."
        )

    samples = []
    skipped = 0
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
                # Skip samples with no actions (agent was idle/stuck)
                if not sample.get("actions"):
                    skipped += 1
                    continue
                # Skip STUCK samples — we don't want to learn failures
                if sample.get("actions") == ["STUCK"]:
                    skipped += 1
                    continue
                # Require both image and response
                if not sample.get("image") or not sample.get("response"):
                    skipped += 1
                    continue
                samples.append(sample)
            except json.JSONDecodeError:
                skipped += 1
                continue

    print(f"Loaded {len(samples)} usable samples ({skipped} skipped)")

    if len(samples) < min_samples:
        raise ValueError(
            f"Only {len(samples)} usable samples — need at least {min_samples}.\n"
            f"Keep playing with Auto Play running to collect more data."
        )

    return samples


def sample_to_messages(sample: dict) -> list:
    """
    Convert a collected sample to the Qwen2-VL chat format.

    Format:
      system:    Pokemon Unbound context
      user:      [image] + prompt
      assistant: response (with action tags)
    """
    game_state = sample.get("game_state", {})
    location   = game_state.get("location", "Unknown")
    team       = game_state.get("team", [])

    team_str = "\n".join(
        f"  {p.get('name','?')} Lv.{p.get('level','?')} — "
        f"{p.get('hp',0)}/{p.get('max_hp',1)} HP"
        for p in team
    ) or "  (unknown)"

    system_msg = (
        "You are an AI playing Pokémon Unbound, a GBA ROM hack set in the Borrius region. "
        "You observe screenshots and game state, then decide the best action to take. "
        "Always respond with action tags like <<PRESS:A>>, <<SEQ:UP,A>>, <<HOLD:LEFT:0.8>>, <<WAIT:0.5>>. "
        "Be decisive and efficient — speed matters."
    )

    user_content = [
        {
            "type": "image",
            "image": f"data:image/jpeg;base64,{sample['image']}",
        },
        {
            "type": "text",
            "text": (
                f"[Location: {location}]\n"
                f"[Team:\n{team_str}]\n\n"
                f"{sample.get('prompt', '').strip()}"
            ),
        },
    ]

    return [
        {"role": "system",    "content": system_msg},
        {"role": "user",      "content": user_content},
        {"role": "assistant", "content": sample.get("response", "").strip()},
    ]


# ── Training ────────────────────────────────────────────────

def train(epochs: int = 3, min_samples: int = 300, export_gguf: bool = False):
    print("=" * 60)
    print("  PokeBot Fine-tuning Pipeline")
    print("  Model: Qwen2-VL-7B-Instruct + QLoRA")
    print("=" * 60)

    # ── 1. Check dependencies ───────────────────────────────
    try:
        from unsloth import FastVisionModel
        import torch
        from trl import SFTTrainer, SFTConfig
        from datasets import Dataset
    except ImportError as e:
        print(f"\n[Error] Missing dependency: {e}")
        print("Install fine-tuning requirements first:")
        print("  pip install -r requirements_finetune.txt")
        return

    import torch
    print(f"\nGPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU (slow!)'}")
    if torch.cuda.is_available():
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"VRAM: {vram:.1f} GB")

    # ── 2. Load dataset ─────────────────────────────────────
    print(f"\nLoading dataset from {DATASET_FILE}...")
    samples = load_dataset(min_samples)
    print(f"Training on {len(samples)} samples × {epochs} epochs")

    # ── 3. Load base model with QLoRA ───────────────────────
    print(f"\nLoading {BASE_MODEL} with 4-bit quantization...")
    model, tokenizer = FastVisionModel.from_pretrained(
        BASE_MODEL,
        load_in_4bit=True,
        use_gradient_checkpointing="unsloth",  # saves 30% VRAM
    )

    # Attach LoRA adapters
    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers=True,   # train vision encoder too
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        random_state=42,
    )

    print(f"LoRA rank: {LORA_RANK} | α: {LORA_ALPHA}")
    model.print_trainable_parameters()

    # ── 4. Build HuggingFace Dataset ────────────────────────
    print("\nPreparing training data...")

    def convert_sample(sample):
        """Apply chat template to a sample."""
        messages = sample_to_messages(sample)
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text, "messages": messages}

    raw_data = [convert_sample(s) for s in samples]
    dataset  = Dataset.from_list(raw_data)
    print(f"Dataset ready: {len(dataset)} examples")

    # ── 5. Train ─────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    FastVisionModel.for_training(model)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        data_collator=_vision_collator(tokenizer),
        args=SFTConfig(
            output_dir=OUTPUT_DIR,
            num_train_epochs=epochs,
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM_STEPS,
            learning_rate=LEARNING_RATE,
            warmup_ratio=WARMUP_RATIO,
            lr_scheduler_type=LR_SCHEDULER,
            weight_decay=WEIGHT_DECAY,
            max_grad_norm=MAX_GRAD_NORM,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            save_steps=100,
            save_total_limit=2,
            dataset_text_field="text",
            max_seq_length=MAX_SEQ_LEN,
            remove_unused_columns=False,
            report_to="none",   # no W&B / wandb needed
        ),
    )

    print(f"\n▶ Training started — {epochs} epoch(s)...")
    print("  ETA on 4080 Super: ~2–4 hours for 1000 samples × 3 epochs\n")

    trainer_stats = trainer.train()

    print(f"\n✅ Training complete!")
    print(f"   Total steps:  {trainer_stats.global_step}")
    print(f"   Final loss:   {trainer_stats.training_loss:.4f}")
    print(f"   Time elapsed: {trainer_stats.metrics['train_runtime']:.0f}s")

    # ── 6. Save LoRA adapter ─────────────────────────────────
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"\nLoRA adapter saved to: {OUTPUT_DIR}")

    # ── 7. Optional: export to GGUF for Ollama ───────────────
    if export_gguf:
        _export_gguf(model, tokenizer)


def _vision_collator(tokenizer):
    """Data collator that handles multimodal (image+text) inputs."""
    from unsloth.trainer import UnslothVisionDataCollator
    return UnslothVisionDataCollator(model=None, tokenizer=tokenizer)


# ── GGUF Export ─────────────────────────────────────────────

def _export_gguf(model=None, tokenizer=None):
    """
    Merge LoRA weights and export to GGUF format for Ollama.
    If model/tokenizer not passed, loads from OUTPUT_DIR.
    """
    print("\n── Exporting to GGUF for Ollama ──")

    if model is None:
        try:
            from unsloth import FastVisionModel
            model, tokenizer = FastVisionModel.from_pretrained(
                OUTPUT_DIR,
                load_in_4bit=False,  # merge at full precision
            )
        except Exception as e:
            print(f"[Error] Could not load model for export: {e}")
            return

    gguf_path = os.path.join(OUTPUT_DIR, "pokebot_unbound.gguf")

    try:
        model.save_pretrained_gguf(
            gguf_path,
            tokenizer=tokenizer,
            quantization_method="q4_k_m",  # good quality/size tradeoff
        )
        print(f"GGUF saved: {gguf_path}")
        _print_ollama_instructions(gguf_path)
    except Exception as e:
        print(f"[Error] GGUF export failed: {e}")
        print("Try running convert_to_ollama.py manually instead.")


def _print_ollama_instructions(gguf_path: str):
    modelfile_path = os.path.join(OUTPUT_DIR, "Modelfile")
    modelfile_content = f'''FROM {gguf_path}

SYSTEM """
You are an AI playing Pokémon Unbound, a GBA ROM hack set in the Borrius region.
You observe screenshots and game state, then decide the best action using action tags.
"""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
'''
    with open(modelfile_path, "w") as f:
        f.write(modelfile_content)

    print(f"\nModelfile saved: {modelfile_path}")
    print("\n── To load your fine-tuned model into Ollama ──")
    print(f"  ollama create pokebot-unbound -f {modelfile_path}")
    print( "  Then in config.py, change MODEL_NAME to: 'pokebot-unbound'")


# ── Dataset stats ────────────────────────────────────────────

def print_dataset_stats():
    """Quick summary of what's been collected so far."""
    if not os.path.isfile(DATASET_FILE):
        print("No dataset yet. Start the bot in Auto Play mode to collect data.")
        return

    samples = []
    with open(DATASET_FILE, "r") as f:
        for line in f:
            try:
                samples.append(json.loads(line.strip()))
            except Exception:
                continue

    if not samples:
        print("Dataset file exists but is empty.")
        return

    total      = len(samples)
    with_actions = sum(1 for s in samples if s.get("actions") and s["actions"] != ["STUCK"])
    stuck      = sum(1 for s in samples if s.get("actions") == ["STUCK"])
    complete   = sum(1 for s in samples if s.get("actions") == ["GOAL_COMPLETE"])
    locations  = set(s.get("game_state", {}).get("location", "Unknown") for s in samples)
    size_mb    = os.path.getsize(DATASET_FILE) / (1024 * 1024)

    print("=" * 50)
    print("  Dataset Statistics")
    print("=" * 50)
    print(f"  Total samples:     {total}")
    print(f"  Usable (w/actions):{with_actions}")
    print(f"  Stuck samples:     {stuck}")
    print(f"  Goal completions:  {complete}")
    print(f"  Unique locations:  {len(locations)}")
    print(f"  File size:         {size_mb:.1f} MB")
    print(f"  File:              {DATASET_FILE}")
    print()
    if with_actions >= 1000:
        print("  ✅ Ready for fine-tuning! Run: python finetune.py")
    elif with_actions >= 300:
        print(f"  ⚡ Getting there — {1000 - with_actions} more samples until recommended minimum.")
    else:
        print(f"  ⏳ Keep playing — {300 - with_actions} more samples until bare minimum (1000 recommended).")


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune PokeBot on your gameplay data")
    parser.add_argument("--epochs",      type=int,  default=3,   help="Training epochs (default: 3)")
    parser.add_argument("--min_samples", type=int,  default=300, help="Minimum usable samples required (default: 300)")
    parser.add_argument("--export",      action="store_true",    help="Export to GGUF for Ollama after training")
    parser.add_argument("--stats",       action="store_true",    help="Print dataset stats and exit")
    parser.add_argument("--export_only", action="store_true",    help="Skip training, just export existing checkpoint to GGUF")
    args = parser.parse_args()

    if args.stats:
        print_dataset_stats()
    elif args.export_only:
        _export_gguf()
    else:
        train(
            epochs=args.epochs,
            min_samples=args.min_samples,
            export_gguf=args.export,
        )

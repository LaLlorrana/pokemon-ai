import os
import json

# List of locations from WRONG games (FireRed, etc.)
FAKE_LOCATIONS = [
    "Vermillion", "Cerulean", "Pewter", "Saffron", "Lavender",
    "Pallet", "Viridian", "Celadon", "Fuchsia", "Cinnabar",
    "Silverleaf", "Mystic Grove", "Shadow Brook"
]

# Real Unbound locations (from your knowledge_base.py)
REAL_LOCATIONS = [
    "Dehara City", "Bellin Town", "Dresco Town", "Blizzard City",
    "Crater Town", "Fallshore City", "Epidimy Town", "Tarmigan Town",
    "Antisis City", "Seaport City", "Gurun Town", "Vivill Town",
    "Polder Town", "Magnolia Town", "Redwood Village", "Frozen Heights",
    "Tehl Town"
]

print("🔍 Checking for hallucinated locations...\n")

# Check Python files
print("=== Checking .py files ===")
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for fake in FAKE_LOCATIONS:
                    if fake.lower() in content.lower():
                        print(f"⚠️  Found '{fake}' in {filepath}")

# Check JSON files
print("\n=== Checking .json files ===")
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".json"):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for fake in FAKE_LOCATIONS:
                    if fake.lower() in content.lower():
                        print(f"⚠️  Found '{fake}' in {filepath}")

# Check wiki_data folder exists and has content
print("\n=== Checking wiki_data folder ===")
if os.path.exists("wiki_data"):
    wiki_files = [f for f in os.listdir("wiki_data") if f.endswith(".txt")]
    print(f"✅ Found {len(wiki_files)} wiki files")
    
    # Sample a few
    print("\n📄 Sample wiki files:")
    for i, f in enumerate(wiki_files[:5]):
        print(f"   - {f}")
else:
    print("❌ wiki_data folder not found!")

print("\n✅ Check complete!")
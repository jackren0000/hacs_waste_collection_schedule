import os
import sys
import types
import importlib.util
import json
from council_lookup import get_council

# --- Stub Collection class so imported sources work ---
class Collection:
    def __init__(self, date, t, icon):
        self.date = date
        self.t = t
        self.icon = icon
    def __repr__(self):
        return f"Collection(date={self.date}, t={self.t}, icon={self.icon})"

stub = types.ModuleType("waste_collection_schedule")
stub.Collection = Collection
sys.modules["waste_collection_schedule"] = stub

# --- Helper functions ---
def normalize(s):
    """Lowercase, remove non-alphanumeric for loose matching."""
    return ''.join(ch for ch in s.lower() if ch.isalnum())

def find_module_for_council(council, sources_path):
    """Find provider module name for council using sources.json mapping."""
    with open(sources_path, 'r') as f:
        sources_data = json.load(f)
    entries = sources_data.get("Australia", [])
    norm_c = normalize(council)
    for entry in entries:
        if norm_c in normalize(entry.get('title', '')):
            return entry['module']
    return None

def load_source_module(module_name, base_dir):
    """Dynamically load provider module by name."""
    src_file = os.path.join(
        base_dir,
        "custom_components", "waste_collection_schedule",
        "waste_collection_schedule", "source", f"{module_name}.py"
    )
    if not os.path.isfile(src_file):
        raise FileNotFoundError(f"Source file not found: {src_file}")
    spec = importlib.util.spec_from_file_location("source_mod", src_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Source

def main():
    address = input("Enter address: ").strip()
    council = get_council(address)
    if not council:
        print(f"Could not determine council for address: {address}")
        sys.exit(1)
    print(f"Detected council: {council}")

    # Special-case fast path
    norm_council = council.lower()
    if 'monash' in norm_council:
        module_name = 'monash_vic_gov_au'
    elif 'melbourne' in norm_council:
        module_name = 'melbourne_vic_gov_au'
    elif 'frankston' in norm_council:
        module_name = 'frankston_vic_gov_au'  # adjust to actual Frankston module name
    else:
        # Use sources.json
        sources_path = os.path.join(
            os.path.dirname(__file__),
            "custom_components", "waste_collection_schedule", "sources.json"
        )
        module_name = find_module_for_council(council, sources_path)
        if not module_name:
            print(f"No source module found for council '{council}'.")
            sys.exit(1)

    # Load and use the source module
    try:
        Source = load_source_module(module_name, os.path.dirname(__file__))
        src = Source(street_address=address)
        for entry in src.fetch():
            print(entry)
    except Exception as e:
        print("Error fetching data:", e)

if __name__ == "__main__":
    main()

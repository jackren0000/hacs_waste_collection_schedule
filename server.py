"""
Simple Flask-based backend for waste_collection_schedule.
Provides a /collections endpoint accepting an 'address' query parameter.
"""
from flask import Flask, request, jsonify
import os, sys, types, importlib.util, json
from council_lookup import get_council

# Ensure the custom_components directory is in the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "custom_components", "waste_collection_schedule"))

# Stub Collection for import
stub = types.ModuleType("waste_collection_schedule")
from waste_collection_schedule import Collection as RealCollection  # type: ignore
stub.Collection = RealCollection
sys.modules["waste_collection_schedule"] = stub

# Helper to normalize
def normalize(s): return ''.join(ch for ch in s.lower() if ch.isalnum())

# Find module via sources.json
def find_module_for_council(council):
    path = os.path.join(os.path.dirname(__file__), "custom_components", "waste_collection_schedule", "sources.json")
    with open(path) as f:
        data = json.load(f)
    for entry in data.get("Australia", []):
        if normalize(council) in normalize(entry.get("title", "")):
            return entry["module"]
    return None

# Dynamically load source class
def load_source(module_name):
    base = os.path.dirname(__file__)
    src_file = os.path.join(base, "custom_components", "waste_collection_schedule", "waste_collection_schedule", "source", f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, src_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Source

app = Flask(__name__)

def extract_street_and_suburb(full_address):
    """Extract just the street and suburb from a full address"""
    # Split by comma and take first two parts (street, suburb)
    parts = [part.strip() for part in full_address.split(',')]
    if len(parts) >= 2:
        return f"{parts[0]}, {parts[1]}"
    return parts[0] if parts else full_address

@app.route('/collections', methods=['GET'])
def get_collections():
    address = request.args.get('address')
    if not address:
        return jsonify({'error':'address parameter is required'}), 400
    council = get_council(address)
    if not council:
        return jsonify({'error':'could not determine council'}), 404
    # Special-case fallbacks
    lower = council.lower()
    if 'monash' in lower:
        module = 'monash_vic_gov_au'
    elif 'melbourne' in lower:
        module = 'melbourne_vic_gov_au'
    else:
        module = find_module_for_council(council)
    if not module:
        return jsonify({'error':f'no source found for {council}'}), 404
    
    # Extract just street and suburb for the source
    simplified_address = extract_street_and_suburb(address)
    
    # load and fetch
    Source = load_source(module)
    # instantiate
    try:
        # try street_address param
        instance = Source(street_address=simplified_address)
    except TypeError:
        instance = Source(address=simplified_address)
    try:
        cols = instance.fetch()
    except Exception as e:
        return jsonify({'error':str(e)}), 500

    # build response: only the closest date for each collection type
    # sort collections by date and pick first occurrence of each type
    cols_sorted = sorted(cols, key=lambda c: c.date)
    seen = set()
    out = []
    for c in cols_sorted:
        if c.type not in seen:
            out.append({'date': str(c.date), 'type': c.type, 'icon': c.icon})
            seen.add(c.type)

    return jsonify({'council': council, 'address': simplified_address, 'collections': out})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

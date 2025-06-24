import requests

API_KEY = "AIzaSyC4R9I9uopoOY10-2hi-BdpsLAciALG1lk"

def get_council(address: str) -> str:
    """
    Lookup the administrative_area_level_2 (city council / LGA) for a given address using Google Maps Geocoding API.
    Returns the long name of the council or None if not found.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": API_KEY}
    resp = requests.get(url, params=params)
    data = resp.json()
    for component in data.get('results', [])[0].get('address_components', []):
        if "administrative_area_level_2" in component.get('types', []):
            return component.get('long_name')
    return None

if __name__ == "__main__":
    addr = input("Enter address: ")
    council = get_council(addr)
    print("Council (city council / LGA) is:", council)


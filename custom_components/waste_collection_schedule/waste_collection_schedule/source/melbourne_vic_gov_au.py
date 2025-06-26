import time
import os
import requests
import json
from datetime import datetime, timedelta
from waste_collection_schedule import Collection

TITLE = "City of Melbourne"
DESCRIPTION = "Source script for melbourne.vic.gov.au"
URL = "https://data.melbourne.vic.gov.au"
TEST_CASES = {
    # Example test cases
    "Queen Victoria Market": {"address": "Queen Victoria Market, Melbourne VIC"},
}
GEOJSON_URL = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/garbage-collection-zones/exports/geojson?lang=en&timezone=Australia%2FSydney"
ICON_MAP = {
    "Recycling": "mdi:recycle",
    "General Waste": "mdi:trash-can",
}

class Source:
    def __init__(self, street_address):
        self._address = street_address

    def get_zones(self):
        resp = requests.get(GEOJSON_URL)
        resp.raise_for_status()
        return resp.json().get("features", [])

    def compute_bbox(self, features):
        minx = miny = float('inf')
        maxx = maxy = float('-inf')
        for feat in features:
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            geom_type = geom.get("type")
            polys = []
            if geom_type == "Polygon": polys = [coords]
            elif geom_type == "MultiPolygon": polys = coords
            for poly in polys:
                for ring in poly:
                    for lon, lat in ring:
                        minx = min(minx, lon); maxx = max(maxx, lon)
                        miny = min(miny, lat); maxy = max(maxy, lat)
        return minx, miny, maxx, maxy

    def geocode(self, bbox):
        # Use Nominatim fallback
        params = {"q": self._address, "format": "json", "limit": 1,
                  "viewbox": f"{bbox[0]},{bbox[3]},{bbox[2]},{bbox[1]}", "bounded": 1}
        r = requests.get("https://nominatim.openstreetmap.org/search", params=params,
                         headers={"User-Agent": "waste-collection-script"})
        r.raise_for_status()
        data = r.json()
        if not data: raise ValueError("Address not found")
        lat = float(data[0]["lat"]); lon = float(data[0]["lon"])
        return lat, lon

    def point_in_polygon(self, x, y, poly):
        inside = False
        j = len(poly) - 1
        for i in range(len(poly)):
            xi, yi = poly[i]; xj, yj = poly[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def find_zone(self, features, lat, lon):
        for feat in features:
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", []); geom_type = geom.get("type")
            poly_list = [coords] if geom_type == "Polygon" else coords
            for poly in poly_list:
                if self.point_in_polygon(lon, lat, poly[0]):
                    return feat.get("properties", {})
        return {}

    def get_collections(self, day_name, weeks, start_date_str):
        weeks = int(weeks)
        weekday = time.strptime(day_name, "%A").tm_wday
        today = datetime.now().date()
        start = datetime.strptime(start_date_str, "%Y/%m/%d").date()
        delta = (weekday - today.weekday() + 7) % 7
        next_date = today + timedelta(days=delta)
        if next_date < start: next_date = start
        while ((next_date - start).days // 7) % weeks != 0:
            next_date += timedelta(weeks=weeks)
        return [next_date + timedelta(weeks=i*weeks) for i in range(4)]

    def fetch(self):
        features = self.get_zones()
        bbox = self.compute_bbox(features)
        lat, lon = self.geocode(bbox)
        props = self.find_zone(features, lat, lon)
        entries = []
        # Recycling
        if props.get("rec_day"):  # ensure property exists in geojson
            for d in self.get_collections(props["rec_day"], props.get("rec_weeks",1), props.get("rec_start","")):
                entries.append(Collection(date=d, t="Recycling", icon=ICON_MAP["Recycling"]))
        # General Waste
        if props.get("rub_day"):
            for d in self.get_collections(props["rub_day"], props.get("rub_weeks",1), props.get("rub_start","")):
                entries.append(Collection(date=d, t="General Waste", icon=ICON_MAP["General Waste"]))
        return entries
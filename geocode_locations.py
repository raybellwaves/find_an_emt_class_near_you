# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests>=2.31.0",
# ]
# ///
# GOOGLE_MAPS_API_KEY=... uv run geocode_locations.py
"""Geocode MFRI locations that host EMT classes using Google Places Text Search.

Results are cached in mfri_locations.json (same field names as the Firefighter I
project), so only new locations cost an API call on later runs.
"""

import json
import os
import re

import requests

LOCATIONS = "mfri_locations.json"
CLASSES = "mfri_emt_old_and_new_courses.json"
URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.location"


def query_for(loc):
    # PO boxes confuse place search; keep street + city/state/zip
    addr = re.sub(r"\b(P\.?\s?O\.?|Post Office)\s+Box\s+\d+,?\s*", "", loc["address"], flags=re.I)
    if addr:
        return f"{loc['location']}, {addr}"
    return f"{loc['location']}, {loc['county']} County, Maryland"


def geocode(text, key):
    r = requests.post(
        URL,
        headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS},
        json={"textQuery": text, "maxResultCount": 1, "regionCode": "us"},
        timeout=30,
    )
    r.raise_for_status()
    places = r.json().get("places", [])
    return places[0] if places else None


def main():
    key = os.environ["GOOGLE_MAPS_API_KEY"]
    locations = json.load(open(LOCATIONS))
    used = {c["location"] for c in json.load(open(CLASSES))}
    todo = [l for l in locations if l["location"] in used and "locationLatitudeLongitude" not in l]
    print(f"Geocoding {len(todo)} locations")
    for loc in todo:
        place = geocode(query_for(loc), key)
        # If Google picked a different street number, fall back to address only
        num = re.match(r"\s*(\d+)", re.sub(r"^.*?Box\s+\d+,?\s*", "", loc["address"], flags=re.I))
        if place and num and not place.get("formattedAddress", "").startswith(num.group(1)):
            place = geocode(re.sub(r"\b(P\.?\s?O\.?|Post Office)\s+Box\s+\d+,?\s*", "", loc["address"], flags=re.I), key) or place
        if not place:
            print(f"  no match: {loc['location']}")
            continue
        latlng = f"{place['location']['latitude']},{place['location']['longitude']}"
        loc.update(
            {
                "formattedAddress": place.get("formattedAddress"),
                "locationLatitudeLongitude": latlng,
                "displayName": place.get("displayName", {}).get("text"),
                "googleMapsUrl": f"https://www.google.com/maps/place/?q=place_id:{place['id']}",
                "googleMapsDirectionsUrl": f"https://www.google.com/maps/dir//{latlng}?travelmode=driving",
            }
        )
    with open(LOCATIONS, "w") as f:
        json.dump(locations, f, indent=4)


if __name__ == "__main__":
    main()

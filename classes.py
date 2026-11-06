# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "beautifulsoup4>=4.12.0",
#     "requests>=2.31.0",
#     "tqdm>=4.66.1",
# ]
# ///
# uv run classes.py
"""Daily update of upcoming MFRI EMT (EMS-106) classes.

1. Crawl section pages for the current and next MFRI fiscal year. The course
   listing page only shows classes whose registration is open, so it misses
   upcoming classes (e.g. agency/academy sections).
2. Enrich with days and registration window from the listing page.
3. Join location details from the committed mfri_locations.json (no API calls;
   run mfri_locations.py + geocode_locations.py by hand if a location is missing).
4. Merge into the history file so past class locations stay on the map.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from bs4 import BeautifulSoup

from all_emt_classes import OUTPUT as HISTORY_FILE
from all_emt_classes import SECTIONS, fetch, session

LISTING_URL = "https://www.mfri.org/course/msfs/EMS/106/"
LOCATIONS_FILE = "mfri_locations.json"
OUTPUT = "current_emt_classes.json"
LOCATION_FIELDS = {
    "locationUrlId": "urlId",
    "locationCounty": "county",
    "locationServedBy": "servedBy",
    "locationServedByUrl": "servedByUrl",
    "locationFormattedAddress": "formattedAddress",
    "locationLatitudeLongitude": "locationLatitudeLongitude",
    "locationDisplayName": "displayName",
    "locationGoogleMapsUrl": "googleMapsUrl",
    "locationGoogleMapsDirectionsUrl": "googleMapsDirectionsUrl",
}


def parse_date(s):
    return datetime.strptime(s, "%m-%d-%Y") if s else None


def current_fiscal_year(today):
    # MFRI fiscal year runs July-June; FY2027 = July 2026 - June 2027
    return today.year + 1 if today.month >= 7 else today.year


def listing_details():
    """Days and registration window for classes on the listing page."""
    r = session.get(LISTING_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    details = {}
    for item in soup.find_all("div", class_="event-item"):
        lines = item.get_text("\n", strip=True).split("\n")
        ids = [l for l in lines if re.fullmatch(r"EMS-106-[A-Z]\d{3}-\d{4}", l)]
        if not ids:
            continue
        info = {"listedAsOpen": True}
        for i, line in enumerate(lines):
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            if line.startswith("Registration Open:"):
                info["registrationOpens"] = line.split(":", 1)[1].strip() or nxt
            elif line.startswith("Registration Close:"):
                info["registrationCloses"] = line.split(":", 1)[1].strip() or nxt
            elif re.match(r"^(Mondays?|Tuesdays?|Wednesdays?|Thursdays?|Fridays?|Saturdays?|Sundays?)\b", line):
                info["days"] = line
        details[ids[0]] = info
    return details


def main():
    today = datetime.now()
    fy = current_fiscal_year(today)
    jobs = [(s, y) for y in (fy, fy + 1) for s in SECTIONS]
    with ThreadPoolExecutor(max_workers=8) as ex:
        crawled = [c for c in ex.map(fetch, jobs) if c]
    crawled = list({c["courseId"]: c for c in crawled}.values())
    print(f"Crawled {len(crawled)} EMT sections for FY{fy}-FY{fy + 1}")

    # Update history (keyed by courseId; newest scrape wins)
    try:
        history = {c["courseId"]: c for c in json.load(open(HISTORY_FILE))}
    except FileNotFoundError:
        history = {}
    history.update({c["courseId"]: c for c in crawled})
    with open(HISTORY_FILE, "w") as f:
        json.dump(
            sorted(history.values(), key=lambda c: parse_date(c["startDate"]) or datetime.min),
            f,
            indent=4,
        )

    listed = listing_details()
    locations = {}
    for loc in json.load(open(LOCATIONS_FILE)):
        locations.setdefault(loc["location"], loc)

    upcoming = []
    for c in crawled:
        start = parse_date(c["startDate"])
        if not start or start.date() < today.date():
            continue
        c = {"days": None, "registrationOpens": None, "registrationCloses": None, "listedAsOpen": False, **c}
        c.update(listed.get(c["courseId"], {}))
        loc = locations.get(c["location"])
        if loc:
            c.update({k: loc.get(v) for k, v in LOCATION_FIELDS.items()})
        if not loc or not loc.get("locationLatitudeLongitude"):
            print(f"  -> Note: '{c['location']}' ({c['courseId']}) not geocoded in {LOCATIONS_FILE}")
        upcoming.append(c)

    upcoming.sort(key=lambda c: parse_date(c["startDate"]))
    with open(OUTPUT, "w") as f:
        json.dump(upcoming, f, indent=4)
    print(f"Saved {len(upcoming)} upcoming EMT classes to {OUTPUT}")
    for c in upcoming:
        print(f"  {c['courseId']} {c['startDate']} {c['firstClassTime']} | {c['location']} | open={c['listedAsOpen']}")


if __name__ == "__main__":
    main()

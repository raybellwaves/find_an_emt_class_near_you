# Find an EMT class near you

Want to ride as an EMS provider with a Maryland volunteer fire company? Find upcoming
[MFRI Emergency Medical Technician (EMS-106)](https://www.mfri.org/course/msfs/EMS/106/) classes on a map.

Map: https://raybellwaves.github.io/find_an_emt_class_near_you/

- Colored dots are upcoming classes, colored by the month they start.
- Black dots are locations that have run EMT classes before but have none coming up.

Companion to [find_a_firefighter_I_class_near_you](https://github.com/raybellwaves/find_a_firefighter_I_class_near_you).

## How it works

A daily GitHub Action ([cron.yml](.github/workflows/cron.yml)) runs:

| Script | What it does |
|---|---|
| `classes.py` | Crawls MFRI EMT section pages for the current and next fiscal year, adds days and registration dates from the course listing, joins location details from `mfri_locations.json`, writes `current_emt_classes.json`, and adds new classes to `mfri_emt_old_and_new_courses.json`. |
| `generate_map.py` | Builds `docs/index.html` with [folium](https://python-visualization.github.io/folium/). |

The MFRI course listing only shows classes with open registration, so `classes.py`
crawls section pages (`/course/msfs/EMS/106/S001/2027/` and so on) to find every upcoming class.
MFRI ignores the letter in the section URL, so only the number is crawled.

## Run by hand when needed

These are not part of the daily job:

| Script | When to run |
|---|---|
| `all_emt_classes.py` | Rebuild the full EMT class history (FY2020 onward). About 2 minutes. |
| `mfri_locations.py` | Fresh pull of all MFRI locations (name, county, office, address). Slow. |
| `geocode_locations.py` | Geocode locations that host EMT classes with the Google Places API. Needs `GOOGLE_MAPS_API_KEY`. Only new locations are looked up. |

Run these when `classes.py` prints a note that a location is not geocoded.

All scripts use [uv inline script dependencies](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies):

```bash
uv run classes.py
uv run generate_map.py
```

## Anne Arundel County requirements

From the [AACoFD volunteer page](https://www.aacounty.org/fire-department/volunteer-opportunities),
EMS volunteers must complete before they can ride:

- EMT-B (the county page says 165 hours; the MFRI course is now 207 hours)
- AED/CPR (8 hours)
- Haz-Mat Awareness (6 hours) or Haz-Mat Operations (36 hours)
- NIMS 200 and 700 (online)

Vibe coded with AI. May contain errors.

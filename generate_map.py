# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "folium>=0.14.0",
# ]
# ///
# uv run generate_map.py
"""Build docs/index.html: a map of upcoming MFRI EMT classes in Maryland.

Upcoming classes are colored by start month. Locations that have hosted EMT
classes before but have none coming up are shown in black with past start dates.
"""

import json
import os
from datetime import datetime, timezone
from html import escape

import folium
from folium.plugins import LocateControl

CURRENT_FILE = "current_emt_classes.json"
HISTORY_FILE = "mfri_emt_old_and_new_courses.json"
LOCATIONS_FILE = "mfri_locations.json"
BOUNDARY_FILE = "maryland-single.geojson"
OUTPUT = "docs/index.html"
REPO_URL = "https://github.com/raybellwaves/find_an_emt_class_near_you"

MONTH_COLORS = {
    1: "#00008B", 2: "#0000FF", 3: "#ADD8E6", 4: "#00FFFF",
    5: "#90EE90", 6: "#FFFF00", 7: "#FF0000", 8: "#FF4500",
    9: "#FFA500", 10: "#FA8072", 11: "#87CEEB", 12: "#0000CD",
}
INACTIVE_COLOR = "#000000"


def parse_date(s):
    return datetime.strptime(s, "%m-%d-%Y") if s else None


def latlng(s):
    lat, lng = s.split(",")
    return float(lat), float(lng)


def link(url, text):
    return f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(text)}</a>' if url else ""


def class_popup(c):
    rows = [
        ("Location", c.get("locationDisplayName") or c["location"]),
        ("Course", c["courseId"]),
        ("Dates", f"{c['startDate']} to {c['endDate']}"),
        ("Days", c.get("days")),
        ("First class time", c.get("firstClassTime")),
        ("Hours", c.get("instructionalHours")),
        ("Registration closes", c.get("registrationCloses")),
        ("Coordinated by", c.get("coordinateBy")),
        ("Contact", c.get("contact")),
    ]
    html = "".join(f"<b>{k}:</b> {escape(str(v))}<br>" for k, v in rows if v)
    if not c.get("listedAsOpen"):
        html += (
            "<i>Not listed as open on the MFRI schedule: registration may be closed "
            "or limited to an agency. Contact the coordinating office.</i><br>"
        )
    html += " | ".join(
        x
        for x in (
            link(c.get("courseUrl"), "Class details"),
            link(c.get("registerLink") if c.get("listedAsOpen") else None, "Register"),
            link(c.get("locationGoogleMapsDirectionsUrl"), "Directions"),
        )
        if x
    )
    return html


def add_legend(m):
    items = [(INACTIVE_COLOR, "No upcoming classes")] + [
        (color, datetime(2000, month, 1).strftime("%B")) for month, color in MONTH_COLORS.items()
    ]
    rows = "".join(
        f'<div style="display:flex;align-items:center;margin-bottom:3px;">'
        f'<i style="background:{color};width:15px;height:15px;display:inline-block;'
        f'margin-right:5px;border:1px solid #888;"></i><span>{name}</span></div>'
        for color, name in items
    )
    m.get_root().html.add_child(
        folium.Element(
            f"""
    <div id="mapLegend" style="position:fixed;bottom:20px;left:20px;z-index:9999;
         background:white;border:2px solid grey;border-radius:5px;font-size:14px;
         box-shadow:0 2px 5px rgba(0,0,0,0.2);">
      <button id="legendHeader" type="button" aria-expanded="false" aria-controls="legendContent"
              onclick="var c=document.getElementById('legendContent');var open=c.hidden;
                       c.hidden=!open;this.setAttribute('aria-expanded',open);
                       this.querySelector('.icon').textContent=open?'[-]':'[+]';"
              style="width:100%;padding:8px;background:#f0f0f0;border:none;cursor:pointer;
                     display:flex;justify-content:space-between;font:inherit;font-weight:bold;">
        <span>Class starts</span><span class="icon" style="margin-left:10px;">[+]</span>
      </button>
      <div id="legendContent" hidden style="padding:8px;max-height:220px;overflow-y:auto;">{rows}</div>
    </div>"""
        )
    )


def main():
    current = json.load(open(CURRENT_FILE))
    history = json.load(open(HISTORY_FILE))
    locations = {}
    for loc in json.load(open(LOCATIONS_FILE)):
        locations.setdefault(loc["location"], loc)

    m = folium.Map(location=[39.0, -76.8], zoom_start=8)
    m.get_root().html.add_child(
        folium.Element('<h1 style="text-align:center;font-size:20px;">Find an EMT class near you</h1>')
    )
    folium.GeoJson(
        json.load(open(BOUNDARY_FILE)),
        name="Maryland border",
        style_function=lambda _: {"color": "black", "weight": 2, "fillOpacity": 0},
    ).add_to(m)

    # Past-only locations first, so upcoming classes draw on top
    active = {c["location"] for c in current}
    past = {}
    for c in history:
        if c["location"] not in active and c.get("startDate"):
            past.setdefault(c["location"], []).append(c["startDate"])
    for name, dates in past.items():
        loc = locations.get(name)
        if not loc or not loc.get("locationLatitudeLongitude"):
            continue
        dates = sorted(set(dates), key=parse_date, reverse=True)
        popup = (
            f"<b>Location:</b> {escape(loc.get('displayName') or name)}<br>"
            f"<b>No upcoming EMT classes.</b> {len(dates)} past classes since {dates[-1][-4:]}.<br>"
            f"<b>Recent start dates:</b> {', '.join(dates[:5])}<br>"
            + link(loc.get("googleMapsDirectionsUrl"), "Directions")
        )
        folium.CircleMarker(
            latlng(loc["locationLatitudeLongitude"]),
            radius=4,
            weight=1,
            color=INACTIVE_COLOR,
            fill=True,
            fill_color=INACTIVE_COLOR,
            fill_opacity=1,
            popup=folium.Popup(popup, max_width=300),
            tooltip=escape(loc.get("displayName") or name),
        ).add_to(m)

    for c in current:
        if not c.get("locationLatitudeLongitude"):
            print(f"Skipping {c['courseId']}: '{c['location']}' has no coordinates")
            continue
        color = MONTH_COLORS[parse_date(c["startDate"]).month]
        folium.CircleMarker(
            latlng(c["locationLatitudeLongitude"]),
            radius=9,
            weight=2,
            color="#333333",
            fill=True,
            fill_color=color,
            fill_opacity=1,
            popup=folium.Popup(class_popup(c), max_width=320),
            tooltip=escape(f"{c.get('locationDisplayName') or c['location']} - starts {c['startDate']}"),
        ).add_to(m)

    add_legend(m)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    m.get_root().html.add_child(
        folium.Element(
            f"""<div style="text-align:center;margin-top:10px;font-size:12px;color:#333;line-height:1.6;">
            Last updated: {updated}
            | Vibe coded with AI. May contain errors.
            | Color shows the month the class starts. Black shows locations with past EMT classes but none coming up.
            | Data from {link("https://www.mfri.org/course/msfs/EMS/106/", "MFRI Emergency Medical Technician courses")}
            | Source code on {link(REPO_URL, "GitHub")}
            </div>"""
        )
    )
    LocateControl().add_to(m)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    m.save(OUTPUT)
    print(f"Map with {len(current)} upcoming classes and {len(past)} past-only locations saved to {OUTPUT}")


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "beautifulsoup4>=4.12.0",
#     "requests>=2.31.0",
#     "tqdm>=4.66.1",
# ]
# ///
# uv run all_emt_classes.py
"""Brute-force crawl MFRI EMT (EMS-106) section pages, past and present.

MFRI section URLs look like https://www.mfri.org/course/msfs/EMS/106/S009/2027/
Invalid sections return HTTP 200 without a "Log Number:", so we check for that.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

COURSE = "EMS/106"
YEARS = range(2020, 2028)  # MFRI fiscal years
# MFRI ignores the letter prefix (S001, A001, R001 all resolve to section 001),
# so only the number matters; the real log number is read from the page.
SECTIONS = [f"S{n:03d}" for n in range(1, 121)]
OUTPUT = "mfri_emt_old_and_new_courses.json"
HEADERS = {"User-Agent": "MFRI EMT Course Data Collector (personal blog project)"}

session = requests.Session()
session.headers.update(HEADERS)


def to_mdy(s):
    try:
        return datetime.strptime(s.strip(), "%B %d, %Y").strftime("%m-%d-%Y")
    except (ValueError, AttributeError):
        return None


def parse(url, html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    text = main.get_text("\n", strip=True)
    m = re.search(r"Log Number:\s*(\S+)", text)
    # Some URLs redirect to other courses (e.g. PDI-277); keep only EMT sections
    if not m or not m.group(1).startswith(COURSE.replace("/", "-") + "-"):
        return None
    lines = text.split("\n")

    def after(label, n=1):
        for i, line in enumerate(lines):
            if line.startswith(label):
                rest = line[len(label):].strip()
                return rest if rest else (lines[i + n] if i + n < len(lines) else None)
        return None

    loc_idx = lines.index("Location:") if "Location:" in lines else None
    date_idx = lines.index("Date:") if "Date:" in lines else None
    loc_lines = lines[loc_idx + 1 : date_idx] if loc_idx is not None and date_idx else []
    hours = re.search(r"Instructional Hours:\s*([\d.]+)", text)
    office = re.search(r"Coordinated by: the MFRI (.+?) Office", " ".join(lines))
    email = re.search(r"[\w.]+@mfri\.org", text)
    reg = main.find("a", href=re.compile(r"/register/"))
    start, end = to_mdy(after("Start:")), to_mdy(after("End:"))
    return {
        "courseId": m.group(1),
        "courseUrl": url,
        "registerLink": reg["href"] if reg else None,
        "startDate": start,
        "endDate": end,
        "firstClassTime": f"{after('First Session Start Time:')} - {after('End Time:')}",
        "location": loc_lines[0] if loc_lines else None,
        "locationAddress": ", ".join(loc_lines[1:]) if len(loc_lines) > 1 else None,
        "instructionalHours": float(hours.group(1)) if hours else None,
        "coordinateBy": office.group(1).strip() if office else None,
        "contact": email.group(0) if email else None,
        "currentDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch(args):
    sec, year = args
    url = f"https://www.mfri.org/course/msfs/{COURSE}/{sec}/{year}/"
    for _ in range(3):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return parse(r.url, r.text)
        except requests.RequestException:
            pass
    return None


def main():
    jobs = [(s, y) for y in YEARS for s in SECTIONS]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(tqdm(ex.map(fetch, jobs), total=len(jobs)))
    # Different URLs can resolve to the same log number (e.g. S001 -> A001)
    courses = {c["courseId"]: c for c in results if c}
    out = sorted(courses.values(), key=lambda c: datetime.strptime(c["startDate"] or "01-01-1900", "%m-%d-%Y"))
    with open(OUTPUT, "w") as f:
        json.dump(out, f, indent=4)
    print(f"Saved {len(out)} EMT classes to {OUTPUT}")


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "beautifulsoup4>=4.12.0",
#     "requests>=2.31.0",
#     "tqdm>=4.66.1",
# ]
# ///
# uv run mfri_locations.py
"""Fresh pull of MFRI training locations from https://www.mfri.org/location/{id}.

Each page gives: name, county (region), serving MFRI office, and address.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

MAX_ID = 1600
ZIP_LINE = re.compile(r"\b[A-Z]{2}\s+\d{5}(-\d{4})?$")
OUTPUT = "mfri_locations.json"
HEADERS = {"User-Agent": "MFRI EMT Course Data Collector (personal blog project)"}

session = requests.Session()
session.headers.update(HEADERS)


def parse(url_id, html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    lines = main.get_text("\n", strip=True).split("\n")
    # Invalid IDs render an empty template whose first line is a label
    if "Address:" not in lines or "Served by:" not in lines or lines[0].endswith(":"):
        return None
    served_idx, addr_idx = lines.index("Served by:"), lines.index("Address:")
    # Address block ends at the "<City> <ST> <zip>" line; drop repeated name
    addr = []
    for line in lines[addr_idx + 1 : addr_idx + 8]:
        addr.append(line)
        if ZIP_LINE.search(line):
            break
    else:
        addr = addr[:1]
    if addr and addr[0] == lines[0]:
        addr = addr[1:]
    office = main.find("a", href=lambda h: h and h.startswith("/office/"))
    return {
        "url": f"https://www.mfri.org/location/{url_id}",
        "urlId": url_id,
        "location": lines[0],
        "county": lines[1] if served_idx > 1 else None,
        "servedBy": lines[served_idx + 1],
        "servedByUrl": f"https://www.mfri.org{office['href']}" if office else None,
        "address": ", ".join(addr),
    }


def fetch(url_id):
    for _ in range(3):
        try:
            r = session.get(f"https://www.mfri.org/location/{url_id}", timeout=30)
            if r.status_code == 200:
                return parse(url_id, r.text)
            return None
        except requests.RequestException:
            pass
    return None


def main():
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(tqdm(ex.map(fetch, range(MAX_ID)), total=MAX_ID))
    out = [r for r in results if r]
    with open(OUTPUT, "w") as f:
        json.dump(out, f, indent=4)
    print(f"Saved {len(out)} locations to {OUTPUT}")


if __name__ == "__main__":
    main()

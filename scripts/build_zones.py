#!/usr/bin/env python3
"""Build per-zone OBSERVED hourly demand fixtures from IESO's public zonal demand reports.

Input : data/ieso_zonal_{2021..2025}.csv   (IESO Hourly Zonal Demand Report, observed)
Output: public/data/zones.json             (index: pins, peaks, load factors)
        public/data/zones/{id}.json        (5 years of hourly MW, integers)
Missing hours are linearly interpolated and counted in `filledHours`.
Pin positions are a representative city per zone (approximate; IESO zones are transmission areas, not municipal boundaries).
"""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "data"; (OUT / "zones").mkdir(parents=True, exist_ok=True)
YEARS = [2021, 2022, 2023, 2024, 2025]
ZONES = {  # id: (display name, representative city, lat, lon)
    "northwest": ("Northwest", "Thunder Bay", 48.38, -89.25), "northeast": ("Northeast", "Sudbury", 46.49, -81.00),
    "ottawa": ("Ottawa", "Ottawa", 45.42, -75.70), "east": ("East", "Kingston", 44.23, -76.49),
    "toronto": ("Toronto", "Toronto", 43.65, -79.38), "essa": ("Essa", "Barrie", 44.39, -79.69),
    "bruce": ("Bruce", "Kincardine", 44.17, -81.63), "southwest": ("Southwest", "London", 42.98, -81.25),
    "niagara": ("Niagara", "St. Catharines", 43.16, -79.24), "west": ("West", "Windsor", 42.32, -83.04),
}
col = {"northwest": "Northwest", "northeast": "Northeast", "ottawa": "Ottawa", "east": "East", "toronto": "Toronto",
       "essa": "Essa", "bruce": "Bruce", "southwest": "Southwest", "niagara": "Niagara", "west": "West"}

def load(year):
    d = pd.read_csv(ROOT / "data" / f"ieso_zonal_{year}.csv", skiprows=3)
    d["Date"] = pd.to_datetime(d["Date"])
    return d

series = {z: {} for z in ZONES}; filled = {z: 0 for z in ZONES}
for y in YEARS:
    d = load(y)
    full = pd.MultiIndex.from_product([pd.date_range(f"{y}-01-01", f"{y}-12-31"), range(1, 25)], names=["Date", "Hour"])
    d = d.set_index(["Date", "Hour"]).reindex(full)
    for z in ZONES:
        s = d[col[z]].astype(float); n = int(s.isna().sum()); filled[z] += n
        series[z][y] = [int(round(v)) for v in s.interpolate(limit_direction="both").tolist()]

index = []
for z, (name, city, lat, lon) in ZONES.items():
    allv = np.array([v for y in YEARS for v in series[z][y]], dtype=float)
    per_year = {str(y): {"peak": int(max(series[z][y])), "mean": int(round(np.mean(series[z][y])))} for y in YEARS}
    (OUT / "zones" / f"{z}.json").write_text(json.dumps({"id": z, "name": name, "source": "IESO Hourly Zonal Demand Report (observed)",
        "unit": "MW", "hourEnding": "1..24 day-major from Jan 1", "years": {str(y): series[z][y] for y in YEARS}}, separators=(",", ":")))
    index.append({"id": z, "name": name, "city": city, "lat": lat, "lon": lon, "years": YEARS, "peakMW": int(allv.max()),
                  "meanMW": int(round(allv.mean())), "loadFactor": round(float(allv.mean() / allv.max()), 3),
                  "perYear": per_year, "filledHours": filled[z]})
(OUT / "zones.json").write_text(json.dumps({"provenance": "Observed (IESO hourly zonal demand)", "pinNote": "pin = representative city; IESO zones are transmission areas, not municipal boundaries", "zones": index}, separators=(",", ":")))
for r in index: print(f"{r['id']:10s} peak {r['peakMW']:6d} mean {r['meanMW']:6d} LF {r['loadFactor']:.2f} filled {r['filledHours']}")

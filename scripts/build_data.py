#!/usr/bin/env python3
"""Build the Waterloo World fixtures from IESO's 2026 KWCG IRRP data tables.

Input : data/kwcg_2026_irrp_tables.xlsx   (IESO, June 2026 — public)
Output: public/data/waterloo.json         (stations, forecasts, derived limits, provenance)
        public/data/profiles.json         (hourly load series for the stations IESO published, tenths of MW)

Run:  python3 scripts/build_data.py
Needs: openpyxl  (pip install -r scripts/requirements.txt)

What is real vs derived:
  * forecasts (Tables 1-17)            : IESO planning forecasts, copied as published (MW).
  * hourly profiles (Tables 18-35)     : IESO station load + capacity NEED, copied as published.
  * station limit ("capacityMW")       : DERIVED per season (summer May-Oct, winter Nov-Apr) = median(Load - Need) over hours where Need > 0.
                                         Validated: Need ~ max(0, Load - seasonal limit) within 0.5 MW; mismatches are counted.
Nothing here is a forecast of ours. Station positions are NOT in the data (UI lays them out).
"""
import json, re, statistics, sys
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "kwcg_2026_irrp_tables.xlsx"
OUT = ROOT / "public" / "data"
YEARS = list(range(2026, 2046))

FORECAST_TABLES = {  # table -> (kind, season, coincidence, case)
    6: ("load", "summer", "coincident", "reference"), 7: ("load", "summer", "non-coincident", "reference"),
    8: ("load", "winter", "coincident", "reference"), 9: ("load", "winter", "non-coincident", "reference"),
    10: ("load", "summer", "coincident", "high"), 11: ("load", "summer", "non-coincident", "high"),
    12: ("load", "winter", "coincident", "high"), 13: ("load", "winter", "non-coincident", "high"),
    14: ("load", "summer", "coincident", "low"), 15: ("load", "summer", "non-coincident", "low"),
    16: ("load", "winter", "coincident", "low"), 17: ("load", "winter", "non-coincident", "low"),
}
CDM_TABLES = {1: "summer", 2: "winter"}
PROFILE_TABLES = {  # table -> (station id, station label, year)  (year None = multi-year 2026-2045)
    18: ("kitchener-mts-6", "Kitchener MTS #6", None), 22: ("puslinch-ts", "Puslinch TS", None),
    26: ("rush-mts", "Waterloo Rush MTS", 2036), 27: ("rush-mts", "Waterloo Rush MTS", 2045),
    28: ("kitchener-mts-1", "Kitchener MTS #1", 2039), 29: ("kitchener-mts-1", "Kitchener MTS #1", 2045),
    30: ("kitchener-mts-4", "Kitchener MTS #4", 2040), 31: ("kitchener-mts-4", "Kitchener MTS #4", 2045),
    32: ("dxk-supply", "DxK supply (Detweiler-Kitchener)", 2034), 33: ("dxk-supply", "DxK supply (Detweiler-Kitchener)", 2045),
    34: ("kitchener-mts-7", "Kitchener MTS #7", 2041), 35: ("kitchener-mts-7", "Kitchener MTS #7", 2045),
}
KEEP_MULTI_YEARS = {2030, 2035, 2040, 2045}   # keeps the browser payload small


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def read_station_table(ws):
    """Generic 'Station | 2026 ... 2045' table -> {station: [values by YEARS]}."""
    rows, header = {}, None
    for r in ws.iter_rows(values_only=True):
        if r and r[0] == "Station":
            header = [int(y) for y in r[1:] if isinstance(y, (int, float))]
            continue
        if header and r and isinstance(r[0], str) and not r[0].startswith("Back to"):
            vals = [v for v in r[1:1 + len(header)]]
            if all(isinstance(v, (int, float)) for v in vals):
                rows[r[0].strip()] = {y: round(float(v), 2) for y, v in zip(header, vals)}
    return rows


def area_of(name):
    n = name.lower()
    if n.startswith("kitchener"): return "Kitchener"
    if n.startswith("waterloo"): return "Waterloo"
    if n.startswith(("galt", "preston")): return "Cambridge"      # Galt and Preston are Cambridge districts
    if n.startswith("elmira"): return "Woolwich"
    if n.startswith("fergus"): return "Centre Wellington"
    if n.startswith("puslinch"): return "Puslinch"
    return None                                                    # not asserted; UI decides layout


def read_profile(ws):
    out = []
    for r in ws.iter_rows(values_only=True):
        if r and all(isinstance(v, (int, float)) for v in r[:6]):
            y, m, d, he, load, need = r[:6]
            out.append((int(y), int(m), int(d), int(he), float(load), float(need)))
    return out


def main():
    if not SRC.exists():
        sys.exit(f"missing {SRC}; download KWCG-2026-IRRP-Data-Tables.xlsx from ieso.ca (see CLAUDE.md §4)")
    wb = openpyxl.load_workbook(SRC, data_only=True, read_only=True)
    checks = []

    # ---- forecasts -------------------------------------------------------------------
    stations = {}
    for t, (_, season, coinc, case) in FORECAST_TABLES.items():
        for name, series in read_station_table(wb[f"Table {t}"]).items():
            st = stations.setdefault(slug(name), {"id": slug(name), "name": name, "area": area_of(name), "forecast": {}, "cdm": {}})
            st["forecast"].setdefault(case, {}).setdefault(season, {})[coinc] = [series[y] for y in YEARS]
    for t, season in CDM_TABLES.items():
        for name, series in read_station_table(wb[f"Table {t}"]).items():
            sid = slug(name)
            if sid in stations:
                stations[sid]["cdm"][season] = [round(series[y], 2) for y in YEARS]
    checks.append(f"forecast stations: {len(stations)}")

    # ---- hourly profiles + derived limits --------------------------------------------
    profiles, limits = {}, {}
    for t, (sid, label, year) in PROFILE_TABLES.items():
        rows = read_profile(wb[f"Table {t}"])
        # limit derivation + validation over ALL rows of the table
        # Ratings are SEASONAL (verified in the data): summer May-Oct, winter Nov-Apr.
        season = lambda m: "summer" if 5 <= m <= 10 else "winter"
        lim_rows = {"summer": [], "winter": []}
        for (_, m, _, _, ld, nd) in rows:
            if nd > 0:
                lim_rows[season(m)].append(ld - nd)
        tab = {s: (statistics.median(v) if v else None) for s, v in lim_rows.items()}
        bad = sum(1 for (_, m, _, _, ld, nd) in rows
                  if tab[season(m)] is not None and abs(max(0.0, ld - tab[season(m)]) - nd) > 0.5)
        limits.setdefault(sid, []).append((tab, bad, len(rows)))
        # keep payload small
        by_year = {}
        for (y, m, d, he, ld, nd) in rows:
            if year is None and y not in KEEP_MULTI_YEARS:
                continue
            by_year.setdefault(year if year is not None else y, []).append(round(ld * 10))   # single-year tables: key by the table's year
        for y, vals in by_year.items():
            profiles.setdefault(sid, {"label": label, "unit": "tenths of MW", "hourEnding": "1..24, day-major, Jan 1 first", "years": {}})["years"][str(y)] = vals
    limit_out = {}
    for sid, L in limits.items():
        seasonal = {}
        for s in ("summer", "winter"):
            vals = [t[s] for t, _, _ in L if t[s] is not None]
            seasonal[s] = round(statistics.median(vals), 1) if vals else None   # None = season never overloads in the published profile
        limit_out[sid] = {"summerMW": seasonal["summer"], "winterMW": seasonal["winter"],
                          "rowsInconsistent": sum(b for _, b, _ in L), "rowsChecked": sum(n for _, _, n in L)}
        checks.append(f"limit {sid}: {limit_out[sid]}")
    for sid, p in profiles.items():
        p["limitMW"] = {k: limit_out.get(sid, {}).get(k) for k in ("summerMW", "winterMW")}
    # attach limits/profile availability to forecast stations where names match
    alias = {"kitchener-mts-6": "kitchener-mts-6", "kitchener-mts-1": "kitchener-mts-1", "kitchener-mts-4": "kitchener-mts-4",
             "kitchener-mts-7": "kitchener-mts-7", "rush-mts": "waterloo-rush-mts", "puslinch-ts": "puslinch-ds"}
    for pid, sid in alias.items():
        if sid in stations and pid in limit_out:
            stations[sid]["limit"] = {**limit_out[pid], "source": "derived: median(Load-Need) from IESO 8760 need profile"}
            stations[sid]["profileId"] = pid
        elif pid in limit_out:
            checks.append(f"WARN profile {pid} has no matching forecast station ({sid})")

    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": "Waterloo World fixtures", "region": "Kitchener-Waterloo-Cambridge-Guelph (KWCG), Ontario",
        "source": "IESO, KWCG Integrated Regional Resource Plan — Data Tables, June 2026 (report dated 08/07/2026)",
        "sourceUrl": "https://www.ieso.ca/-/media/Files/IESO/Document-Library/regional-planning/KWCG/KWCG-2026-IRRP-Data-Tables.xlsx",
        "years": YEARS, "units": "MW",
        "notes": ["Forecasts are IESO's planning forecasts, not ours.",
                  "Station limits are seasonal (summer May-Oct, winter Nov-Apr) and derived from IESO need profiles (Need ~ max(0, Load - limit)); a season that never overloads has no published limit (null).",
                  "Only the stations listed in profiles.json have hourly data; others have annual forecasts only.",
                  "Station map positions are not public data; the UI lays them out illustratively.",
                  "Planning-level model; not a utility connection approval."],
    }
    (OUT / "waterloo.json").write_text(json.dumps({"meta": meta, "stations": list(stations.values()), "limits": limit_out}, separators=(",", ":")))
    (OUT / "profiles.json").write_text(json.dumps(profiles, separators=(",", ":")))
    for c in checks: print(c)
    for f in ("waterloo.json", "profiles.json"):
        print(f"{f}: {(OUT / f).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()

"""Deterministic helpers. No Python hash() (salted per process) and no global RNG state: every draw is a pure
function of (seed, keys), so results never depend on call order."""
import hashlib
import math

import pandas as pd

LAT, LON, EST_MERIDIAN = 43.47, -80.52, -75.0   # Waterloo; fixed-EST meridian (IESO convention)


def uhash(*keys) -> float:
    h = hashlib.blake2b("|".join(map(str, keys)).encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") / 2**64


def to_est(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_localize("Etc/GMT+5") if t.tzinfo is None else t.tz_convert("Etc/GMT+5")


def hod(t: pd.Timestamp) -> float:
    return t.hour + t.minute / 60.0


def date_key(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%d")


def prev_date_key(t: pd.Timestamp) -> str:
    return (t - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def is_weekend(t: pd.Timestamp) -> bool:
    return t.dayofweek >= 5


def clear_sky_fraction(t: pd.Timestamp) -> float:
    """Clear-sky output as a fraction of installed capacity (simple solar geometry, Waterloo, fixed EST)."""
    doy = t.dayofyear
    decl = math.radians(23.44) * math.sin(2 * math.pi * (284 + doy) / 365)
    solar_noon = 12.0 + (-LON + EST_MERIDIAN) * 4 / 60.0          # ~12:22 EST
    ha = math.radians(15.0 * (hod(t) + 0.5 - solar_noon))          # mid-hour
    lat = math.radians(LAT)
    s = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    return max(0.0, s) ** 1.15 * 0.9

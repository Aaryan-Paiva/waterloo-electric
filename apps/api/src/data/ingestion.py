"""Build a world's historical dataset from a world pack (CLAUDE.md §10).

  python -m src.data.ingestion --world waterloo-demo          # writes data/processed/<world>_hourly.parquet + fixture
Deterministic: same raw files + same pack => byte-identical fixture.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .. import settings
from ..schemas.world import WorldPack
from .normalization import read_ieso_zonal

LEGACY_HOURS_PER_YEAR = 24


def load_world_pack(world_id: str) -> WorldPack:
    path = settings.WORLD_PACKS_DIR / f"{world_id.replace('-', '_')}.json"
    return WorldPack.model_validate_json(path.read_text())


def build_dataset(pack: WorldPack, raw_dir: Path | None = None) -> pd.DataFrame:
    """Concatenate yearly files, scale the shape to the pack's target peak, keep the unscaled value."""
    raw_dir = raw_dir or settings.RAW_DIR
    frames = [read_ieso_zonal(raw_dir / f, pack.historical_load.column) for f in pack.historical_load.raw_files]
    df = pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    if df["timestamp"].duplicated().any():
        raise ValueError("duplicate timestamps across yearly files")
    factor = pack.historical_load.scale.target_peak_mw / df["observed_mw"].max()
    df["load_mw"] = (df["observed_mw"] * factor).round(3)
    df["scale_factor"] = factor
    return df


def dataset_path(world_id: str) -> Path:
    return settings.PROCESSED_DIR / f"{world_id.replace('-', '_')}_hourly.parquet"


def write_dataset(pack: WorldPack, df: pd.DataFrame) -> Path:
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    p = dataset_path(pack.id)
    df.to_parquet(p, index=False)
    return p


def build_fixture(pack: WorldPack, df: pd.DataFrame) -> dict:
    """A small committed window (30 days) centred on the 2025 annual peak of the scaled series."""
    d25 = df[df["timestamp"].dt.year == 2025]
    peak_ts = d25.loc[d25["load_mw"].idxmax(), "timestamp"]
    start = (peak_ts.normalize() - pd.Timedelta(days=pack.fixture.days // 2))
    end = start + pd.Timedelta(days=pack.fixture.days)
    win = df[(df["timestamp"] >= start) & (df["timestamp"] < end)]
    points = [{"timestamp": t.isoformat(), "loadMw": float(l), "observedZoneMw": float(o), "qualityFlag": q}
              for t, l, o, q in zip(win["timestamp"], win["load_mw"], win["observed_mw"], win["quality_flag"])]
    body = {"worldId": pack.id, "datasetId": pack.historical_load.dataset_id, "hours": len(points),
            "start": start.isoformat(), "end": end.isoformat(), "anchorPeak": peak_ts.isoformat(),
            "scaleFactor": float(df["scale_factor"].iloc[0]),
            "note": "Committed deterministic fixture: observed IESO Southwest-zone shape, scaled to the demo zone (derived).",
            "points": points}
    body["sha256"] = hashlib.sha256(json.dumps(points, sort_keys=True).encode()).hexdigest()
    return body


def write_fixture(pack: WorldPack, body: dict) -> Path:
    settings.FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    p = settings.FIXTURES_DIR / pack.fixture.file
    p.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="waterloo-demo")
    a = ap.parse_args()
    pack = load_world_pack(a.world)
    df = build_dataset(pack)
    print(f"hours: {len(df)}  range: {df.timestamp.min()} -> {df.timestamp.max()}  interpolated: {(df.quality_flag != 'ok').sum()}")
    print(f"scaled peak: {df.load_mw.max():.3f} MW  scale factor: {df.scale_factor.iloc[0]:.6f}")
    print("parquet:", write_dataset(pack, df))
    print("fixture:", write_fixture(pack, build_fixture(pack, df)))


if __name__ == "__main__":
    main()

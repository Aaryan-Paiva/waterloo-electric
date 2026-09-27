import json

import pytest

from src import settings
from src.data import ingestion
from src.data.repositories import get_load, summarize

RAW_OK = all((settings.RAW_DIR / f"ieso_zonal_{y}.csv").exists() for y in range(2021, 2026))
needs_raw = pytest.mark.skipif(not RAW_OK, reason="raw IESO files not present")


@needs_raw
def test_full_dataset_shape_and_scaling():
    pack = ingestion.load_world_pack("waterloo-demo")
    df = ingestion.build_dataset(pack)
    assert len(df) == 43824                                   # 5 years incl. 2024 leap year
    assert df["timestamp"].is_monotonic_increasing and not df["timestamp"].duplicated().any()
    assert df["load_mw"].max() == pytest.approx(78.0, abs=1e-3)   # scaled to target peak
    assert (df["load_mw"] > 0).all()
    ratio = (df["load_mw"] / df["observed_mw"]).round(6)
    assert ratio.nunique() == 1                               # pure scaling, shape untouched


@needs_raw
def test_fixture_is_deterministic_and_committed_copy_matches():
    pack = ingestion.load_world_pack("waterloo-demo")
    df = ingestion.build_dataset(pack)
    a, b = ingestion.build_fixture(pack, df), ingestion.build_fixture(pack, df)
    assert a == b and a["hours"] == 720
    committed = json.loads((settings.FIXTURES_DIR / pack.fixture.file).read_text())
    assert committed["sha256"] == a["sha256"]                 # committed fixture == what the pipeline builds


def test_committed_fixture_is_self_consistent():
    pack = ingestion.load_world_pack("waterloo-demo")
    body = json.loads((settings.FIXTURES_DIR / pack.fixture.file).read_text())
    assert body["hours"] == 720 == len(body["points"])
    assert max(p["loadMw"] for p in body["points"]) <= pack.historical_load.scale.target_peak_mw + 1e-6


def test_summary_metrics_use_capacity():
    data = get_load("waterloo-demo")
    s = summarize(data.df, 90.0)
    assert s.peak_mw <= 78.0 + 1e-6
    assert s.headroom_at_peak_mw == pytest.approx(90.0 - s.peak_mw, abs=1e-3)
    assert s.hours_above_capacity == 0                        # baseline alone never exceeds 90 MW
    assert 0 < s.load_factor < 1

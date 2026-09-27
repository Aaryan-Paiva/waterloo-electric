import pandas as pd
import pytest

from src.data.normalization import MAX_GAP_HOURS, SOURCE_TZ, normalize_series, read_ieso_zonal

CSV = """\\\\Hourly Zonal Demand Report,,,
\\\\Created at 2026-01-01 00:00:00,,,
\\\\For 2025,,,
Date,Hour,Ontario Demand,Southwest
2025-01-01,1,100,10
2025-01-01,2,100,20
2025-01-01,3,100,30
2025-01-01,4,100,40
"""


def _write(tmp_path, body):
    p = tmp_path / "z.csv"
    p.write_text(body)
    return p


def test_hour_ending_maps_to_start_of_hour_fixed_est(tmp_path):
    df = read_ieso_zonal(_write(tmp_path, CSV), "Southwest")
    assert list(df["observed_mw"]) == [10, 20, 30, 40]
    assert df["timestamp"].iloc[0].isoformat() == "2025-01-01T00:00:00-05:00"  # HE1 -> 00:00 EST
    assert df["timestamp"].iloc[-1].isoformat() == "2025-01-01T03:00:00-05:00"
    assert str(df["timestamp"].dt.tz) == SOURCE_TZ


def test_missing_hour_is_interpolated_and_flagged(tmp_path):
    body = CSV.replace("2025-01-01,3,100,30\n", "")
    df = read_ieso_zonal(_write(tmp_path, body), "Southwest")
    assert len(df) == 4
    assert df.loc[2, "observed_mw"] == pytest.approx(30.0)   # halfway between 20 and 40
    assert list(df["quality_flag"]) == ["ok", "ok", "interpolated", "ok"]


def test_long_gap_is_refused():
    idx = pd.date_range("2025-01-01", periods=30, freq="h", tz=SOURCE_TZ)
    s = pd.Series(50.0, index=idx)
    s.iloc[5 : 5 + MAX_GAP_HOURS + 1] = float("nan")
    with pytest.raises(ValueError, match="gap"):
        normalize_series(s)


def test_non_positive_values_refused():
    idx = pd.date_range("2025-01-01", periods=3, freq="h", tz=SOURCE_TZ)
    with pytest.raises(ValueError, match="non-positive"):
        normalize_series(pd.Series([5.0, 0.0, 5.0], index=idx))


def test_unknown_column_refused(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        read_ieso_zonal(_write(tmp_path, CSV), "Nowhere")

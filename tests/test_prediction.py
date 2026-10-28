import pandas as pd
import pytest

from fouling.synthetic import make_synthetic_data
from fouling.validation import validate_data
from fouling.normalization import normalize_operating_data


def make_config():
    return {
        "normalization": {
            "reference_temperature_c": 25.0,
            "reference_ndp_bar": 20.0,
            "temperature_coefficient_per_c": 0.0239,
            "osmotic_pressure_bar_per_g_l": 0.75,
        },
        "forecast": {
            "minimum_rows": 14,
            "max_gap_hours": 48,
            "minimum_ndp_bar": 0.1,
        },
    }


def test_synthetic_data_passes_validation():
    cfg = make_config()
    df = make_synthetic_data(30, 1)

    checked = validate_data(df, cfg)
    out = normalize_operating_data(checked, cfg)

    assert len(out) == 30
    assert out["normalized_flow_ratio"].notna().all()


def test_missing_column_has_clear_error():
    cfg = make_config()
    df = pd.DataFrame({"timestamp": ["2025-01-01"]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_data(df, cfg)


def test_duplicate_timestamps_are_rejected():
    cfg = make_config()
    df = make_synthetic_data(30, 1)
    df.loc[1, "timestamp"] = df.loc[0, "timestamp"]

    with pytest.raises(ValueError, match="Duplicate timestamps"):
        validate_data(df, cfg)


def test_time_gap_over_limit_is_rejected():
    cfg = make_config()
    df = make_synthetic_data(30, 1)

    timestamps = pd.to_datetime(df["timestamp"], utc=True)
    timestamps.iloc[1:] = timestamps.iloc[1:] + pd.Timedelta(days=3)
    df["timestamp"] = timestamps

    with pytest.raises(ValueError, match="Time-series gap detected"):
        validate_data(df, cfg)


def test_temperature_outside_expected_range_is_rejected():
    cfg = make_config()
    df = make_synthetic_data(30, 1)
    df.loc[0, "feed_temperature_c"] = 250

    with pytest.raises(ValueError, match="Check units"):
        validate_data(df, cfg)


def test_non_numeric_flow_is_rejected():
    cfg = make_config()
    df = make_synthetic_data(30, 1)
    df["permeate_flow_m3_h"] = df["permeate_flow_m3_h"].astype(object)
    df.loc[0, "permeate_flow_m3_h"] = "invalid"

    with pytest.raises(ValueError, match="non-numeric"):
        validate_data(df, cfg)


def test_non_positive_permeate_flow_is_rejected():
    cfg = make_config()
    df = make_synthetic_data(30, 1)
    df.loc[0, "permeate_flow_m3_h"] = 0

    with pytest.raises(ValueError, match="greater than zero"):
        validate_data(df, cfg)

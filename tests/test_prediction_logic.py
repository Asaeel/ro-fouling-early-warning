import numpy as np
import pandas as pd
import pytest

from fouling.model import predict_dataframe


def make_config():
    return {
        "model": {"version": "0.1.0"},
        "normalization": {
            "reference_temperature_c": 25.0,
            "reference_ndp_bar": 20.0,
            "temperature_coefficient_per_c": 0.0239,
            "osmotic_pressure_bar_per_g_l": 0.75,
            "assume_permeate_osmotic_pressure_negligible": True,
        },
        "forecast": {
            "threshold_flow_ratio": 0.90,
            "horizon_days": 14,
            "minimum_rows": 14,
            "max_gap_hours": 48,
            "minimum_ndp_bar": 0.1,
            "minimum_feed_pressure_bar": 0.0,
        },
    }


def test_threshold_status_when_current_flow_is_below_threshold(monkeypatch, tmp_path):
    import fouling.model as model_module

    n = 20
    norm = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC"),
        "normalized_flow_ratio": np.linspace(0.95, 0.85, n),
        "feed_temperature_c": [25.0] * n,
        "feed_tds_mg_l": [1000.0] * n,
        "net_driving_pressure_bar": [20.0] * n,
    })

    monkeypatch.setattr(model_module, "validate_data", lambda df, cfg: df)
    monkeypatch.setattr(model_module, "normalize_operating_data", lambda df, cfg: norm)

    artifact_path = tmp_path / "artifact.joblib"
    import joblib
    joblib.dump({
        "model": None,
        "selected_model": "persistence_baseline",
        "metadata": {"model_version": "0.1.0", "data_type": "synthetic_only"},
    }, artifact_path)

    result = predict_dataframe(pd.DataFrame({"placeholder": [1]}), make_config(), artifact_path)

    assert result["status"] == "threshold_reached"
    assert result["estimated_days_until_cleaning"] == 0.0
    assert result["current_normalized_flow_ratio"] <= result["threshold_flow_ratio"]


def test_non_declining_trend_does_not_estimate_cleaning_time(monkeypatch, tmp_path):
    import fouling.model as model_module
    import joblib

    n = 20
    norm = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC"),
        "normalized_flow_ratio": np.linspace(0.92, 0.95, n),
        "feed_temperature_c": [25.0] * n,
        "feed_tds_mg_l": [1000.0] * n,
        "net_driving_pressure_bar": [20.0] * n,
    })

    monkeypatch.setattr(model_module, "validate_data", lambda df, cfg: df)
    monkeypatch.setattr(model_module, "normalize_operating_data", lambda df, cfg: norm)

    artifact_path = tmp_path / "artifact.joblib"
    joblib.dump({
        "model": None,
        "selected_model": "persistence_baseline",
        "metadata": {"model_version": "0.1.0", "data_type": "synthetic_only"},
    }, artifact_path)

    result = predict_dataframe(pd.DataFrame({"placeholder": [1]}), make_config(), artifact_path)

    assert result["status"] == "no_declining_trend_detected"
    assert result["estimated_days_until_cleaning"] is None

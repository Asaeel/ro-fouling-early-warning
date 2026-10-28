import pandas as pd
from fouling.synthetic import make_synthetic_data
from fouling.validation import validate_data
from fouling.normalization import normalize_operating_data

def test_synthetic_data_passes_validation():
    cfg = {"normalization":{"reference_temperature_c":25.0,"reference_ndp_bar":20.0,
        "temperature_coefficient_per_c":0.0239,"osmotic_pressure_bar_per_g_l":0.75},
        "forecast":{"minimum_rows":14,"max_gap_hours":48,"minimum_ndp_bar":0.1}}
    df = make_synthetic_data(30,1)
    checked = validate_data(df,cfg)
    out = normalize_operating_data(checked,cfg)
    assert len(out) == 30
    assert out["normalized_flow_ratio"].notna().all()

def test_missing_column_has_clear_error():
    from fouling.validation import validate_data
    import pytest
    cfg = {"normalization":{"osmotic_pressure_bar_per_g_l":0.75},
        "forecast":{"minimum_rows":1,"max_gap_hours":48,"minimum_ndp_bar":0.1}}
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_data(pd.DataFrame({"timestamp":["2025-01-01"]}),cfg)

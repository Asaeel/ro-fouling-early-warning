from __future__ import annotations
import pandas as pd

REQUIRED_COLUMNS = [
    "timestamp", "feed_temperature_c", "feed_pressure_bar",
    "concentrate_pressure_bar", "permeate_pressure_bar",
    "feed_tds_mg_l", "permeate_flow_m3_h"
]

def validate_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("Input CSV contains no data rows.")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    out = df.copy()
    try:
        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="raise", utc=True)
    except Exception as exc:
        raise ValueError("Column 'timestamp' must contain valid date/time values (ISO 8601 recommended).") from exc
    if out["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps found. Provide one row per timestamp.")
    out = out.sort_values("timestamp").reset_index(drop=True)
    numeric = [c for c in REQUIRED_COLUMNS if c != "timestamp"]
    for col in numeric:
        out[col] = pd.to_numeric(out[col], errors="coerce")
        if out[col].isna().any():
            raise ValueError(f"Column '{col}' contains missing or non-numeric values.")
        if not (out[col].map(lambda x: float('-inf') < x < float('inf'))).all():
            raise ValueError(f"Column '{col}' contains infinite values.")
    if (out["feed_temperature_c"] < -2).any() or (out["feed_temperature_c"] > 60).any():
        raise ValueError("feed_temperature_c must be in degrees Celsius (expected range -2 to 60). Check units.")
    for col in ["feed_pressure_bar", "concentrate_pressure_bar", "permeate_pressure_bar"]:
        if (out[col] < 0).any() or (out[col] > 150).any():
            raise ValueError(f"{col} must be in bar (expected range 0 to 150). Check units.")
    if (out["feed_tds_mg_l"] < 0).any() or (out["feed_tds_mg_l"] > 100000).any():
        raise ValueError("feed_tds_mg_l must be in mg/L (expected range 0 to 100000). Check units.")
    if (out["permeate_flow_m3_h"] <= 0).any():
        raise ValueError("permeate_flow_m3_h must be greater than zero and expressed in m^3/h.")
    ndp = ((out["feed_pressure_bar"] + out["concentrate_pressure_bar"]) / 2
           - out["permeate_pressure_bar"]
           - out["feed_tds_mg_l"] / 1000 * config["normalization"]["osmotic_pressure_bar_per_g_l"])
    if (ndp <= config["forecast"]["minimum_ndp_bar"]).any():
        raise ValueError("Calculated net driving pressure is non-positive or too small; check pressure/TDS units and values.")
    if len(out) >= 2:
        deltas = out["timestamp"].diff().dropna().dt.total_seconds() / 3600
        max_gap = float(config["forecast"]["max_gap_hours"])
        if (deltas > max_gap).any():
            worst = deltas.max()
            raise ValueError(f"Time-series gap detected ({worst:.1f} hours; configured maximum is {max_gap:g} hours). Resample or document gaps before prediction.")
    if len(out) < int(config["forecast"]["minimum_rows"]):
        raise ValueError(f"Need at least {config['forecast']['minimum_rows']} rows; received {len(out)}.")
    return out

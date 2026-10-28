from __future__ import annotations
import numpy as np
import pandas as pd

def normalize_operating_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Approximate normalized permeate flow using temperature and net-driving-pressure correction.

    This is a transparent prototype approximation, not a vendor ASTM D4516 implementation.
    Site use requires membrane-specific TCF/osmotic-pressure equations and validation.
    """
    out = df.copy()
    ncfg = config["normalization"]
    t_ref = float(ncfg["reference_temperature_c"])
    ndp_ref = float(ncfg["reference_ndp_bar"])
    beta = float(ncfg["temperature_coefficient_per_c"])
    osmotic_coeff = float(ncfg["osmotic_pressure_bar_per_g_l"])
    temp_correction = np.exp(beta * (out["feed_temperature_c"] - t_ref))
    feed_osmotic_bar = (out["feed_tds_mg_l"] / 1000.0) * osmotic_coeff
    ndp_actual = ((out["feed_pressure_bar"] + out["concentrate_pressure_bar"]) / 2.0
                  - out["permeate_pressure_bar"] - feed_osmotic_bar)
    if (ndp_actual <= 0).any():
        raise ValueError("Cannot normalize: calculated net driving pressure must be positive.")
    # Q_ref = Q_measured / TCF * (NDP_ref / NDP_actual)
    out["temperature_correction_factor"] = temp_correction
    out["estimated_feed_osmotic_pressure_bar"] = feed_osmotic_bar
    out["net_driving_pressure_bar"] = ndp_actual
    out["normalized_permeate_flow_m3_h"] = (
        out["permeate_flow_m3_h"] / temp_correction * (ndp_ref / ndp_actual)
    )
    baseline = float(out["normalized_permeate_flow_m3_h"].iloc[0])
    if baseline <= 0:
        raise ValueError("Normalized flow baseline must be positive.")
    out["normalized_flow_ratio"] = out["normalized_permeate_flow_m3_h"] / baseline
    out["normalized_flow_pct_of_baseline"] = 100.0 * out["normalized_flow_ratio"]
    return out

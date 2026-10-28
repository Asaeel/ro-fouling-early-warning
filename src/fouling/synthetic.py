from __future__ import annotations
import numpy as np
import pandas as pd

def make_synthetic_data(n_days: int = 240, seed: int = 42) -> pd.DataFrame:
    """Create explicitly synthetic daily RO operating data with gradual fouling and two cleanings."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2025-01-01", periods=n_days, freq="D", tz="UTC")
    temp = 24 + 3*np.sin(np.arange(n_days)*2*np.pi/90) + rng.normal(0, .4, n_days)
    feed_p = 55 + rng.normal(0, 1.0, n_days)
    conc_p = feed_p - 1.3 - np.arange(n_days)*0.001
    perm_p = 1.0 + rng.normal(0, .08, n_days)
    tds = 35000 + 1200*np.sin(np.arange(n_days)*2*np.pi/60) + rng.normal(0, 150, n_days)
    # A slowly declining intrinsic membrane performance, with cleaning resets.
    degradation = np.zeros(n_days)
    state = 0.0
    for i in range(n_days):
        if i in (80, 165):
            state = 0.015  # incomplete restoration after cleaning
        state += 0.00075 + max(0, tds[i]-35000)*1e-9
        degradation[i] = min(state, .35)
    tcf = np.exp(.0239*(temp-25))
    ndp = (feed_p + conc_p)/2 - perm_p - (tds/1000)*.75
    # Flow reflects TCF, NDP and fouling. Normalization should recover the trend approximately.
    clean_flow_ref = 8.0
    flow = clean_flow_ref * tcf * (ndp/20.0) * (1-degradation) * (1+rng.normal(0, .006, n_days))
    return pd.DataFrame({
        "timestamp": ts.astype(str),
        "feed_temperature_c": temp,
        "feed_pressure_bar": feed_p,
        "concentrate_pressure_bar": conc_p,
        "permeate_pressure_bar": perm_p,
        "feed_tds_mg_l": tds,
        "permeate_flow_m3_h": flow,
        "feed_flow_m3_h": 30 + rng.normal(0, .4, n_days),
        "concentrate_flow_m3_h": 22 + rng.normal(0, .4, n_days),
        "stage_dp_bar": feed_p-conc_p
    })

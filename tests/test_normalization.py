import numpy as np
import pandas as pd
from fouling.normalization import normalize_operating_data

def test_normalization_recovers_reference_flow():
    cfg = {"normalization": {"reference_temperature_c":25.0, "reference_ndp_bar":20.0,
        "temperature_coefficient_per_c":0.0239, "osmotic_pressure_bar_per_g_l":0.75}}
    temp = np.array([20.0, 25.0, 30.0])
    tcf = np.exp(.0239*(temp-25))
    ndp = np.array([18.0,20.0,22.0])
    q = 8.0*tcf*(ndp/20.0)
    df = pd.DataFrame({"feed_temperature_c":temp,"feed_pressure_bar":ndp,
        "concentrate_pressure_bar":ndp,"permeate_pressure_bar":0.0,
        "feed_tds_mg_l":0.0,"permeate_flow_m3_h":q})
    out = normalize_operating_data(df,cfg)
    assert np.allclose(out["normalized_permeate_flow_m3_h"],8.0)

def test_normalized_ratio_starts_at_one():
    cfg = {"normalization": {"reference_temperature_c":25.0, "reference_ndp_bar":20.0,
        "temperature_coefficient_per_c":0.0239, "osmotic_pressure_bar_per_g_l":0.75}}
    df = pd.DataFrame({"feed_temperature_c":[25,25],"feed_pressure_bar":[21,21],
        "concentrate_pressure_bar":[21,21],"permeate_pressure_bar":[0,0],
        "feed_tds_mg_l":[0,0],"permeate_flow_m3_h":[8,7]})
    out = normalize_operating_data(df,cfg)
    assert out["normalized_flow_ratio"].iloc[0] == 1.0
    assert out["normalized_flow_ratio"].iloc[1] < 1.0


def test_seawater_tds_gives_plausible_first_order_osmotic_pressure():
    cfg = {"normalization": {"reference_temperature_c":25.0, "reference_ndp_bar":20.0,
        "temperature_coefficient_per_c":0.0239, "osmotic_pressure_bar_per_g_l":0.75}}
    df = pd.DataFrame({"feed_temperature_c":[25.0], "feed_pressure_bar":[55.0],
        "concentrate_pressure_bar":[53.7], "permeate_pressure_bar":[1.0],
        "feed_tds_mg_l":[35000.0], "permeate_flow_m3_h":[20.0]})
    out = normalize_operating_data(df, cfg)
    assert 20.0 <= out["estimated_feed_osmotic_pressure_bar"].iloc[0] <= 30.0
    assert out["net_driving_pressure_bar"].iloc[0] > 0

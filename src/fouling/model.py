from __future__ import annotations
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.linear_model import LinearRegression
from .normalization import normalize_operating_data
from .validation import validate_data
from .synthetic import make_synthetic_data

FEATURES = ["flow_lag_0", "flow_lag_1", "flow_lag_3", "flow_lag_7",
            "rolling_mean_7", "rolling_slope_7", "temperature_c", "tds_g_l", "ndp_bar"]

def _features(norm: pd.DataFrame) -> pd.DataFrame:
    y = norm["normalized_flow_ratio"].astype(float).reset_index(drop=True)
    f = pd.DataFrame(index=norm.index)
    f["flow_lag_0"] = y
    f["flow_lag_1"] = y.shift(1)
    f["flow_lag_3"] = y.shift(3)
    f["flow_lag_7"] = y.shift(7)
    f["rolling_mean_7"] = y.shift(1).rolling(7).mean()
    f["rolling_slope_7"] = y.shift(1).rolling(7).apply(
        lambda a: np.polyfit(np.arange(len(a)), a, 1)[0], raw=True)
    f["temperature_c"] = norm["feed_temperature_c"].to_numpy()
    f["tds_g_l"] = norm["feed_tds_mg_l"].to_numpy()/1000
    f["ndp_bar"] = norm["net_driving_pressure_bar"].to_numpy()
    return f

def train_model(config: dict, artifact_path: str | Path) -> dict:
    # Demonstration model trained on synthetic data; replace with verified real data when available.
    raw = make_synthetic_data(n_days=300, seed=int(config["model"]["random_state"]))
    clean = validate_data(raw, config)
    norm = normalize_operating_data(clean, config)
    X = _features(norm)
    y = norm["normalized_flow_ratio"].shift(-7).rename("target_7d")
    data = X.join(y).dropna().reset_index(drop=True)
    # Time-aware split: first 70% train, next 15% validation, final 15% test.
    n = len(data); i1 = int(n*.70); i2 = int(n*.85)
    train, val, test = data.iloc[:i1], data.iloc[i1:i2], data.iloc[i2:]
    model = RandomForestRegressor(n_estimators=250, min_samples_leaf=3,
                                  random_state=int(config["model"]["random_state"]),
                                  n_jobs=-1)
    model.fit(train[FEATURES], train["target_7d"])
    # Select the Random Forest or persistence baseline using validation data only.
    val_pred = model.predict(val[FEATURES])
    val_baseline = val["flow_lag_0"].to_numpy()
    rf_val_mae = float(mean_absolute_error(val["target_7d"], val_pred))
    baseline_val_mae = float(mean_absolute_error(val["target_7d"], val_baseline))
    selected_model = "random_forest" if rf_val_mae < baseline_val_mae else "persistence_baseline"
    # Baseline: next-week normalized flow equals current normalized flow.
    baseline = test["flow_lag_0"].to_numpy()
    pred = model.predict(test[FEATURES]) if selected_model == "random_forest" else baseline
    result = {
        "model_version": config["model"]["version"],
        "data_type": "synthetic_only",
        "selected_model": selected_model,
        "validation_random_forest_mae_7d": rf_val_mae,
        "validation_baseline_mae_7d": baseline_val_mae,
        "n_rows": int(len(data)),
        "train_rows": int(len(train)),
        "validation_rows": int(len(val)),
        "test_rows": int(len(test)),
        "model_mae_7d": float(mean_absolute_error(test["target_7d"], pred)),
        "baseline_mae_7d": float(mean_absolute_error(test["target_7d"], baseline)),
        "model_rmse_7d": float(root_mean_squared_error(test["target_7d"], pred)),
        "warning": "Metrics are synthetic demonstration metrics, not evidence of real-plant performance. Model selection used validation data only."
    }
    artifact = {
        "model": model, "selected_model": selected_model, "features": FEATURES, "config": config,
        "metadata": result
    }
    Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_path)
    return result

def predict_dataframe(df: pd.DataFrame, config: dict, artifact_path: str | Path) -> dict:
    checked = validate_data(df, config)
    norm = normalize_operating_data(checked, config)
    artifact = joblib.load(artifact_path)
    model = artifact["model"]
    features = _features(norm)
    if features.iloc[-1].isna().any():
        raise ValueError("Not enough history to construct lag features; provide at least 8 consecutive observations.")
    # Forecast 7 days ahead at the latest observed state.
    if artifact.get("selected_model", "random_forest") == "persistence_baseline":
        forecast_7d = float(features["flow_lag_0"].iloc[-1])
    else:
        forecast_7d = float(model.predict(features.iloc[[-1]][FEATURES])[0])
    threshold = float(config["forecast"]["threshold_flow_ratio"])
    current = float(norm["normalized_flow_ratio"].iloc[-1])
    # Estimate days-to-threshold from robust recent linear slope. This is an extrapolation, not a guaranteed cleaning date.
    recent = norm["normalized_flow_ratio"].tail(min(14, len(norm))).to_numpy()
    x = np.arange(len(recent), dtype=float).reshape(-1, 1)
    slope = float(LinearRegression().fit(x, recent).coef_[0]) if len(recent) >= 2 else 0.0
    if current <= threshold:
        days_remaining = 0.0
        status = "threshold_reached"
    elif slope >= -1e-6:
        days_remaining = None
        status = "no_declining_trend_detected"
    else:
        days_remaining = max(0.0, (threshold-current)/slope)
        status = "estimated"
    horizon = int(config["forecast"]["horizon_days"])
    forecast_days = list(range(1, horizon+1))
    # Transparent local linear trend path for threshold crossing; ML forecast is separately reported.
    forecast_path = [max(0.0, current+slope*d) for d in forecast_days]
    crossed = next((d for d,v in zip(forecast_days, forecast_path) if v <= threshold), None)
    return {
        "model_version": artifact["metadata"]["model_version"],
        "selected_model": artifact.get("selected_model", "random_forest"),
        "data_type": artifact["metadata"]["data_type"],
        "latest_timestamp": str(norm["timestamp"].iloc[-1]),
        "current_normalized_flow_ratio": current,
        "current_normalized_flow_pct": current*100,
        "predicted_normalized_flow_ratio_7d": forecast_7d,
        "predicted_normalized_flow_pct_7d": forecast_7d*100,
        "trend_projected_normalized_flow_ratio_7d": forecast_path[min(6, len(forecast_path)-1)] if forecast_path else current,
        "trend_projected_normalized_flow_pct_7d": (forecast_path[min(6, len(forecast_path)-1)] if forecast_path else current)*100,
        "threshold_flow_ratio": threshold,
        "estimated_days_until_cleaning": days_remaining,
        "days_until_threshold_within_horizon": crossed,
        "status": status,
        "recent_daily_slope": slope,
        "trend_projection": [{"days_ahead": d, "normalized_flow_ratio": v, "normalized_flow_pct": v*100}
                             for d,v in zip(forecast_days, forecast_path)],
        "normalized_data": norm.replace({np.nan: None}).to_dict(orient="records"),
        "limitations": [
            "Osmotic pressure is estimated with a first-order TDS coefficient (0.75 bar per g/L); it is not a membrane/vendor-specific normalization and must be validated.",
            "Model artefact was trained on synthetic data only; predictions are a software demonstration, not validated plant advice.",
            "Cleaning time is a local trend extrapolation; sudden operating changes can invalidate it."
        ]
    }

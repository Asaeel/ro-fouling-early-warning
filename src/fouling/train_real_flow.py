from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


ROOT = Path.cwd()
SOURCE = ROOT / "data" / "MBR_RO_AIOT_daily_flow_540d.xlsx"
ARTIFACT = ROOT / "artifacts" / "real_station_flow_model.joblib"
METRICS = ROOT / "data" / "real_station_model_metrics.json"
PREDICTIONS = ROOT / "data" / "real_station_test_predictions.csv"

HORIZON_DAYS = 7
RANDOM_STATE = 42


def calculate_metrics(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
    }


def load_data():
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Source Excel file was not found: {SOURCE}"
        )

    df = pd.read_excel(SOURCE, sheet_name="Sheet1", header=1)

    required_columns = [
        "Date",
        "IW (m3)",
        "MBR product (m3/day)",
        "RO product (m3/day)",
        "Phase",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required Excel columns: {missing_columns}. "
            f"Available columns: {list(df.columns)}"
        )

    df = df[required_columns].copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    numeric_columns = [
        "IW (m3)",
        "MBR product (m3/day)",
        "RO product (m3/day)",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["Phase"] = df["Phase"].astype("string").str.strip()

    df = df.dropna(
        subset=["Date", *numeric_columns, "Phase"]
    )

    df = df.sort_values("Date").reset_index(drop=True)

    if df.empty:
        raise ValueError("No valid observations remain after cleaning.")

    if df["Date"].duplicated().any():
        duplicates = int(df["Date"].duplicated().sum())
        raise ValueError(
            f"Found {duplicates} duplicate dates. "
            "Resolve duplicate daily records before training."
        )

    if (df[numeric_columns] < 0).any().any():
        raise ValueError(
            "Negative flow values were found. "
            "Check the source data before training."
        )

    if len(df) < 100:
        raise ValueError(
            f"Only {len(df)} valid observations were found; "
            "at least 100 are required."
        )

    # Report missing calendar dates without fabricating observations.
    expected_dates = pd.date_range(
        start=df["Date"].min(),
        end=df["Date"].max(),
        freq="D",
    )

    missing_dates = expected_dates.difference(
        pd.DatetimeIndex(df["Date"])
    )

    return df, {
        "observations": int(len(df)),
        "start_date": df["Date"].min().strftime("%Y-%m-%d"),
        "end_date": df["Date"].max().strftime("%Y-%m-%d"),
        "missing_calendar_dates": int(len(missing_dates)),
        "phase_counts": {
            str(key): int(value)
            for key, value in df["Phase"].value_counts().items()
        },
        "zero_ro_flow_days": int(
            (df["RO product (m3/day)"] == 0).sum()
        ),
    }


def build_dataset(df):
    ro = df["RO product (m3/day)"]
    mbr = df["MBR product (m3/day)"]
    iw = df["IW (m3)"]

    phase_codes = {
        "Commissioning": 0,
        "Handover": 1,
        "Recommissioning": 2,
    }

    features = pd.DataFrame(index=df.index)

    features["day_number"] = np.arange(len(df), dtype=float)
    features["ro_today"] = ro
    features["ro_lag_1"] = ro.shift(1)
    features["ro_lag_3"] = ro.shift(3)
    features["ro_lag_7"] = ro.shift(7)
    features["ro_mean_7d"] = ro.rolling(7).mean()
    features["ro_mean_14d"] = ro.rolling(14).mean()
    features["ro_zero_days_7d"] = (
        (ro == 0).astype(float).rolling(7).sum()
    )

    features["mbr_today"] = mbr
    features["mbr_lag_1"] = mbr.shift(1)
    features["mbr_mean_7d"] = mbr.rolling(7).mean()
    features["iw_today"] = iw
    features["iw_mean_7d"] = iw.rolling(7).mean()

    features["phase_code"] = (
        df["Phase"]
        .map(phase_codes)
        .fillna(-1)
        .astype(float)
    )

    target = ro.shift(-HORIZON_DAYS).rename("target_ro")

    dataset = features.join(target).dropna().copy()
    dataset["forecast_date"] = df.loc[dataset.index, "Date"]
    dataset["target_date"] = df.loc[
        dataset.index + HORIZON_DAYS, "Date"
    ].to_numpy()

    return dataset.reset_index(drop=True), list(features.columns)


def main():
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)

    df, data_summary = load_data()
    dataset, feature_columns = build_dataset(df)

    n = len(dataset)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    # Leave a horizon-sized gap between each chronological split.
    train = dataset.iloc[:train_end].copy()
    validation = dataset.iloc[
        train_end + HORIZON_DAYS:val_end
    ].copy()
    test = dataset.iloc[val_end + HORIZON_DAYS:].copy()

    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError(
            "Not enough rows for chronological train/validation/test "
            "splits. Reduce the split gaps or check the source data."
        )

    X_train = train[feature_columns]
    y_train = train["target_ro"]

    X_val = validation[feature_columns]
    y_val = validation["target_ro"]

    X_test = test[feature_columns]
    y_test = test["target_ro"]

    model = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=4,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    # Baseline: use today's RO flow as the forecast for the target date.
    val_persistence = validation["ro_today"].to_numpy()
    test_persistence = test["ro_today"].to_numpy()

    val_rf = model.predict(X_val)
    test_rf = model.predict(X_test)

    validation_scores = {
        "random_forest": calculate_metrics(y_val, val_rf),
        "persistence_baseline": calculate_metrics(
            y_val, val_persistence
        ),
    }

    # Select only between models implemented in this training artifact.
    selected_model = (
        "random_forest"
        if validation_scores["random_forest"]["mae"]
        < validation_scores["persistence_baseline"]["mae"]
        else "persistence_baseline"
    )

    selected_predictions = (
        test_rf
        if selected_model == "random_forest"
        else test_persistence
    )

    test_scores = {
        "selected_model": calculate_metrics(
            y_test, selected_predictions
        ),
        "random_forest": calculate_metrics(y_test, test_rf),
        "persistence_baseline": calculate_metrics(
            y_test, test_persistence
        ),
    }

    artifact = {
        "model": model,
        "selected_model": selected_model,
        "feature_columns": feature_columns,
        "horizon_days": HORIZON_DAYS,
        "baseline": "persistence_baseline",
        "target_column": "RO product (m3/day)",
        "training_end_date": train["target_date"].max().strftime(
            "%Y-%m-%d"
        ),
        "validation_metrics": validation_scores,
        "notes": (
            "Flow-only forecasting is not proof of membrane fouling. "
            "Zero flow and phase changes may reflect stoppages, "
            "commissioning, or operational changes."
        ),
    }

    joblib.dump(artifact, ARTIFACT)

    predictions = test[
        ["forecast_date", "target_date"]
    ].copy()

    predictions["actual_ro"] = y_test.to_numpy()
    predictions["predicted_ro"] = selected_predictions
    predictions["random_forest_prediction"] = test_rf
    predictions["persistence_prediction"] = test_persistence
    predictions["selected_model"] = selected_model

    predictions.to_csv(PREDICTIONS, index=False)

    results = {
        "data": data_summary,
        "horizon_days": HORIZON_DAYS,
        "split_sizes": {
            "train": int(len(train)),
            "validation": int(len(validation)),
            "test": int(len(test)),
        },
        "validation_metrics": validation_scores,
        "test_metrics": test_scores,
        "selected_model": selected_model,
        "artifact_path": str(ARTIFACT.relative_to(ROOT)),
        "predictions_path": str(PREDICTIONS.relative_to(ROOT)),
        "interpretation": (
            "The model forecasts RO production flow only. "
            "It does not independently diagnose fouling or determine "
            "whether chemical cleaning is required."
        ),
    }

    METRICS.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Real Station Flow Model ===")
    print(f"Observations: {data_summary['observations']}")
    print(f"Date range: {data_summary['start_date']} to "
          f"{data_summary['end_date']}")
    print(f"Missing calendar dates: "
          f"{data_summary['missing_calendar_dates']}")
    print(f"Zero RO flow days: {data_summary['zero_ro_flow_days']}")
    print(f"Train/validation/test: "
          f"{len(train)}/{len(validation)}/{len(test)}")
    print("\nValidation metrics:")
    print(json.dumps(validation_scores, indent=2))
    print(f"\nSelected model: {selected_model}")
    print("\nTest metrics:")
    print(json.dumps(test_scores, indent=2))
    print(f"\nSaved artifact: {ARTIFACT}")
    print(f"Saved metrics: {METRICS}")
    print(f"Saved predictions: {PREDICTIONS}")


if __name__ == "__main__":
    main()

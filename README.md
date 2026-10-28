# RO Membrane Fouling Early-Warning Model

Prototype software for normalizing RO operating data, forecasting a 7-day normalized-flow indicator, and estimating time to a configurable cleaning threshold.

> **Important limitation:** This repository contains two separate workflows: a synthetic-data forecasting prototype and a real-station RO production-flow analysis. The synthetic model is not trained on plant data. The real-station workflow forecasts RO production flow and flags low-flow patterns; it does not independently diagnose membrane fouling or determine chemical-cleaning requirements. Neither workflow is validated for operational maintenance decisions.

## Requirements
- Python 3.10+
- Docker (optional)

## Quick start (Mac Terminal)
```bash
cd ro-fouling-early-warning
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
fouling train
pytest
```

## Run API
```bash
uvicorn fouling.api:app --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/docs`. Upload a CSV to `POST /predict`.

## CLI prediction
```bash
fouling predict data/sample_input.csv
```
JSON output includes normalized data, the 7-day prediction, a 14-day trend projection, threshold status, estimated days to threshold, and limitations.

## Input CSV format
Required columns (exact names and units):
- `timestamp`: ISO date/time; one row per observation.
- `feed_temperature_c`: °C.
- `feed_pressure_bar`: bar.
- `concentrate_pressure_bar`: bar.
- `permeate_pressure_bar`: bar.
- `feed_tds_mg_l`: mg/L.
- `permeate_flow_m3_h`: m³/h.

Optional columns are retained but not currently used in prediction, e.g. `feed_flow_m3_h`, `concentrate_flow_m3_h`, `stage_dp_bar`.

Input must contain at least 14 rows, timestamps must be unique, and gaps must not exceed the configured 48 hours. The maximum gap and minimum row count are configurable in `config.yaml`. Data are sorted by timestamp after duplicate detection. Wrong-looking units and nonphysical calculated NDP trigger clear errors. The expected units are enforced partly through plausible-range checks; units cannot always be inferred reliably from numbers alone.

## Configuration
Edit `config.yaml`:
- `normalization.reference_temperature_c`: reference temperature.
- `normalization.reference_ndp_bar`: reference net driving pressure.
- `normalization.temperature_coefficient_per_c`: simplified temperature coefficient.
- `normalization.osmotic_pressure_bar_per_g_l`: first-order osmotic-pressure coefficient; 0.75 bar per g/L is a rough seawater approximation, not a validated membrane equation.
- `forecast.threshold_flow_ratio`: cleaning threshold; 0.90 means 10% below the first normalized value.
- `forecast.horizon_days`: displayed forecast horizon.
- `model.artifact_path`: saved model path.

Retrain after changing training-related settings:
```bash
fouling train
```
The saved artefact contains model metadata and version. Do not load untrusted joblib artefacts.

## Method
The prototype calculates:
- `TCF = exp(beta * (T - T_ref))`
- `NDP ≈ (P_feed + P_concentrate)/2 - P_permeate - pi_feed`
- `Q_norm = Q_measured / TCF * (NDP_ref / NDP)`

The osmotic-pressure approximation assumes a configurable proportionality to TDS and negligible permeate osmotic pressure. This is a transparent placeholder, not a substitute for membrane-specific ASTM D4516/vendor equations. Correct normalization should use appropriate feed/concentrate/permeate salinity, recovery, membrane model and reference conditions when available.

The candidate model predicts normalized flow 7 days ahead using lagged normalized-flow features and a Random Forest. The persistence baseline predicts that the 7-day value equals the latest value. The candidate is selected using validation MAE only; if Random Forest does not beat the baseline on validation, the saved artifact deploys the baseline instead. Final test metrics are calculated only after this selection. Training uses chronological 70%/15%/15% train/validation/test partitions. No random split is used. Time-to-threshold is estimated separately from a recent linear trend; it is not a probabilistic survival model.

## Data source log
See `data/data_source_log.md`. Public RO performance datasets may support normalization experiments but do not necessarily include long-term fouling labels or cleaning events. Synthetic data are used only for a runnable demonstration.

## Real-station data analysis

The repository also includes an analysis of `data/MBR_RO_AIOT_daily_flow_540d.xlsx`, containing 540 daily observations from 2024-01-04 through 2025-06-26. This is a separate workflow from the synthetic-data model described above.

Run the rule-based low-flow analysis:

```bash
fouling analyze-real data/MBR_RO_AIOT_daily_flow_540d.xlsx --output data/real_analysis_results.csv
```

Train and evaluate the 7-day RO production-flow forecasting baseline:

```bash
python -m fouling.train_real_flow
```

The real-station training script reports chronological train/validation/test results and compares Random Forest against a persistence baseline. In the recorded run, persistence was selected because its validation MAE (258.24 m³/day) was lower than Random Forest's (529.36 m³/day). On the held-out test segment, the selected baseline had MAE 97.02 m³/day and RMSE 183.42 m³/day. These values describe this dataset and split only; they are not proof of fouling-detection performance or generalization to another plant.

Generated files include `data/real_station_model_metrics.json`, `data/real_station_test_predictions.csv`, and `artifacts/real_station_flow_model.joblib`. The rule-based analysis output is `data/real_analysis_results.csv`.

The low-flow rules use historical production-flow observations and operational phase. Alerts are screening indicators, not confirmed fouling labels. Baselines may drift during sustained low production, and zero production may have causes other than membrane fouling. Review results with a qualified process engineer before any operational use.

## Tests
```bash
pytest -q
```

## Docker
```bash
docker build -t ro-fouling-early-warning .
docker run --rm -p 8000:8000 ro-fouling-early-warning
```

## Known limitations
- The original forecasting model is trained on synthetic data. The separate real-station workflow predicts production flow and flags low-flow patterns, not confirmed fouling.
- Simplified temperature and osmotic-pressure correction.
- Cleaning time is trend extrapolation and can be wrong after operational changes.
- No plant-specific membrane geometry, recovery, membrane age, cleaning records, or sensor calibration.
- No automatic imputation of missing values; missing required values are rejected.
- Gaps above configured limit are rejected instead of silently interpolated.

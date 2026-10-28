# AI Use Log

## 1. Tools used and purposes

- **ChatGPT:** Helped translate the project brief into an implementation plan, design the Python package and API, review validation logic, explain model-selection decisions, and improve documentation.
- **Web search and browser:** Reviewed public landing pages and descriptions for candidate RO and membrane-related datasets, including their access conditions and suitability. Candidate sources were not treated as verified training data without further inspection.
- **Python and local terminal:** Used to implement and compile the package, train and evaluate the prototype, run automated tests, inspect the real-station data, build and run Docker, test API endpoints, and validate the repository.
- **Git and GitHub:** Used for version control, documenting changes, and publishing the project repository.

## 2. Key prompts used (summarized)

1. Identify public reverse-osmosis datasets with time-series operating variables and determine whether fouling or cleaning labels are available.
2. Design chronological validation for flow forecasting, avoid data leakage, and compare a machine-learning candidate against a persistence baseline.
3. Package the workflow as a documented Python CLI/API with input validation, tests, versioned model artifacts, configuration, Docker support, and explicit limitations.

## 3. Important corrections and decisions

- Generic feature scaling is not equivalent to physical normalization. A simplified temperature and net-driving-pressure correction was implemented, with its assumptions and limitations documented.
- A factor-of-1000 error in the first-order TDS-to-osmotic-pressure coefficient was corrected. The approximation remains simplified and requires process-engineering or membrane-vendor validation.
- The synthetic Random Forest candidate performed worse than the persistence baseline on validation. Persistence was selected instead of choosing a model based on held-out test results.
- The seven-day model prediction and the separate fourteen-day linear trend projection were distinguished to avoid presenting them as the same forecast.
- Public datasets describing RO performance were not assumed to contain verified fouling and cleaning labels. The data-source log records candidate sources and limitations.
- A separate real-station workflow was added. Its flow forecasts and low-flow alerts are not evidence of confirmed membrane fouling.

## 4. Synthetic-data experiment

The synthetic forecasting experiment contains 286 supervised rows, split chronologically into 200 training, 43 validation, and 43 test rows.

- Random Forest validation MAE: 0.02077 normalized-flow ratio.
- Persistence validation MAE: 0.00794 normalized-flow ratio.
- Selected model: persistence baseline.
- Selected-model test MAE: 0.00822.
- Selected-model test RMSE: 0.00975.

These results describe the synthetic experiment only. They do not establish operational performance on a real plant.

## 5. Real-station experiment

The station spreadsheet contains 540 daily observations from 2024-01-04 through 2025-06-26, including 19 days with zero RO production.

The recorded chronological split contains 364 training, 71 validation, and 71 test rows.

- Random Forest validation MAE: 529.36 m³/day.
- Persistence validation MAE: 258.24 m³/day.
- Selected model: persistence baseline, based on validation MAE.
- Selected-baseline test MAE: 97.02 m³/day.
- Selected-baseline test RMSE: 183.42 m³/day.

The rule-based analysis recorded 47 alert days, 47 watch-low-flow days, and 19 production-stopped days. These are rule outputs, not verified fouling events. The metrics apply to this dataset and split and do not establish generalization to other plants.

## 6. Final verification — 28 October 2026

- `python -m pytest -q`: 16 tests passed in the recorded final run.
- `python -m compileall -q src tests`: completed successfully in the recorded run.
- Git whitespace check: `git diff --cached --check` completed without reported errors before the final code commit.
- Docker image was rebuilt and the container started successfully during local verification.
- The user confirmed `GET /health` returned `{"status":"ok","service":"ro-fouling-early-warning"}`.
- The `/docs` endpoint returned HTTP 200.
- The `/predict` and `/analyze-real` workflows were previously reported as successfully tested.
- The technical report and README were updated and committed to GitHub. The latest documentation commit before this log update was `3b232db`.

## 7. Remaining limitations

- The original predictive model is trained on synthetic data and is not validated for operational plant decisions.
- The real-station workflow forecasts RO production flow and flags low-flow patterns; it does not independently diagnose membrane fouling or determine chemical-cleaning requirements.
- No confirmed fouling labels or verified cleaning-event labels are available in the station dataset.
- The simplified normalization requires engineering review.
- Before operational use, the workflows need validation on appropriately labelled plant data, assessment on unseen periods or plants, and review by a qualified process engineer.

## 8. Reproducibility and deliverables

The repository includes the Python package, CLI, FastAPI service, Dockerfile, configuration, versioned model artifacts, sample data, source log, tests, README, technical report, and this AI use log.

See `README.md` for setup, prediction, real-station analysis, and API commands.

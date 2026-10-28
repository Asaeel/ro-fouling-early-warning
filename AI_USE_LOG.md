# AI Use Log

This is a working log. Keep it accurate and update it after every further tool or manual check.

## Tools used so far
- ChatGPT: helped translate the brief into a software plan, draft the project structure and code, and identify assumptions that need to be disclosed.
- Web search/browser: reviewed public landing pages for candidate RO datasets and their descriptions, variables, and access notes.
- Python execution environment: compiled the Python files, ran pytest, trained the demonstration artefact, and ran a prediction smoke test. Local validation was completed on the target Mac. The Docker image was built and the container, dashboard, and health endpoint were checked.

## Key prompts used (summarized)
1. “Find public datasets for reverse-osmosis desalination with time-series pressure, temperature, salinity, permeate flow, and fouling/cleaning labels; distinguish direct downloads from data available on request.”
2. “Design time-aware validation for normalized permeate-flow forecasting without leakage and compare with a simple baseline.”
3. “Build a runnable Python package/API with input validation, tests, versioned artefact, configuration, README, and documented limitations.”

## Corrections and verification
- Generic feature scaling (for example, StandardScaler) is not physical normalization for temperature, pressure, and salinity. The prototype uses an explicit simplified temperature/net-driving-pressure correction and documents its limitations.
- Public datasets that characterize dynamic RO performance are not automatically labelled fouling datasets. The source log separates candidates for normalization tests from datasets suitable for labelled fouling forecasting. The public landing pages were reviewed, but the downloadable workbooks/archives have not yet been fully inspected or used to train this artefact.
- An initial Random Forest result was worse than the persistence baseline on validation. The implementation was corrected to select Random Forest only if it beats the persistence baseline on the validation split; otherwise the saved artefact uses the baseline. This is a deliberate conservative selection rule, not evidence of strong predictive skill.
- The original forecasting artefact uses synthetic data only. A separate real-station workflow was subsequently added; its flow-forecasting metrics must not be represented as validated fouling-detection performance.
- Checks completed in the build environment: Python compile check; `python -m pytest -q` passed 5 tests; training and prediction smoke test completed. `python -m compileall -q src tests` also completed successfully. Docker build and runtime checks succeeded; the user confirmed the dashboard and health endpoint worked.


## 27 October 2026 — post-integration review
- Corrected a factor-of-1000 configuration error in the first-order TDS-to-osmotic-pressure coefficient: 35 g/L seawater now estimates about 26.25 bar rather than 0.026 bar. This remains a simplified approximation and requires process-engineering/vendor validation.
- Updated the synthetic generator to use the same coefficient as normalization, avoiding an internally inconsistent synthetic pipeline.
- Separated the selected model's 7-day prediction from the 14-day linear trend projection used for time-to-threshold estimation, and added a sanity test for seawater osmotic pressure.
- The original model training data remain synthetic. The separate real-station workflow uses the station spreadsheet for flow forecasting and rule-based low-flow analysis; it does not establish confirmed fouling labels.
## Final Validation Update

- **Automated tests:** 14 passed in the latest recorded run.
- **Code compilation:** `python -m compileall -q src tests` completed successfully.
- **Git commit:** `914e1de` — Add data validation tests.
- **Repository status:** Not clean at the latest review; real-station analysis, training, metrics, predictions, and tests include uncommitted changes.
- **Validation coverage:** Synthetic data acceptance, missing columns, duplicate timestamps, excessive time gaps, out-of-range temperature, non-numeric flow values, and non-positive permeate flow.
- **Important limitation:** The original predictive model is trained on synthetic data. The separate real-station workflow forecasts RO production flow and flags low-flow patterns, but no confirmed fouling labels are available. Neither workflow should be treated as an operational maintenance recommendation.


## Real-station workflow — documentation update

- Reviewed `data/real_station_model_metrics.json`: 540 observations, 2024-01-04 to 2025-06-26, with no missing calendar dates and 19 zero-RO-flow days.
- The 7-day flow-forecasting experiment uses chronological splits: 364 training, 71 validation, and 71 test rows.
- Validation MAE: Random Forest 529.36 m³/day; persistence baseline 258.24 m³/day. The persistence baseline was selected using validation MAE.
- Test metrics for the selected baseline: MAE 97.02 m³/day; RMSE 183.42 m³/day. Random Forest test RMSE was lower, but the model selection rule was based on validation MAE and must not be changed using test results.
- The rule-based analysis produced 47 alert days, 47 watch-low-flow days, and 19 production-stopped days in the recorded run. These are rule outputs, not verified fouling events.
- Latest test and compilation checks reported by the user: 14 tests passed; `python -m compileall -q src tests` completed successfully.
- Documentation was updated to distinguish the synthetic forecasting prototype from the real-station production-flow workflow. Re-run checks after documentation changes and record their actual results.

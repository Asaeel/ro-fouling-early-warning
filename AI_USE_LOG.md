# AI Use Log

This is a working log. Keep it accurate and update it after every further tool or manual check.

## Tools used so far
- ChatGPT: helped translate the brief into a software plan, draft the project structure and code, and identify assumptions that need to be disclosed.
- Web search/browser: reviewed public landing pages for candidate RO datasets and their descriptions, variables, and access notes.
- Python execution environment: compiled the Python files, ran pytest, trained the demonstration artefact, and ran a prediction smoke test. These checks were run in the project build environment; repeat them on the target Mac before final submission.

## Key prompts used (summarized)
1. “Find public datasets for reverse-osmosis desalination with time-series pressure, temperature, salinity, permeate flow, and fouling/cleaning labels; distinguish direct downloads from data available on request.”
2. “Design time-aware validation for normalized permeate-flow forecasting without leakage and compare with a simple baseline.”
3. “Build a runnable Python package/API with input validation, tests, versioned artefact, configuration, README, and documented limitations.”

## Corrections and verification
- Generic feature scaling (for example, StandardScaler) is not physical normalization for temperature, pressure, and salinity. The prototype uses an explicit simplified temperature/net-driving-pressure correction and documents its limitations.
- Public datasets that characterize dynamic RO performance are not automatically labelled fouling datasets. The source log separates candidates for normalization tests from datasets suitable for labelled fouling forecasting. The public landing pages were reviewed, but the downloadable workbooks/archives have not yet been fully inspected or used to train this artefact.
- An initial Random Forest result was worse than the persistence baseline on validation. The implementation was corrected to select Random Forest only if it beats the persistence baseline on the validation split; otherwise the saved artefact uses the baseline. This is a deliberate conservative selection rule, not evidence of strong predictive skill.
- The artefact currently uses synthetic data only. The model metrics must not be represented as real-plant performance.
- Checks completed in the build environment: Python compile check; `pytest -q` passed 4 tests; training and prediction smoke test completed. Re-run these commands in a clean Mac environment and record the exact result before final delivery.


## 27 October 2026 — post-integration review
- Corrected a factor-of-1000 configuration error in the first-order TDS-to-osmotic-pressure coefficient: 35 g/L seawater now estimates about 26.25 bar rather than 0.026 bar. This remains a simplified approximation and requires process-engineering/vendor validation.
- Updated the synthetic generator to use the same coefficient as normalization, avoiding an internally inconsistent synthetic pipeline.
- Separated the selected model's 7-day prediction from the 14-day linear trend projection used for time-to-threshold estimation, and added a sanity test for seawater osmotic pressure.
- The training data remain synthetic; no real-plant performance claim is made.

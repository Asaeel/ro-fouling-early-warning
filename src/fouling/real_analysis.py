from __future__ import annotations

from pathlib import Path

import pandas as pd


def analyze_real_data(
    input_path: str | Path,
    output_path: str | Path,
    threshold_ratio: float = 0.90,
    baseline_days: int = 30,
    consecutive_days: int = 3,
) -> dict:
    """Analyze RO production decline using historical operating data.

    This is an operational early-warning indicator, not a validated
    membrane-fouling diagnosis.
    """
    if not 0 < threshold_ratio < 1:
        raise ValueError("threshold_ratio must be between 0 and 1.")

    if (
        not isinstance(baseline_days, int)
        or isinstance(baseline_days, bool)
        or baseline_days < 1
    ):
        raise ValueError("baseline_days must be a positive integer.")

    if (
        not isinstance(consecutive_days, int)
        or isinstance(consecutive_days, bool)
        or consecutive_days < 1
    ):
        raise ValueError("consecutive_days must be a positive integer.")

    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    if source.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(source, sheet_name="Sheet1", header=1)
    elif source.suffix.lower() == ".csv":
        df = pd.read_csv(source)
    else:
        raise ValueError("Input must be an Excel (.xlsx/.xls) or CSV file.")

    df.columns = [str(c).strip() for c in df.columns]

    required = ["Day", "Date", "RO product (m3/day)", "Phase"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))

    if df.empty:
        raise ValueError("Input file contains no data rows.")

    out = df.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["RO product (m3/day)"] = pd.to_numeric(
        out["RO product (m3/day)"], errors="coerce"
    )

    if out["Date"].isna().any():
        raise ValueError("Date contains missing or invalid values.")

    if out["RO product (m3/day)"].isna().any():
        raise ValueError("RO production contains missing or non-numeric values.")

    if (out["RO product (m3/day)"] < 0).any():
        raise ValueError("RO production cannot be negative.")

    if out["Phase"].isna().any():
        raise ValueError("Phase contains missing values.")

    out["Phase"] = out["Phase"].astype(str).str.strip()
    if out["Phase"].eq("").any():
        raise ValueError("Phase contains empty values.")

    # Use calendar dates for daily sequencing and detect duplicate days.
    out["Date"] = out["Date"].dt.normalize()
    if out["Date"].duplicated().any():
        duplicates = (
            out.loc[out["Date"].duplicated(keep=False), "Date"]
            .dt.strftime("%Y-%m-%d")
            .unique()
            .tolist()
        )
        raise ValueError(f"Duplicate dates found: {duplicates[:10]}")

    out = out.sort_values("Date").reset_index(drop=True)

    out["baseline_ro_m3_day"] = float("nan")
    out["flow_ratio"] = float("nan")
    out["flow_pct_of_baseline"] = float("nan")
    out["low_flow"] = False
    out["alert"] = False
    out["status"] = "insufficient_baseline"

    # Keep prior positive flows by phase. The current observation is
    # never included in its own baseline.
    history: dict[str, list[float]] = {}

    # A run of low-flow days must be uninterrupted in calendar time.
    # Missing-baseline days and stopped-production days break the run.
    low_run: dict[str, list[pd.Timestamp]] = {}
    previous_date: dict[str, pd.Timestamp] = {}

    for i, row in out.iterrows():
        phase = str(row["Phase"])
        date = row["Date"]
        flow = float(row["RO product (m3/day)"])

        history.setdefault(phase, [])
        low_run.setdefault(phase, [])

        # A phase's sequence cannot continue across a calendar-date gap.
        last_date = previous_date.get(phase)
        if last_date is not None and (date - last_date).days != 1:
            low_run[phase] = []

        previous_date[phase] = date

        if flow == 0:
            out.at[i, "status"] = "production_stopped"
            low_run[phase] = []
            continue

        prior = history[phase][-baseline_days:]

        if len(prior) < baseline_days:
            # This day cannot be classified reliably; it also breaks
            # any consecutive low-flow sequence.
            out.at[i, "status"] = "insufficient_baseline"
            low_run[phase] = []
            history[phase].append(flow)
            continue

        baseline = float(pd.Series(prior).median())
        out.at[i, "baseline_ro_m3_day"] = baseline

        ratio = flow / baseline if baseline > 0 else float("nan")
        out.at[i, "flow_ratio"] = ratio
        out.at[i, "flow_pct_of_baseline"] = ratio * 100

        is_low = bool(pd.notna(ratio) and ratio < threshold_ratio)
        out.at[i, "low_flow"] = is_low

        if is_low:
            out.at[i, "status"] = "watch_low_flow"
            low_run[phase].append(date)
        else:
            out.at[i, "status"] = "normal"
            low_run[phase] = []

        # Keep only a run of consecutive calendar dates.
        if len(low_run[phase]) > consecutive_days:
            low_run[phase] = low_run[phase][-consecutive_days:]

        if len(low_run[phase]) == consecutive_days:
            elapsed_days = (
                low_run[phase][-1] - low_run[phase][0]
            ).days

            if elapsed_days == consecutive_days - 1:
                out.at[i, "alert"] = True
                out.at[i, "status"] = "alert_low_flow"

        history[phase].append(flow)

    # Export dates in a readable, consistent format.
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(destination, index=False)

    status_counts = {
        str(key): int(value)
        for key, value in out["status"].value_counts().items()
    }

    return {
        "input_file": str(source),
        "output_file": str(destination),
        "rows_analyzed": int(len(out)),
        "threshold_ratio": threshold_ratio,
        "baseline_days": baseline_days,
        "consecutive_days_for_alert": consecutive_days,
        "alert_count": int(out["alert"].sum()),
        "low_flow_day_count": int(out["low_flow"].sum()),
        "production_stopped_day_count": int(
            (out["status"] == "production_stopped").sum()
        ),
        "status_counts": status_counts,
        "data_type": "real_operational_dataset",
        "interpretation": (
            "Alerts indicate consecutive days of RO production below "
            "the configured threshold relative to the median of the "
            "previous positive-production observations in the same phase. "
            "Insufficient-baseline days, stopped-production days, and "
            "calendar-date gaps break alert sequences. These alerts do "
            "not confirm membrane fouling or determine cleaning requirements."
        ),
    }

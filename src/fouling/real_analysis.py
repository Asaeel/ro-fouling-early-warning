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
    """Analyze daily RO production using historical operating data.

    This is a transparent production-decline indicator, not a
    validated membrane-fouling diagnosis.
    """
    if not 0 < threshold_ratio < 1:
        raise ValueError("threshold_ratio must be between 0 and 1.")
    if baseline_days < 1 or consecutive_days < 1:
        raise ValueError("Day counts must be positive integers.")

    source = Path(input_path)
    if source.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(source, sheet_name="Sheet1", header=1)
    else:
        df = pd.read_csv(source)

    df.columns = [str(c).strip() for c in df.columns]

    required = [
        "Day", "Date", "RO product (m3/day)", "Phase"
    ]
    missing = [c for c in required if c not in df.columns]
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
    if out["Date"].duplicated().any():
        raise ValueError("Duplicate dates found.")
    out = out.sort_values("Date").reset_index(drop=True)

    out["baseline_ro_m3_day"] = float("nan")
    out["flow_ratio"] = float("nan")
    out["flow_pct_of_baseline"] = float("nan")
    out["low_flow"] = False
    out["alert"] = False
    out["status"] = "insufficient_baseline"

    # Calculate the baseline from earlier positive-production days
    # in the same operating phase. The current day is never included.
    history: dict[str, list[float]] = {}
    previous_rows: dict[str, list[dict]] = {}

    for i, row in out.iterrows():
        phase = str(row["Phase"])
        flow = float(row["RO product (m3/day)"])
        history.setdefault(phase, [])
        previous_rows.setdefault(phase, [])

        if flow == 0:
            out.at[i, "status"] = "production_stopped"
            previous_rows[phase].append(
                {"date": row["Date"], "low": False, "stopped": True}
            )
            continue

        prior = history[phase][-baseline_days:]
        if len(prior) >= baseline_days:
            baseline = float(pd.Series(prior).median())
            out.at[i, "baseline_ro_m3_day"] = baseline
            ratio = flow / baseline if baseline > 0 else float("nan")
            out.at[i, "flow_ratio"] = ratio
            out.at[i, "flow_pct_of_baseline"] = ratio * 100

            is_low = ratio < threshold_ratio
            out.at[i, "low_flow"] = is_low
            out.at[i, "status"] = "watch_low_flow" if is_low else "normal"

            recent = previous_rows[phase][- (consecutive_days - 1):]
            sequence = recent + [
                {"date": row["Date"], "low": is_low, "stopped": False}
            ]

            consecutive = len(sequence) >= consecutive_days
            if consecutive:
                sequence = sequence[-consecutive_days:]
                consecutive = all(
                    item["low"] and not item["stopped"]
                    for item in sequence
                )
                if consecutive:
                    dates = [item["date"] for item in sequence]
                    consecutive = all(
                        (dates[j] - dates[j - 1]).days == 1
                        for j in range(1, len(dates))
                    )

            if consecutive:
                out.at[i, "alert"] = True
                out.at[i, "status"] = "alert_low_flow"

        history[phase].append(flow)
        previous_rows[phase].append(
            {
                "date": row["Date"],
                "low": bool(out.at[i, "low_flow"]),
                "stopped": False,
            }
        )

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
        "status_counts": status_counts,
        "data_type": "real_operational_dataset",
        "interpretation": (
            "Alerts indicate sustained RO production decline relative to "
            "the previous operating history in the same phase. They do not "
            "confirm membrane fouling or determine cleaning requirements."
        ),
    }

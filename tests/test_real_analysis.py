import pandas as pd
import pytest

from src.fouling.real_analysis import analyze_real_data


def make_data(flows):
    return pd.DataFrame({
        "Day": range(1, len(flows) + 1),
        "Date": pd.date_range("2025-01-01", periods=len(flows)),
        "RO product (m3/day)": flows,
        "Phase": ["Handover"] * len(flows),
    })


def test_alert_starts_after_three_consecutive_low_days(tmp_path):
    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"

    # Five baseline days followed by three low-flow days.
    make_data([100] * 5 + [80, 80, 80]).to_csv(source, index=False)

    analyze_real_data(
        source, output, threshold_ratio=0.9,
        baseline_days=5, consecutive_days=3
    )

    result = pd.read_csv(output)

    assert result["alert"].tolist() == [
        False, False, False, False, False,
        False, False, True
    ]


def test_zero_flow_breaks_alert_sequence(tmp_path):
    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"

    make_data([100] * 5 + [80, 80, 0, 80, 80]).to_csv(
        source, index=False
    )

    analyze_real_data(
        source, output, threshold_ratio=0.9,
        baseline_days=5, consecutive_days=3
    )

    result = pd.read_csv(output)

    assert not result["alert"].any()
    assert result.loc[7, "status"] == "production_stopped"


def test_missing_dates_break_alert_sequence(tmp_path):
    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"

    data = make_data([100] * 5 + [80, 80, 80, 80])
    data.loc[7:, "Date"] += pd.Timedelta(days=1)
    data.to_csv(source, index=False)

    analyze_real_data(
        source, output, threshold_ratio=0.9,
        baseline_days=5, consecutive_days=3
    )

    result = pd.read_csv(output)

    assert not result["alert"].any()


def test_negative_threshold_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        analyze_real_data(
            "missing.csv", tmp_path / "output.csv",
            threshold_ratio=-0.1
        )

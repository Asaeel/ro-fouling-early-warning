from __future__ import annotations

import argparse
import json

import pandas as pd
import yaml

from .model import train_model, predict_dataframe
from .real_analysis import analyze_real_data


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(
        prog="fouling",
        description="RO membrane fouling early-warning prototype",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    tr = sub.add_parser(
        "train",
        help="Train and save a demonstration model using synthetic data",
    )
    tr.add_argument("--config", default="config.yaml")
    tr.add_argument("--artifact", default=None)

    ra = sub.add_parser(
        "analyze-real",
        help="Analyze real daily RO production data",
    )
    ra.add_argument("file", help="Input Excel or CSV file")
    ra.add_argument("--output", default="data/real_analysis_results.csv")
    ra.add_argument("--threshold", type=float, default=0.90)
    ra.add_argument("--baseline-days", type=int, default=30)
    ra.add_argument("--consecutive-days", type=int, default=3)

    pr = sub.add_parser("predict", help="Predict from a plant CSV")
    pr.add_argument("csv")
    pr.add_argument("--config", default="config.yaml")
    pr.add_argument("--artifact", default=None)

    args = parser.parse_args()

    if args.command == "analyze-real":
        result = analyze_real_data(
            args.file,
            args.output,
            args.threshold,
            args.baseline_days,
            args.consecutive_days,
        )
        print(json.dumps(result, indent=2, default=str))
        return

    config = load_config(args.config)
    artifact = args.artifact or config["model"]["artifact_path"]

    if args.command == "train":
        print(json.dumps(train_model(config, artifact), indent=2))
    elif args.command == "predict":
        df = pd.read_csv(args.csv)
        result = predict_dataframe(df, config, artifact)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

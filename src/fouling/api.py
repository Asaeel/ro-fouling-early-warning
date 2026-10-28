from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import yaml
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .model import predict_dataframe
from .real_analysis import analyze_real_data

app = FastAPI(
    title="RO Fouling Early-Warning API",
    version="0.1.0",
    description="Prototype for RO production monitoring and early warning.",
)

STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ro-fouling-early-warning"}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")

    try:
        df = pd.read_csv(file.file)
        cfg = _load_config()
        return predict_dataframe(df, cfg, cfg["model"]["artifact_path"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="Model artefact not found. Run `fouling train` first.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process CSV: {exc}",
        ) from exc


@app.post("/analyze-real")
async def analyze_real(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Choose a file.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(
            status_code=400,
            detail="Upload an Excel (.xlsx, .xls) or CSV (.csv) file.",
        )

    try:
        content = await file.read()
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / f"input{suffix}"
            output = Path(temp_dir) / "analysis_results.csv"
            source.write_bytes(content)

            summary = analyze_real_data(source, output)
            result_df = pd.read_csv(output)

            # Convert dates, NumPy values, and missing cells to JSON-safe values.
            result_df = result_df.astype(object).where(
                pd.notna(result_df), None
            )
            rows = result_df.to_dict(orient="records")

            for row in rows:
                for key, value in row.items():
                    if hasattr(value, "item"):
                        row[key] = value.item()
                    if pd.isna(row[key]) if row[key] is not None else False:
                        row[key] = None

            summary["input_file"] = file.filename
            summary["output_file"] = "analysis_results.csv"
            return {"summary": summary, "rows": rows}

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not analyze file: {exc}",
        ) from exc

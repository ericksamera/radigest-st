from __future__ import annotations

import json
from pathlib import Path
from typing import SupportsFloat, cast

import pandas as pd
import streamlit as st


def file_signature(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (str(path), stat.st_size, stat.st_mtime_ns)


@st.cache_data(show_spinner=False)
def read_tsv_cached(path: str, size: int, mtime_ns: int) -> pd.DataFrame:
    del size, mtime_ns
    return pd.read_csv(path, sep="\t")


@st.cache_data(show_spinner=False)
def read_json_cached(path: str, size: int, mtime_ns: int) -> dict:
    del size, mtime_ns
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_tsv(path: Path) -> pd.DataFrame:
    return read_tsv_cached(*file_signature(path))


def read_json(path: Path) -> dict:
    return read_json_cached(*file_signature(path))


def truthy_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def first_value(df: pd.DataFrame, column: str, default: object = "NA") -> object:
    if column not in df.columns or df.empty:
        return default
    value = df.iloc[0][column]
    if pd.isna(value):
        return default
    return value


def format_float(value: object, digits: int = 3) -> str:
    try:
        numeric = cast(SupportsFloat, value)
        return f"{float(numeric):.{digits}f}"
    except (TypeError, ValueError):
        return "NA"

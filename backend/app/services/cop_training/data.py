"""Reading the uploaded table: CSV (comma or semicolon, decimal point or
comma), Excel (any sheet) or Parquet, and guessing which column is which."""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any, Dict, List, Optional

import pandas as pd

MAX_FILE_BYTES = 20 * 1024 * 1024
# Rows used for training. A small network with 2–4 temperature inputs stops
# improving well before this (the shipped model saw 3,468), and it keeps a
# training run to seconds. Larger files are sampled down, not rejected.
MAX_ROWS = 10_000
MIN_ROWS = 30
# What a file may unpack to. Excel and Parquet are compressed, so 20 MB on the
# wire can be gigabytes once read; these are checked before anything is parsed.
# Rows above MAX_ROWS are sampled down, but only up to this many are read.
MAX_READ_ROWS = 200_000
MAX_COLUMNS = 200
MAX_SHEETS = 50
MAX_UNPACKED_BYTES = 100 * 1024 * 1024


class DataError(ValueError):
    pass


def _numeric(col: pd.Series) -> pd.Series:
    """Numbers as written, with a decimal comma allowed."""
    if col.dtype.kind in "if":
        return col.astype(float)
    text = col.astype(str).str.strip().str.replace(" ", "", regex=False)
    if text.str.contains(r"^-?\d{1,3}(?:\.\d{3})*,\d+$|^-?\d+,\d+$", regex=True).any():
        text = text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


EXCEL = (".xlsx", ".xlsm")


def _check_size(content: bytes) -> None:
    if len(content) > MAX_FILE_BYTES:
        raise DataError(f"The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")


def _check_excel(content: bytes) -> None:
    """An .xlsx is a zip of XML: its unpacked size is known before parsing."""
    _check_size(content)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            unpacked = sum(i.file_size for i in z.infolist())
    except zipfile.BadZipFile as exc:
        raise DataError("The file is not a valid Excel (.xlsx) file.") from exc
    if unpacked > MAX_UNPACKED_BYTES:
        raise DataError(f"The Excel file unpacks to more than {MAX_UNPACKED_BYTES // (1024 * 1024)} MB.")


def _check_parquet(content: bytes) -> None:
    """Rows, columns and unpacked size from the Parquet footer, before reading."""
    import pyarrow.parquet as pq
    try:
        meta = pq.ParquetFile(io.BytesIO(content)).metadata
    except Exception as exc:  # noqa: BLE001 - any parser failure is the file's
        raise DataError(f"The file could not be read: {exc}") from exc
    _check_shape(meta.num_rows, meta.num_columns)
    unpacked = sum(meta.row_group(i).total_byte_size for i in range(meta.num_row_groups))
    if unpacked > MAX_UNPACKED_BYTES:
        raise DataError(f"The Parquet file unpacks to more than {MAX_UNPACKED_BYTES // (1024 * 1024)} MB.")


def _check_shape(rows: int, columns: int) -> None:
    if rows > MAX_READ_ROWS:
        raise DataError(f"The table has more than {MAX_READ_ROWS:,} rows.")
    if columns > MAX_COLUMNS:
        raise DataError(f"The table has more than {MAX_COLUMNS} columns.")


def sheets(filename: str, content: bytes) -> List[str]:
    """The sheets of an Excel file; empty for other files."""
    if not filename.lower().endswith(EXCEL):
        return []
    _check_excel(content)
    try:
        names = pd.ExcelFile(io.BytesIO(content)).sheet_names
    except Exception as exc:  # noqa: BLE001 - any parser failure is the file's
        raise DataError(f"The file could not be read: {exc}") from exc
    if len(names) > MAX_SHEETS:
        raise DataError(f"The Excel file has more than {MAX_SHEETS} sheets.")
    return names


def default_sheet(filename: str, content: bytes) -> Optional[str]:
    """The first sheet with a COP column (parameter studies often keep their
    inputs on the first sheet and the results on another), else the first."""
    names = sheets(filename, content)
    try:
        book = pd.ExcelFile(io.BytesIO(content)) if names else None
        for name in names:
            head = pd.read_excel(book, sheet_name=name, nrows=0)
            if any(re.search(r"\bcop\b", str(c).lower()) for c in head.columns):
                return name
    except Exception as exc:  # noqa: BLE001 - any parser failure is the file's
        raise DataError(f"The file could not be read: {exc}") from exc
    return names[0] if names else None


def read_table(filename: str, content: bytes, sheet: Optional[str] = None) -> pd.DataFrame:
    _check_size(content)
    name = filename.lower()
    # One row more than allowed, so a longer table is told apart from one of
    # exactly MAX_READ_ROWS without reading the rest.
    nrows = MAX_READ_ROWS + 1
    try:
        if name.endswith(EXCEL):
            _check_excel(content)
            df = pd.read_excel(io.BytesIO(content), sheet_name=sheet or default_sheet(filename, content),
                               nrows=nrows)
        elif name.endswith((".csv", ".txt", ".tsv")):
            kw = dict(sep=None, engine="python", encoding_errors="replace")
            # The header first: a single line of a million cells is no table.
            _check_shape(0, len(pd.read_csv(io.BytesIO(content), nrows=0, **kw).columns))
            df = pd.read_csv(io.BytesIO(content), nrows=nrows, **kw)
        elif name.endswith(".parquet"):
            _check_parquet(content)
            df = pd.read_parquet(io.BytesIO(content))
        else:
            raise DataError("Upload a CSV, Excel (.xlsx) or Parquet file.")
    except DataError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure is the file's
        raise DataError(f"The file could not be read: {exc}") from exc
    _check_shape(len(df), len(df.columns))
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or len(df.columns) < 3:
        raise DataError("The table needs at least three columns: two temperatures and the COP.")
    return df


# Name patterns per role, for a first guess of the mapping.
_GUESS = {
    "COP": [r"^cop$", r"\bcop\b"],
    "T_source_out": [r"r(ü|ue)cklauf.*quelle", r"source.*(out|return)", r"evap.*out", r"t_?src"],
    "T_sink_out": [r"vorlauf.*senke", r"sink.*(out|supply)", r"cond.*out", r"t_?sink"],
    "medium": [r"medium", r"senke.*medium"],
    "refrigerant": [r"k(ä|ae)ltemittel", r"refrigerant", r"fluid"],
    "stages": [r"stufe", r"stage", r"compressor", r"verdichter"],
}


def guess_mapping(columns) -> Dict[str, Optional[str]]:
    taken, out = set(), {}
    for role, patterns in _GUESS.items():
        out[role] = None
        for pat in patterns:
            hit = next((c for c in columns if c not in taken and re.search(pat, c.lower())), None)
            if hit:
                out[role] = hit
                taken.add(hit)
                break
    return out


def inspect(df: pd.DataFrame, sheet_names: Optional[List[str]] = None,
            sheet: Optional[str] = None) -> Dict[str, Any]:
    # Numbers in (nearly) every row; a units row like "°C" does not spoil it.
    numeric = [c for c in df.columns if _numeric(df[c]).notna().mean() > 0.9]
    return {
        "sheets": sheet_names or [],
        "sheet": sheet,
        "columns": list(df.columns),
        "numeric_columns": numeric,
        "rows": len(df),
        "max_rows": MAX_ROWS,
        "min_rows": MIN_ROWS,
        # Empty cells as "", so the preview is valid JSON (no NaN).
        "preview": df.head(8).map(lambda v: "" if pd.isna(v) else str(v)).to_dict(orient="records"),
        "guess": guess_mapping(list(df.columns)),
    }

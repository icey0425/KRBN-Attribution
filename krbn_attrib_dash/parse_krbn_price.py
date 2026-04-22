"""
Parse KRBN price.xlsx: daily prices or returns for KRBN LN and Index.
Output: DataFrame with statement_date, krbn_ret, index_ret (decimal).
"""
from pathlib import Path
import pandas as pd


def _find_date_col(df: pd.DataFrame):
    for c in df.columns:
        if "date" in str(c).lower():
            return c
    return df.columns[0]


def _find_krbn_col(df: pd.DataFrame):
    for c in df.columns:
        s = str(c).lower()
        if "krbn" in s and "index" not in s:
            return c
    return None


def _find_index_col(df: pd.DataFrame):
    for c in df.columns:
        s = str(c).lower()
        if "index" in s or "glcarbp" in s:
            return c
    return None


def _is_likely_return(series: pd.Series) -> bool:
    """True if values look like returns (e.g. -0.02 to 0.02) rather than prices."""
    drop = series.dropna()
    if len(drop) == 0:
        return False
    abs_median = drop.abs().median()
    return abs_median < 0.5 and drop.abs().max() < 2.0


def parse_krbn_price_file(filepath: str | Path) -> pd.DataFrame:
    """
    Read KRBN price.xlsx. Expects first sheet with a date column and KRBN / Index columns.
    If columns look like prices, compute daily returns; if like returns, use as is.
    Returns DataFrame with columns: statement_date, krbn_ret, index_ret (decimal).
    """
    path = Path(filepath)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_excel(path, sheet_name=0)
    if df.empty or len(df.columns) < 2:
        return pd.DataFrame()

    date_col = _find_date_col(df)
    krbn_col = _find_krbn_col(df)
    index_col = _find_index_col(df)
    if krbn_col is None or index_col is None:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["statement_date"] = pd.to_datetime(df[date_col]).dt.normalize()
    krbn = pd.to_numeric(df[krbn_col], errors="coerce")
    idx = pd.to_numeric(df[index_col], errors="coerce")

    if _is_likely_return(krbn) and _is_likely_return(idx):
        out["krbn_ret"] = krbn
        out["index_ret"] = idx
    else:
        out["krbn_ret"] = krbn.pct_change()
        out["index_ret"] = idx.pct_change()

    out = out.dropna(subset=["statement_date"])
    out = out.sort_values("statement_date").drop_duplicates(subset=["statement_date"], keep="first").reset_index(drop=True)
    return out


def build_krbn_index_returns():
    """Load KRBN price spreadsheet, parse, and save to processed/krbn_index_daily_returns.parquet."""
    from config import get_krbn_price_path, KRBN_INDEX_RETURNS_PATH, ensure_processed_dir
    path = get_krbn_price_path()
    if not path.exists():
        return pd.DataFrame()
    df = parse_krbn_price_file(path)
    if df.empty:
        return df
    ensure_processed_dir()
    df.to_parquet(KRBN_INDEX_RETURNS_PATH, index=False)
    return df

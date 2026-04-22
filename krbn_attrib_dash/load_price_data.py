"""
Load KRBN price.xlsx: daily returns (in % form) for KRBN LN and GLCARBP Index.
Columns: Date | KRBN LN | GLCARBP Index. Values e.g. 0.4483 = 0.4483%.
"""
import pandas as pd

from config import get_krbn_price_path


def _find_column(df, *candidates):
    """Return first column name in df that matches any candidate (strip, case-insensitive)."""
    for c in df.columns:
        raw = str(c).strip().lower()
        for want in candidates:
            if want.strip().lower() == raw or want.strip().lower() in raw:
                return c
    return None


def load_price_data():
    """Load KRBN price.xlsx. Returns DataFrame with Date, fund_ret_pct, index_ret_pct."""
    path = get_krbn_price_path()
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_excel(path)
    if df.empty or len(df.columns) < 3:
        return pd.DataFrame()

    # Normalize column names (strip whitespace)
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    date_col = _find_column(df, "Date", "date")
    fund_col = _find_column(df, "KRBN LN", "KRBN")
    index_col = _find_column(df, "GLCARBP Index", "GLCARBP", "Index")

    if not date_col or not fund_col or not index_col:
        return pd.DataFrame()

    df = df.rename(columns={date_col: "Date", fund_col: "fund_ret_pct", index_col: "index_ret_pct"})
    df = df[["Date", "fund_ret_pct", "index_ret_pct"]].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    return df

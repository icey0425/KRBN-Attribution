"""Parse FCM statement Excel: find Futures table, return normalized DataFrame."""
import re
from pathlib import Path
import pandas as pd

EXCEL_TO_NORM = {
    "Contract": "contract_label",
    "Bbg ID": "bbg_id",
    "Security Name": "security_name",
    "Position": "position",
    "Contract Size": "contract_size",
    "Ccy": "ccy",
    "FX": "fx",
    "Prior Day Close Px": "prior_close_px",
    "Current Exposure (USD)": "exposure_usd",
    "% Benchmark": "w_benchmark",
    "% NAV": "w_fund",
}


def _parse_date_from_filename(filepath):
    """'...02-27-26.xlsx' -> 2026-02-27."""
    name = Path(filepath).stem
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{2})\b", name)
    if not m:
        return None
    month, day, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = 2000 + yy if yy < 70 else 1900 + yy
    try:
        return pd.Timestamp(year=year, month=month, day=day)
    except Exception:
        return None


def _pct_to_decimal(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val) / 100.0 if (val > 1.5 or val < -0.5) else float(val)
    s = str(val).strip().replace("%", "")
    try:
        x = float(s)
        return x / 100.0 if (x > 1.5 or x < -0.5) else x
    except ValueError:
        return None


def _market_bucket(label):
    if pd.isna(label):
        return "OTHER"
    s = str(label).strip().upper()
    if "EUA" in s: return "EUA"
    if "UKA" in s: return "UKA"
    if "CCA" in s: return "CCA"
    if "RGGI" in s: return "RGGI"
    if "WCA" in s: return "WCA"
    return "OTHER"


def _find_futures_sheet(xl):
    for name in xl.sheet_names:
        if "Futures" in name:
            return name
    return xl.sheet_names[0]


def _find_header_row(df):
    for i in range(min(50, len(df))):
        cells = " ".join(str(v) for v in df.iloc[i].astype(str))
        if "Contract" in cells and "Bbg ID" in cells:
            return i
    return None


def _read_table(filepath, sheet_name, statement_date):
    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
    hr = _find_header_row(df_raw)
    if hr is None:
        return pd.DataFrame()

    header_row = df_raw.iloc[hr]
    col_names = [EXCEL_TO_NORM.get(str(v).strip(), None) for v in header_row]
    col_idx = [i for i, n in enumerate(col_names) if n is not None]
    names = [col_names[i] for i in col_idx]
    try:
        i_contract = names.index("contract_label")
        i_bbg = names.index("bbg_id")
        i_exposure = names.index("exposure_usd") if "exposure_usd" in names else None
    except ValueError:
        return pd.DataFrame()

    rows = []
    consecutive_blank = 0
    for i in range(hr + 1, len(df_raw)):
        r = df_raw.iloc[i]
        contract_blank = pd.isna(r.iloc[col_idx[i_contract]]) or str(r.iloc[col_idx[i_contract]]).strip() == ""
        bbg_blank = pd.isna(r.iloc[col_idx[i_bbg]]) or str(r.iloc[col_idx[i_bbg]]).strip() == ""

        if contract_blank and bbg_blank:
            consecutive_blank += 1
            if consecutive_blank >= 2:
                break
            if i_exposure is not None:
                exp = r.iloc[col_idx[i_exposure]]
                if pd.notna(exp) and str(exp).strip() != "":
                    break
            cell_str = " ".join(str(r.iloc[j]) for j in range(min(8, len(r))))
            if "Collateral" in cell_str:
                break
            continue
        consecutive_blank = 0
        cell_str = " ".join(str(r.iloc[j]) for j in range(min(8, len(r))))
        if "Collateral" in cell_str and "Futures" not in cell_str:
            break
        rows.append({n: r.iloc[col_idx[j]] for j, n in enumerate(names)})

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out["statement_date"] = statement_date
    out["bbg_id"] = out["bbg_id"].astype(str).str.strip()
    out = out[out["bbg_id"].notna() & (out["bbg_id"] != "") & (out["bbg_id"] != "nan")]
    out = out[out["prior_close_px"].notna()]
    out["prior_close_px"] = pd.to_numeric(out["prior_close_px"], errors="coerce")
    out = out[out["prior_close_px"].notna()]

    for w in ("w_benchmark", "w_fund"):
        if w in out.columns:
            out[w] = out[w].apply(_pct_to_decimal)
    if "ccy" in out.columns and "fx" in out.columns:
        usd = out["ccy"].astype(str).str.upper().str.strip() == "USD"
        out.loc[usd & out["fx"].isna(), "fx"] = 1.0
    if "fx" in out.columns:
        out["fx"] = pd.to_numeric(out["fx"], errors="coerce")
    out["market_bucket"] = out["contract_label"].astype(str).map(_market_bucket)
    return out


def parse_futures_table(filepath, statement_date):
    path = Path(filepath)
    if path.suffix.lower() not in (".xlsx", ".xls"):
        return pd.DataFrame()
    with pd.ExcelFile(path, engine="openpyxl") as xl:
        sheet = _find_futures_sheet(xl)
        return _read_table(path, sheet, statement_date)


def parse_statement_date_from_filename(filepath):
    return _parse_date_from_filename(filepath)

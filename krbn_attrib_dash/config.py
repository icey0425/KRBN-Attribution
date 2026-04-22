"""Paths for KRBN attribution. Raw data: LN - KRBN ETC Position Snapshots (sibling folder)."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

RAW_DIR = WORKSPACE_ROOT / "LN - KRBN ETC Position Snapshots"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

FUTURES_PANEL_PATH = PROCESSED_DIR / "futures_panel.parquet"
FUTURES_RETURNS_PATH = PROCESSED_DIR / "futures_returns.parquet"
ATTRIB_DAILY_PATH = PROCESSED_DIR / "attrib_daily.parquet"
ATTRIB_DAILY_TOTALS_PATH = PROCESSED_DIR / "attrib_daily_totals.parquet"

# KRBN price.xlsx: daily returns for Growth of $1 chart (Date | KRBN LN | GLCARBP Index)
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def get_krbn_price_path():
    for base in (DATA_RAW_DIR, PROJECT_ROOT / "data", WORKSPACE_ROOT):
        if not base.exists():
            continue
        for name in ("KRBN price.xlsx", "KRBN price.xls", "KRBN price"):
            p = base / name
            if p.exists():
                return p
        # Fallback: any file in this folder whose name contains "KRBN" and "price"
        try:
            for f in base.iterdir():
                if f.is_file() and "KRBN" in f.name.upper() and "price" in f.name.lower():
                    return f
        except OSError:
            pass
    return DATA_RAW_DIR / "KRBN price.xlsx"

EXCEL_GLOB = "*.xlsx"


def ensure_processed_dir():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

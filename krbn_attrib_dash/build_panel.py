"""Build futures panel from all Excel files in raw folder."""
from pathlib import Path
import pandas as pd

from config import RAW_DIR, PROCESSED_DIR, FUTURES_PANEL_PATH, EXCEL_GLOB, ensure_processed_dir
from parse_fcm import parse_futures_table, parse_statement_date_from_filename


def build_futures_panel(raw_dir=None):
    raw = Path(raw_dir) if raw_dir is not None else RAW_DIR
    if not raw.is_dir():
        raise FileNotFoundError(f"Raw folder not found: {raw}")

    files = sorted(raw.glob(EXCEL_GLOB))
    all_dfs = []
    for f in files:
        stmt_date = parse_statement_date_from_filename(f)
        if stmt_date is None:
            continue
        try:
            df = parse_futures_table(f, stmt_date)
            if df is not None and not df.empty:
                all_dfs.append(df)
        except Exception:
            pass

    if not all_dfs:
        return pd.DataFrame()

    panel = pd.concat(all_dfs, ignore_index=True)
    panel = panel.sort_values(["statement_date", "bbg_id"]).reset_index(drop=True)

    dupes = panel.duplicated(subset=["statement_date", "bbg_id"], keep=False)
    if dupes.any():
        panel["_nna"] = (
            panel["w_fund"].notna().astype(int)
            + panel["w_benchmark"].notna().astype(int)
            + panel["prior_close_px"].notna().astype(int)
        )
        panel = panel.sort_values("_nna", ascending=False).drop_duplicates(
            subset=["statement_date", "bbg_id"], keep="first"
        )
        panel = panel.drop(columns=["_nna"])

    ensure_processed_dir()
    panel.to_parquet(FUTURES_PANEL_PATH, index=False)
    return panel

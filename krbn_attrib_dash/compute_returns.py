"""Compute daily contract returns from Prior Day Close Px."""
import pandas as pd
from config import FUTURES_PANEL_PATH, FUTURES_RETURNS_PATH, ensure_processed_dir

RET_MISSING_REASON = "FIRST_OBS_OR_NEW_CONTRACT"


def compute_contract_returns(panel_df=None):
    if panel_df is None:
        if not FUTURES_PANEL_PATH.exists():
            raise FileNotFoundError(f"Panel not found. Run build_panel first.")
        panel_df = pd.read_parquet(FUTURES_PANEL_PATH)

    pdf = panel_df[["statement_date", "bbg_id", "prior_close_px"]].copy()
    pdf = pdf.sort_values(["bbg_id", "statement_date"]).reset_index(drop=True)
    pdf["prior_close_px"] = pd.to_numeric(pdf["prior_close_px"], errors="coerce")
    pdf["ret"] = pdf.groupby("bbg_id")["prior_close_px"].transform(lambda x: x / x.shift(1) - 1)
    pdf["ret_missing_reason"] = pdf["ret"].isna().map(lambda na: RET_MISSING_REASON if na else None)

    ensure_processed_dir()
    pdf.to_parquet(FUTURES_RETURNS_PATH, index=False)
    return pdf

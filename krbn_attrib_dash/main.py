"""
KRBN LN Weight-Difference Attribution — single entry point.

Run this file to build data (if needed) and open the Dash app.
Excel files must be in: LN - KRBN ETC Position Snapshots (folder next to krbn_attrib_dash).
"""
from config import (
    RAW_DIR,
    FUTURES_PANEL_PATH,
    ATTRIB_DAILY_PATH,
    ATTRIB_DAILY_TOTALS_PATH,
)
from build_panel import build_futures_panel
from compute_returns import compute_contract_returns
from compute_attrib import compute_weight_diff_attrib
from dash_app import run_dash


def main():
    # Build panel, returns, and attribution if parquet files are missing
    if not ATTRIB_DAILY_PATH.exists() or not ATTRIB_DAILY_TOTALS_PATH.exists():
        if not RAW_DIR.is_dir():
            print(f"Raw data folder not found: {RAW_DIR}")
            print("Put Excel files in that folder and run again.")
            return
        print("Building panel from Excel files...")
        build_futures_panel()
        print("Computing returns...")
        compute_contract_returns()
        print("Computing attribution...")
        compute_weight_diff_attrib()
        print("Done. Opening Dash app.")
    else:
        print("Data found. Opening Dash app.")

    run_dash()


if __name__ == "__main__":
    main()

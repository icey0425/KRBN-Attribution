"""Weight-difference attribution: contrib = dw_lag * ret."""
import pandas as pd
from config import (
    FUTURES_PANEL_PATH,
    FUTURES_RETURNS_PATH,
    ATTRIB_DAILY_PATH,
    ATTRIB_DAILY_TOTALS_PATH,
    ensure_processed_dir,
)


def compute_weight_diff_attrib(panel_df=None, returns_df=None):
    if panel_df is None:
        panel_df = pd.read_parquet(FUTURES_PANEL_PATH)
    if returns_df is None:
        returns_df = pd.read_parquet(FUTURES_RETURNS_PATH)

    panel_df = panel_df.copy()
    returns_df = returns_df.copy()
    panel_df["statement_date"] = pd.to_datetime(panel_df["statement_date"]).dt.normalize()
    returns_df["statement_date"] = pd.to_datetime(returns_df["statement_date"]).dt.normalize()

    panel_cols = [c for c in ["statement_date", "bbg_id", "contract_label", "market_bucket", "w_benchmark", "w_fund", "prior_close_px"] if c in panel_df.columns]
    df = panel_df[panel_cols].merge(
        returns_df[["statement_date", "bbg_id", "ret", "ret_missing_reason"]],
        on=["statement_date", "bbg_id"],
        how="left",
    )
    df = df.sort_values(["bbg_id", "statement_date"]).reset_index(drop=True)
    df["dw"] = df["w_fund"].astype(float) - df["w_benchmark"].astype(float)
    df["dw_lag"] = df.groupby("bbg_id")["dw"].shift(1)
    df["contrib"] = df["dw_lag"] * df["ret"]

    daily = df.groupby("statement_date").agg(
        total_contrib=("contrib", "sum"),
        sum_w_fund=("w_fund", "sum"),
        sum_w_benchmark=("w_benchmark", "sum"),
    ).reset_index()

    # Missing-ret stats from returns file (source of truth), then join panel for weights
    # so we don't rely on merged df having the same keys
    ret_miss = returns_df.loc[returns_df["ret"].isna(), ["statement_date", "bbg_id"]].copy()
    ret_miss["statement_date"] = pd.to_datetime(ret_miss["statement_date"]).dt.normalize()
    if not ret_miss.empty:
        panel_weights = panel_df[["statement_date", "bbg_id", "w_fund", "w_benchmark"]].copy()
        panel_weights["statement_date"] = pd.to_datetime(panel_weights["statement_date"]).dt.normalize()
        miss_merged = ret_miss.merge(
            panel_weights,
            on=["statement_date", "bbg_id"],
            how="left",
        )
        w_f = miss_merged["w_fund"].abs().fillna(0)
        w_b = miss_merged["w_benchmark"].abs().fillna(0)
        miss_merged["_exposure"] = (w_f + w_b) / 2
        missing_ser = miss_merged.groupby("statement_date")["_exposure"].sum()
        missing_count_ser = miss_merged.groupby("statement_date").size()
    else:
        missing_ser = pd.Series(dtype=float)
        missing_count_ser = pd.Series(dtype=int)
    daily["missing_ret_abs_weight"] = daily["statement_date"].map(missing_ser).fillna(0)
    daily["missing_ret_count"] = daily["statement_date"].map(missing_count_ser).fillna(0).astype(int)

    ensure_processed_dir()
    df.to_parquet(ATTRIB_DAILY_PATH, index=False)
    daily.to_parquet(ATTRIB_DAILY_TOTALS_PATH, index=False)
    return df, daily

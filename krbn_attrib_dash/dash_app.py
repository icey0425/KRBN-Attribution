"""Dash app: date range, cumulative/daily attribution charts, contract and diagnostics tables."""
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go

from config import ATTRIB_DAILY_PATH, ATTRIB_DAILY_TOTALS_PATH, RAW_DIR
from build_panel import build_futures_panel
from compute_returns import compute_contract_returns
from compute_attrib import compute_weight_diff_attrib
from load_price_data import load_price_data


def load_data():
    if not ATTRIB_DAILY_PATH.exists() or not ATTRIB_DAILY_TOTALS_PATH.exists():
        return None, None, None
    attrib = pd.read_parquet(ATTRIB_DAILY_PATH)
    attrib["statement_date"] = pd.to_datetime(attrib["statement_date"]).dt.normalize()
    totals = pd.read_parquet(ATTRIB_DAILY_TOTALS_PATH)
    totals["statement_date"] = pd.to_datetime(totals["statement_date"]).dt.normalize()
    price_df = load_price_data()
    if price_df is not None and not price_df.empty:
        price_df["Date"] = pd.to_datetime(price_df["Date"]).dt.normalize()
    else:
        price_df = None
    return attrib, totals, price_df


def create_app(attrib_daily, attrib_totals, krbn_index_returns=None):
    external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]
    app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
    min_date = attrib_totals["statement_date"].min() if attrib_totals is not None and not attrib_totals.empty else None
    max_date = attrib_totals["statement_date"].max() if attrib_totals is not None and not attrib_totals.empty else None

    card_style = {
        "backgroundColor": "white",
        "padding": "20px 24px",
        "borderRadius": "8px",
        "border": "1px solid #e5e7eb",
        "marginBottom": "20px",
    }
    table_cell = {"textAlign": "center", "fontSize": "1.2rem", "padding": "10px 12px"}
    table_header = {"textAlign": "center", "fontWeight": "600", "backgroundColor": "#f8fafc", "fontSize": "1.2rem", "padding": "10px 12px", "borderBottom": "1px solid #e5e7eb"}
    zebra_and_total = [
        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
        {"if": {"filter_query": "{contract_label} = Total"}, "fontWeight": "bold", "backgroundColor": "white"},
    ]
    diagnostics_zebra = [{"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"}]

    container_style = {"maxWidth": "1280px", "margin": "0 auto", "padding": "24px 20px"}
    page_style = {
        "fontFamily": "'Segoe UI', system-ui, -apple-system, sans-serif",
        "fontSize": "14px",
        "backgroundColor": "#f1f5f9",
        "minHeight": "100vh",
        "width": "100%",
    }

    app.layout = html.Div(
        [
            html.Header(
                html.Div(
                    [
                        html.H2(
                            "KRBN LN Weight-Difference Attribution (v1)",
                            style={"margin": "0 0 12px 0", "fontSize": "1.9rem", "fontWeight": "700", "textAlign": "left"},
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Start Date", style={"fontSize": "0.85rem", "color": "#64748b", "marginBottom": "4px"}),
                                        dcc.DatePickerSingle(
                                            id="start-date",
                                            min_date_allowed=min_date,
                                            max_date_allowed=max_date,
                                            date=min_date,
                                            display_format="YYYY-MM-DD",
                                        ),
                                    ]
                                ),
                                html.Div(
                                    [
                                        html.Div("End Date", style={"fontSize": "0.85rem", "color": "#64748b", "marginBottom": "4px"}),
                                        dcc.DatePickerSingle(
                                            id="end-date",
                                            min_date_allowed=min_date,
                                            max_date_allowed=max_date,
                                            date=max_date,
                                            display_format="YYYY-MM-DD",
                                        ),
                                    ]
                                ),
                                html.Button("Recompute from raw", id="recompute-btn", n_clicks=0, style={"marginLeft": "12px"}),
                                html.Span(id="recompute-status", style={"marginLeft": "8px", "fontSize": "0.8125rem", "color": "#64748b"}),
                            ],
                            style={"display": "flex", "alignItems": "flex-end", "gap": "12px"},
                        ),
                    ],
                    style=container_style,
                ),
                style={
                    "width": "100%",
                    "backgroundColor": "white",
                    "borderBottom": "1px solid #e5e7eb",
                    "boxSizing": "border-box",
                },
            ),
            html.Main(
                html.Div(
                    [
                        html.Div(id="summary-section", style={"marginBottom": "20px"}),
                        html.Div(
                            [
                                html.Div(id="tracking-diff-display", style={"marginBottom": "12px"}),
                                dcc.Graph(id="growth-chart"),
                            ],
                            style={**card_style, "marginBottom": "20px"},
                        ),
                        html.Div(
                            [
                                html.Div(dcc.Graph(id="cumulative-attrib"), style={"flex": 1, "minWidth": 0}),
                                html.Div(dcc.Graph(id="daily-attrib"), style={"flex": 1, "minWidth": 0}),
                            ],
                            style={"display": "flex", "gap": "20px", "marginBottom": "20px"},
                        ),
                        html.Div(
                            [
                                html.H4("Contract-level period attribution", style={"margin": "0 0 12px 0", "fontSize": "1.25rem", "fontWeight": "700", "textAlign": "left"}),
                                dash_table.DataTable(
                                    id="contract-table",
                                    columns=[
                                        {"name": "Bbg ID", "id": "bbg_id"},
                                        {"name": "Contract", "id": "contract_label"},
                                        {"name": "Bucket", "id": "market_bucket"},
                                        {"name": "Contrib (bps)", "id": "contrib_bps"},
                                        {"name": "Avg |dw| (%)", "id": "avg_abs_dw_pct"},
                                        {"name": "Return (%)", "id": "period_ret_pct"},
                                        {"name": "", "id": "_is_total"},
                                    ],
                                    hidden_columns=["_is_total"],
                                    sort_action="native",
                                    sort_by=[{"column_id": "_is_total", "direction": "asc"}, {"column_id": "contrib_bps", "direction": "desc"}],
                                    page_size=20,
                                    style_table={"overflowX": "auto", "borderRadius": "6px", "overflow": "hidden"},
                                    style_cell=table_cell,
                                    style_header=table_header,
                                    style_data_conditional=zebra_and_total,
                                ),
                            ],
                            style=card_style,
                        ),
                        html.Div(
                            [
                                html.H4("Daily diagnostics", style={"margin": "0 0 12px 0", "fontSize": "1.25rem", "fontWeight": "700", "textAlign": "left"}),
                                dash_table.DataTable(
                                    id="diagnostics-table",
                                    columns=[
                                        {"name": "Date", "id": "statement_date"},
                                        {"name": "Total contrib (bps)", "id": "total_contrib_bps"},
                                        {"name": "Sum w_fund (%)", "id": "sum_w_fund"},
                                        {"name": "Sum w_benchmark (%)", "id": "sum_w_benchmark"},
                                    ],
                                    sort_action="native",
                                    page_size=15,
                                    style_table={"overflowX": "auto", "borderRadius": "6px", "overflow": "hidden"},
                                    style_cell=table_cell,
                                    style_header=table_header,
                                    style_data_conditional=diagnostics_zebra,
                                ),
                            ],
                            style=card_style,
                        ),
                        dcc.Store(id="store-attrib"),
                        dcc.Store(id="store-totals"),
                        dcc.Store(id="store-krbn-index"),
                    ],
                    style={**container_style, "paddingTop": "24px", "paddingBottom": "48px"},
                ),
                style={"width": "100%", "boxSizing": "border-box", "flex": 1},
            ),
        ],
        style={**page_style, "display": "flex", "flexDirection": "column"},
    )

    @app.callback(
        [Output("store-attrib", "data"), Output("store-totals", "data"), Output("store-krbn-index", "data")],
        Input("recompute-btn", "n_clicks"),
        State("store-attrib", "data"),
        prevent_initial_call=False,
    )
    def load_or_recompute(n_clicks, _prev):
        if n_clicks and n_clicks > 0 and RAW_DIR.is_dir():
            try:
                build_futures_panel(RAW_DIR)
                compute_contract_returns()
                compute_weight_diff_attrib()
                attrib, totals, price_df = load_data()
                ki_data = price_df.to_dict("records") if price_df is not None and not price_df.empty else None
                return (attrib.to_dict("records") if attrib is not None else None), (totals.to_dict("records") if totals is not None else None), ki_data
            except Exception:
                return dash.no_update, dash.no_update, dash.no_update
        attrib, totals, price_df = load_data()
        ki_data = price_df.to_dict("records") if price_df is not None and not price_df.empty else None
        return (attrib.to_dict("records") if attrib is not None else None), (totals.to_dict("records") if totals is not None else None), ki_data

    @app.callback(Output("recompute-status", "children"), Input("recompute-btn", "n_clicks"))
    def status(n_clicks):
        return "Recomputed." if (n_clicks and n_clicks > 0 and RAW_DIR.is_dir()) else ""

    @app.callback(
        Output("contract-table", "sort_by"),
        Input("contract-table", "sort_by"),
        prevent_initial_call=False,
    )
    def keep_total_last(sort_by):
        if not sort_by:
            return [{"column_id": "_is_total", "direction": "asc"}, {"column_id": "contrib_bps", "direction": "desc"}]
        existing = {s["column_id"] for s in sort_by}
        if "_is_total" in existing:
            return sort_by
        return [{"column_id": "_is_total", "direction": "asc"}] + sort_by

    @app.callback(
        [
            Output("summary-section", "children"),
            Output("tracking-diff-display", "children"),
            Output("growth-chart", "figure"),
            Output("cumulative-attrib", "figure"),
            Output("daily-attrib", "figure"),
            Output("contract-table", "data"),
            Output("diagnostics-table", "data"),
        ],
        [Input("store-totals", "data"), Input("store-attrib", "data"), Input("store-krbn-index", "data")],
        [Input("start-date", "date"), Input("end-date", "date")],
    )
    def update(totals_data, attrib_data, price_data, start_date, end_date):
        empty_fig = go.Figure().add_annotation(text="No data. Run pipeline or add parquet files.", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        no_price_fig = go.Figure().add_annotation(
            text="Put KRBN price.xlsx in: krbn_attrib_dash/data/raw/ OR krbn_attrib_dash/data/ OR the KRBN Attribution folder. Columns: Date | KRBN LN | GLCARBP Index. Then restart the app.",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=11)
        )
        if not totals_data or not attrib_data:
            return [], "", no_price_fig, empty_fig, empty_fig, [], []

        totals = pd.DataFrame(totals_data)
        attrib = pd.DataFrame(attrib_data)
        totals["statement_date"] = pd.to_datetime(totals["statement_date"])
        attrib["statement_date"] = pd.to_datetime(attrib["statement_date"])
        start = pd.Timestamp(start_date).normalize() if start_date else None
        end = pd.Timestamp(end_date).normalize() if end_date else None
        if start is not None and end is not None and start > end:
            start, end = end, start
        if start is not None:
            totals = totals[totals["statement_date"] >= start]
            attrib = attrib[attrib["statement_date"] >= start]
        if end is not None:
            totals = totals[totals["statement_date"] <= end]
            attrib = attrib[attrib["statement_date"] <= end]

        totals = totals.sort_values("statement_date").reset_index(drop=True)
        totals["cum_contrib"] = totals["total_contrib"].cumsum()
        totals["cum_contrib_bps"] = totals["cum_contrib"] * 10_000
        totals["total_contrib_bps"] = totals["total_contrib"] * 10_000

        cum_fig = px.line(totals, x="statement_date", y="cum_contrib_bps", title="Cumulative total attribution", labels={"cum_contrib_bps": "Cumulative contrib (bps)", "statement_date": "Date"})
        cum_fig.update_layout(template="plotly_white", hovermode="x unified", yaxis_title="Cumulative contrib (bps)", margin=dict(t=48, b=48, l=56, r=24), font=dict(size=12))
        daily_fig = px.bar(totals, x="statement_date", y="total_contrib_bps", title="Daily total attribution", labels={"total_contrib_bps": "Daily contrib (bps)", "statement_date": "Date"})
        daily_fig.update_layout(template="plotly_white", hovermode="x unified", yaxis_title="Daily contrib (bps)", margin=dict(t=48, b=48, l=56, r=24), font=dict(size=12))

        # Growth of $1 chart and tracking difference from KRBN price.xlsx (daily returns in %)
        growth_fig = no_price_fig
        tracking_diff_html = ""
        if price_data:
            df = pd.DataFrame(price_data)
            # Normalize date column (Date or statement_date)
            date_col = "Date" if "Date" in df.columns else ("statement_date" if "statement_date" in df.columns else None)
            if date_col is None:
                df = pd.DataFrame()
            else:
                df["Date"] = pd.to_datetime(df[date_col])
                if start is not None:
                    df = df[df["Date"] >= start]
                if end is not None:
                    df = df[df["Date"] <= end]
                df = df.sort_values("Date").reset_index(drop=True)
                # Support: fund_ret_pct/index_ret_pct (%), or krbn_ret/index_ret (decimal), or raw "KRBN LN"/"GLCARBP Index" (%)
                if "fund_ret_pct" in df.columns and "index_ret_pct" in df.columns:
                    df["fund_ret"] = pd.to_numeric(df["fund_ret_pct"], errors="coerce") / 100
                    df["index_ret"] = pd.to_numeric(df["index_ret_pct"], errors="coerce") / 100
                elif "krbn_ret" in df.columns and "index_ret" in df.columns:
                    df["fund_ret"] = pd.to_numeric(df["krbn_ret"], errors="coerce")
                    df["index_ret"] = pd.to_numeric(df["index_ret"], errors="coerce")
                elif "KRBN LN" in df.columns and "GLCARBP Index" in df.columns:
                    df["fund_ret"] = pd.to_numeric(df["KRBN LN"], errors="coerce") / 100
                    df["index_ret"] = pd.to_numeric(df["GLCARBP Index"], errors="coerce") / 100
                else:
                    df = pd.DataFrame()
                if "fund_ret" in df.columns and "index_ret" in df.columns:
                    df = df.dropna(subset=["fund_ret", "index_ret"])
            if not df.empty:
                df = df.copy()
                df["fund_growth"] = (1 + df["fund_ret"]).cumprod()
                df["index_growth"] = (1 + df["index_ret"]).cumprod()
                # Display cumulative return (%) = (growth - 1) * 100
                fund_cum_pct = (df["fund_growth"] - 1) * 100
                index_cum_pct = (df["index_growth"] - 1) * 100
                growth_fig = go.Figure()
                growth_fig.add_trace(go.Scatter(x=df["Date"], y=fund_cum_pct, mode="lines", name="KRBN LN NAV"))
                growth_fig.add_trace(go.Scatter(x=df["Date"], y=index_cum_pct, mode="lines", name="GLCARBP Index"))
                growth_fig.update_layout(
                    title="Cumulative return (%)",
                    template="plotly_white",
                    hovermode="x unified",
                    yaxis_title="Cumulative return (%)",
                    xaxis_title="Date",
                    margin=dict(t=48, b=48, l=56, r=24),
                    font=dict(size=12),
                )
                fund_total = df["fund_growth"].iloc[-1] - 1
                index_total = df["index_growth"].iloc[-1] - 1
                tracking_diff = fund_total - index_total
                tracking_diff_html = html.Div(
                    [
                        html.Div("Tracking Difference (Selected Period)", style={"fontSize": "0.875rem", "color": "#64748b", "marginBottom": "4px"}),
                        html.Div(f"KRBN LN – GLCARBP Index = {tracking_diff:.2%}", style={"fontSize": "18px", "fontWeight": "600"}),
                    ],
                )

        contract_summary = attrib.groupby(["bbg_id", "contract_label", "market_bucket"], dropna=False).agg(
            contrib_sum=("contrib", "sum"),
            avg_abs_dw=("dw", lambda s: s.abs().mean()),
            period_ret=("ret", lambda s: (1 + s.dropna()).prod() - 1),
        ).reset_index()
        contract_summary["contrib_bps"] = (contract_summary["contrib_sum"] * 10_000).round(2)
        contract_summary = contract_summary.sort_values("contrib_sum", key=abs, ascending=False).reset_index(drop=True)
        contract_summary["avg_abs_dw_pct"] = (contract_summary["avg_abs_dw"] * 100).round(2)
        contract_summary["_is_total"] = 0
        contract_summary["period_ret_pct"] = (contract_summary["period_ret"] * 100).round(2)
        total_contrib_bps = round(contract_summary["contrib_bps"].sum(), 2)
        total_row = pd.DataFrame([
            {"bbg_id": "", "contract_label": "Total", "market_bucket": "", "contrib_bps": "{:.2f}".format(total_contrib_bps), "avg_abs_dw_pct": "", "period_ret_pct": "", "_is_total": 1}
        ])
        contract_summary = pd.concat([
            contract_summary[["bbg_id", "contract_label", "market_bucket", "contrib_bps", "avg_abs_dw_pct", "period_ret_pct", "_is_total"]],
            total_row,
        ], ignore_index=True)
        contract_data = contract_summary.to_dict("records")

        diag = totals[["statement_date", "total_contrib", "sum_w_fund", "sum_w_benchmark"]].copy()
        diag["statement_date"] = diag["statement_date"].dt.strftime("%Y-%m-%d")
        diag["total_contrib_bps"] = (diag["total_contrib"] * 10_000).round(2)
        diag["sum_w_fund"] = (diag["sum_w_fund"] * 100).round(2)
        diag["sum_w_benchmark"] = (diag["sum_w_benchmark"] * 100).round(2)

        total_contrib_bps_period = round(attrib["contrib"].sum() * 10_000, 2)
        n_contracts = attrib["bbg_id"].nunique()
        n_days = totals["statement_date"].nunique()
        summary_cards = [
            html.Div(
                [
                    html.Div("Total contribution (bps)", style={"fontSize": "1.2rem", "color": "#64748b", "marginBottom": "6px", "fontWeight": "600"}),
                    html.Div(f"{total_contrib_bps_period:,.2f}", style={"fontSize": "1.75rem", "fontWeight": "700", "lineHeight": "1.1"}),
                ],
                style={**card_style, "flex": "1", "minWidth": "180px", "marginBottom": 0},
            ),
            html.Div(
                [
                    html.Div("Contracts", style={"fontSize": "1.2rem", "color": "#64748b", "marginBottom": "6px", "fontWeight": "600"}),
                    html.Div(str(n_contracts), style={"fontSize": "1.75rem", "fontWeight": "700", "lineHeight": "1.1"}),
                ],
                style={**card_style, "flex": "1", "minWidth": "180px", "marginBottom": 0},
            ),
            html.Div(
                [
                    html.Div("Days (selected period)", style={"fontSize": "1.2rem", "color": "#64748b", "marginBottom": "6px", "fontWeight": "600"}),
                    html.Div(str(n_days), style={"fontSize": "1.75rem", "fontWeight": "700", "lineHeight": "1.1"}),
                ],
                style={**card_style, "flex": "1", "minWidth": "180px", "marginBottom": 0},
            ),
        ]
        summary_children = html.Div(summary_cards, style={"display": "flex", "gap": "16px", "flexWrap": "wrap"})
        return summary_children, tracking_diff_html, growth_fig, cum_fig, daily_fig, contract_data, diag.to_dict("records")

    return app


def run_dash():
    attrib, totals, krbn_index = load_data()
    app = create_app(attrib, totals, krbn_index)
    app.run(debug=True, port=8050)

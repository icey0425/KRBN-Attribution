# KRBN LN Weight-Difference Attribution

Builds attribution from daily Excel FCM statements and opens a Dash app to view it.

## Setup

1. Put your Excel files in the folder **LN - KRBN ETC Position Snapshots** (same level as the `krbn_attrib_dash` folder).
2. Install dependencies once:
   ```bash
   pip install -r requirements.txt
   ```

## How to run

**One file runs everything:**

```bash
cd krbn_attrib_dash
python main.py
```

- If the data files don’t exist yet, it builds them from Excel, then opens the app.
- If they already exist, it just opens the app.
- In the app you can pick a date range and use “Recompute from raw” to rebuild from Excel.

Open the URL shown in the console (e.g. http://127.0.0.1:8050/).

## Methodology (what the model does)

This project performs a **contract-level active attribution** for KRBN LN versus its benchmark using FCM position snapshots.

### 1) Input data and panel construction

- Source files: daily Excel statements in `LN - KRBN ETC Position Snapshots`.
- For each file, `parse_fcm.py`:
  - extracts statement date from the filename (`MM-DD-YY`);
  - finds the Futures table and normalizes columns (contract, `bbg_id`, `% NAV`, `% Benchmark`, `Prior Day Close Px`, etc.);
  - converts `% NAV` and `% Benchmark` to decimal weights when needed.
- `build_panel.py` stacks all statement files into one panel and keeps one row per (`statement_date`, `bbg_id`).

Result: `futures_panel.parquet` with contract-level weights and prices by date.

### 2) Return calculation

`compute_returns.py` computes contract returns from `Prior Day Close Px`:

\[
ret_{i,t} = \frac{P_{i,t}}{P_{i,t-1}} - 1
\]

- grouped by `bbg_id` (contract identifier),
- sorted by statement date,
- first observation per contract has no prior point, so return is `NaN`.

Result: `futures_returns.parquet`.

### 3) Active weight-difference attribution

`compute_attrib.py` computes active weights and contribution as:

\[
dw_{i,t} = w^{fund}_{i,t} - w^{bench}_{i,t}
\]
\[
contrib_{i,t} = dw_{i,t-1} \times ret_{i,t}
\]

Important detail: the model uses **lagged active weight** (`dw_{t-1}`), not same-day `dw_t`, to reduce look-ahead bias (position at start of move times move).

Daily total attribution is:

\[
TotalContrib_t = \sum_i contrib_{i,t}
\]

The app also shows:
- cumulative attribution (sum of daily totals over the selected period),
- contract-level period contribution (sum of `contrib`),
- period return per contract (compounded from available daily returns),
- diagnostics such as sum of portfolio/benchmark weights.

Results:
- `attrib_daily.parquet` (contract-day level),
- `attrib_daily_totals.parquet` (daily aggregate).

### 4) Dashboard outputs

`dash_app.py` renders:
- summary cards (`Total contribution`, `Contracts`, `Days`),
- cumulative and daily attribution charts,
- contract contribution table,
- diagnostics table.

It can also load `KRBN price.xlsx` (`Date | KRBN LN | GLCARBP Index`) to show cumulative return lines and tracking difference over the selected range.

## Interpretation notes and assumptions

- Attribution is based on **reported statement snapshots**, not intraday positions.
- If statement dates are not continuous business days, one return step can span multiple calendar days.
- Missing contract returns (e.g., first observation / new contract) are excluded from contribution by construction (`NaN` return).
- This is a **weights-based active return decomposition**, not a full PnL decomposition (no explicit transaction cost, roll slippage, or fee model).
- Contribution units are decimal return; app tables/charts often convert to **bps** (`1 bps = 0.0001`).

## Data refresh behavior

- `python main.py`:
  - builds from raw Excel **only if** attribution parquet files are missing;
  - otherwise opens app using existing processed files.
- To force refresh from raw:
  - use **Recompute from raw** button in the app, or
  - delete files under `data/processed/` and run `main.py` again.

## Project layout (simple)

- **main.py** — run this; it builds data (if needed) and starts the Dash app.
- **config.py** — paths (raw folder, processed outputs).
- **parse_fcm.py** — read Futures table from Excel.
- **build_panel.py** — build the panel from all Excel files.
- **compute_returns.py** — daily returns from Prior Day Close Px.
- **compute_attrib.py** — weight-difference attribution.
- **dash_app.py** — Dash UI (charts and tables).
- **data/processed/** — parquet outputs (created when you run).

No `src/`, no package, no tests. Just run `main.py`.

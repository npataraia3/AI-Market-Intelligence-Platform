# AI Market Intelligence Platform

A free, local, portfolio-ready data application for collecting cryptocurrency market data, storing it in SQLite, monitoring significant moves, exposing an API, and visualizing results in a Dash dashboard.

## What it demonstrates

- Public API ingestion with safe timeouts, optional API-key support, retry on rate limits and a local on-disk cache
- SQLite data modelling and persistent time-series snapshots
- Flask backend with documented endpoints
- Dash and Plotly dashboard with Excel export of analysis and forecasts
- Explainable, rule-based market summaries (no paid LLM or API key required)
- Configurable 24-hour price-change alerts logged to console and shown in the dashboard
- Feature engineering: lagged prices, SMA, RSI, Bollinger Bands, VWAP, volume and Fear & Greed Index
- Leakage-aware rolling time-series validation for Linear Regression, ARIMA, XGBoost and a persistence (naive) baseline
- ML models predict next-day *returns* (not raw prices) with a divergence-guarded recursive path, so multi-step forecasts stay stable and internally consistent
- ARIMA order auto-selected by AIC over a small grid (with an ADF stationarity check) instead of a fixed `(1,1,1)`
- 95% prediction interval that widens with the horizon, stationarity (ADF) check, model comparison and signal-vs-buy-and-hold backtest
- Model interpretability via feature-importance charts
- Long-horizon forecasts that switch to an ARIMA baseline and grow uncertainty with the horizon
- Daily GitHub Actions ETL workflow and local MLflow experiment tracking
- Unit-test foundation

## Project layout

```text
app/          Flask backend, storage, data collection, monitoring, assistant
dashboard/    Dash dashboard
data/         Local SQLite database and API cache (ignored by Git)
notebooks/    EDA and methodology walkthrough (Jupyter)
tests/        Automated tests
```

## Setup

Python 3.11+ is required. The current project environment has been verified with Python 3.14.

> **Important:** all commands below must be run in **PowerShell**, not in the Python
> interactive console (the `>>>` / `...` prompt). Pasting PowerShell commands there causes
> `SyntaxError`. To open PowerShell: press **Win**, type `PowerShell`, and press Enter.

### Quick start (recommended) — no typing needed

1. Download the project folder.
2. Open **PowerShell**.
3. Change into the project folder, for example:
   ```powershell
   cd "C:\Users\ninop\Desktop\2026_Learning Data Science Basics (independently)\AI Market Intelligence Platform"
   ```
3. Run these one at a time:
   ```powershell
   .\setup.bat
   .\start.bat
   ```
   `setup.bat` installs dependencies (only needed the first time). `start.bat` launches
   both servers and opens the dashboard in your browser at **http://127.0.0.1:8501**.
4. To stop the servers later:
   ```powershell
   .\stop.bat
   ```

## Dashboard access

Once both servers are running, the interactive dashboard is available at:

- **Dashboard:** http://127.0.0.1:8501
- **API index:** http://127.0.0.1:8000/api
- **API health check:** http://127.0.0.1:8000/api/health

Everything runs locally on your machine — no account, API key or cloud deployment is required.

## API endpoints

- `POST /api/market/refresh` — fetch, save and evaluate current market data
- `GET /api/market/snapshots` — read stored observations
- `GET /api/alerts` — view significant-movement alerts
- `GET /api/assistant/summary?coin_id=bitcoin` — get transparent market commentary
- `GET /api/market/analysis/bitcoin?days=365` — features, model evaluation, forecast and backtest output
- `GET /api/market/analysis/bitcoin?days=365&forecast_days=90` — same, with a 90-day forecast horizon

## Results & limitations

Typical output from the rolling 90-day backtest on real Bitcoin data (illustrative — refresh
the data for current numbers):

| Model                | MAE (USD) | RMSE (USD) |
|----------------------|-----------|------------|
| Persistence (naive)  | 1,317     | 1,646      |
| XGBoost Regressor    | 1,717     | 2,002      |
| ARIMA (auto order)   | 2,663     | 3,073      |
| Linear Regression    | 17,889    | 19,611     |

Key takeaways:

- **The naive baseline wins.** Predicting "tomorrow = last price" beat every ML model on this
  90-day window. This is the expected and honest outcome for crypto — prices are noisy and
  close to a random walk, and it shows why every forecasting project must benchmark against a
  naive baseline before trusting a model.
- **Best feature is momentum.** XGBoost gain importances rank `sma_7`, `lag_1` and
  `fear_greed` highest — short-term momentum and sentiment, not volume or VWAP.
- **Interpretability is built in.** Feature-importance charts and rule-based market summaries
  explain *why* the model makes a call, without a paid LLM.
- **Long horizons are treated honestly.** Recursive tree/linear forecasts compound their own
  errors, so horizons beyond 90 days automatically switch to an ARIMA baseline and the 95%
  interval widens with `sqrt(horizon)`.
- **A flat point forecast is a feature, not a bug.** For a near-random-walk asset the best
  single estimate of the future price is "around today's price", so the forecast line stays
  flat while the 95% band widens with the horizon. Injecting artificial movement would make
  the report misleading; the widening band is where the uncertainty lives.

Limitations to be aware of:

- CoinGecko's public API is rate-limited; the app caches responses to `data/cache/` to stay
  within limits.
- Models are educational baselines, not trading signals. Never make financial decisions from
  this output.
- A 3-year forecast is an extrapolation of a few months of history — treat it as a scenario,
  not a prediction.
- ARIMA occasionally fails to converge on short samples and falls back to a recursive model.

## MLflow

Every analysis run is logged to a local SQLite tracking store (`mlflow.db`) and a
human-readable `logs/model_experiments.jsonl`:

```powershell
mlflow ui --backend-store-uri sqlite:///mlflow.db   # then open http://127.0.0.1:5000
```

## Notebook

A self-contained Jupyter notebook (`notebooks/analysis.ipynb`) walks through EDA, stationarity,
feature engineering, leakage-aware validation, the naive-baseline comparison, feature
importance and forecast uncertainty. Run in **PowerShell**:

```powershell
python -m pip install jupyter
jupyter notebook notebooks/analysis.ipynb
```

## Tests

Run in **PowerShell**:

```powershell
python -m pytest
```

## Free-data note

The application uses CoinGecko's public endpoint. A demo key is optional and can be placed in `.env`; never commit it. Public services can rate-limit requests, so refresh only when needed.

The dashboard also retrieves the free [Crypto Fear & Greed Index](https://alternative.me/crypto/fear-and-greed-index/) as an exogenous feature. MLflow is included for optional local experiment tracking; no cloud account or API key is required.

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
- Market Intelligence layer: market-regime detection, risk analytics, strategy backtesting with transaction costs, a transparent market score, data-quality checks, model-drift monitoring, cross-asset comparison and SHAP explainability
- Unit-test foundation

## Project layout

```text
app/          Flask backend, storage, data collection, monitoring, assistant
dashboard/    Dash workstation (dash_app.py shell, theme.py, components.py, pages.py, home.py)
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
- `GET /api/market/analysis/bitcoin?days=365` — features, model evaluation, forecast, backtest output, SHAP explanation and technical alerts
- `GET /api/market/analysis/bitcoin?days=365&forecast_days=90` — same, with a 90-day forecast horizon
- `GET /api/market/overview` — latest snapshot per asset, Fear & Greed and recent alerts
- `GET /api/market/comparison?days=90` — cross-asset performance, risk, correlation matrix and chart series
- `GET /api/market/regime/bitcoin?days=90` — rule-based + unsupervised market-regime detection
- `GET /api/market/risk/bitcoin?days=90` — volatility, max drawdown, VaR/CVaR, Sharpe/Sortino/Calmar
- `GET /api/market/backtest/bitcoin?days=365` — six strategies with transaction costs and equity curves
- `GET /api/market/score/bitcoin?days=90` — transparent 0–100 market score with per-component breakdown
- `GET /api/market/data-quality/bitcoin?days=90` — schema, completeness, duplicates, outliers, freshness and Fear & Greed checks
- `GET /api/monitoring/drift?coin_id=bitcoin` — model-performance drift detection over recorded runs

The full endpoint list is always available at **http://127.0.0.1:8000/api**.

## Market Intelligence

The dashboard opens on a **landing homepage** at `/` with a live hero (BTC/ETH price and 24h
movement, Fear & Greed sentiment, volatility and a relative-performance sparkline), an
editorial grid of feature cards and a section index — every card routes into the real page it
describes. From there it becomes a multi-page "market research workstation" with a sidebar +
top bar shell. The sidebar is driven by a single `PAGES` registry (one place to add, rename or
relink a page); canonical routes are `/overview`, `/markets`, `/forecast`, `/risk`,
`/strategy`, `/explainability`, `/alerts` and `/system`, with `/analysis`, `/strategy-lab`
and `/intelligence` kept as aliases for older links.
An **active asset** (selected in the top bar, default Bitcoin) carries through all pages,
and one `data-store` callback loads every endpoint in a single refresh:

- **Overview** — market-regime badge, market score, risk cards, the 24h alert feed, and
  relative-performance and correlation panels across all tracked assets.
- **Markets** — a leaderboard of every tracked asset (24h/7d/30d return, momentum,
  volatility, max drawdown, RSI, Sharpe), a correlation heatmap and a normalized-performance
  chart over the last 90 days.
- **Forecast Lab** — price/candles/forecast charts, leakage-aware model-comparison table and
  Excel export of the full analysis.
- **Risk Analytics** — annualized volatility, maximum drawdown with its historical series,
  historical vs parametric VaR, CVaR, and Sharpe/Sortino/Calmar ratios for the active asset.
- **Strategy Lab** — six-strategy backtest leaderboard with transaction costs and equity curves.
- **Explainability** — per-asset SHAP local explanation, global feature importance and the
  technical signal indicators feeding the forecast.
- **Signals & Alerts** — severity-filterable alert log, model-drift status and data-quality box.
- **System** — data freshness, stored-snapshot statistics, model-run history and API health.

### News intelligence

The **Overview** asset cards now carry a **LIVE NEWS** block on top of the price: the latest
relevant headline for that asset (with its real source and a relative timestamp), a
one-line impact hint (24h move + RSI), a **Read article** link that opens the actual article
in a new tab, and an **Analyze impact** link into the Forecast Lab for that coin.

- **Sources** — 5 legitimate public RSS feeds, **no API key needed**: CoinDesk,
  Cointelegraph, Decrypt, The Block and Bitcoin Magazine (`app/services/news.py`).
- **News API** — `GET /api/news?limit=30` returns the freshest articles across all feeds and
  `GET /api/news/<coin_id>?limit=5` filters to a specific asset (aliases like `btc`/`eth`
  supported). Every article is a real headline from a real publisher with its exact URL.
- **Tagging** — articles are matched to tracked coins with word-boundary matching, so a
  "Solidity" headline does not get tagged to Solana.
- **Reliability** — feeds are fetched with timeouts, cached in memory for 15 minutes and
  persisted to SQLite, so the dashboard still shows recent articles even if a feed is
  temporarily offline; when everything fails the page degrades gracefully with a
  "News unavailable." message instead of crashing.

Every `analysis` call also appends **technical alerts** (RSI overbought/oversold, Bollinger
crossings, volume anomalies, volatility spikes and market-regime changes) and records the run
into `logs/model_runs.jsonl`, which powers the **model-drift** indicator (recent 3-run MAE vs
a 5-run baseline; a ratio above 1.25 flags drift).

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

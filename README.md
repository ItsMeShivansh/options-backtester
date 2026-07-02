# Options Backtester

A simple Python backtester for running options trading strategies on historical NIFTY and BANKNIFTY data. It loads market data, simulates strategies tick by tick, and writes performance results to disk.

## Directory Structure

```text
options-backtester/
├── backtester/
│   ├── __init__.py
│   ├── data_ingestion.py
│   ├── evaluator.py
│   ├── portfolio.py
│   └── time_sync.py
├── strategies/
│   ├── strategy.py
│   ├── strategy_1.py
│   └── strategy_2.py
├── main.py
├── README.md
└── results/            # created after running the backtest
```

## What Each Module Does

- `main.py` starts the backtest and selects the strategy to run.
- `backtester/data_ingestion.py` reads futures and options CSVs from the raw data folders.
- `backtester/time_sync.py` aligns all market data to a 1-second timeline.
- `backtester/portfolio.py` tracks positions, trades, and PnL.
- `backtester/evaluator.py` builds the final result files and charts.
- `strategies/strategy.py` defines the base strategy interface and the straddle strategy.
- `strategies/strategy_1.py` contains the morning breakout strategy.
- `strategies/strategy_2.py` contains the opening range breakout strategy.

## How To Run

1. Install dependencies:

```bash
pip3 install -r requirements.txt
```

2. Run the backtest:

```bash
python3 main.py --strategy straddle
```

Before running, make sure the `allData/` folder is present at the project root and contains the expected raw data layout.

You can also try:

```bash
python3 main.py --strategy breakout
python3 main.py --strategy orb
```

## Results

After the run finishes, the generated files are saved in `results/`:

- `pnl_timeseries.csv` - second-by-second portfolio PnL
- `trade_log.csv` - all executed trades
- `summary_metrics.txt` - final summary statistics
- `cumulative_pnl_combined.png` - combined PnL chart
- `cumulative_pnl_per_underlier.png` - per-underlier PnL chart
- `daily_pnl.png` - daily PnL bar chart

Check the `results/` folder in the project root after the run.

## Adding More Strategies

1. Create a new file in `strategies/`, for example `strategies/my_strategy.py`.
2. Subclass `Strategy` from `strategies/strategy.py`.
3. Implement `on_tick(self, snapshot, current_positions)`.
4. If your strategy needs specific data, override `data_requirements()`.
5. Import the new strategy in `main.py` and add it to the `--strategy` choices.

Example skeleton:

```python
from strategies.strategy import Strategy, Order


class MyStrategy(Strategy):
	def on_tick(self, snapshot, current_positions):
		return []
```

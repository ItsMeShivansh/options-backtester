"""
Backtester

Ties together the modules that run the backtest on NIFTY and BANKNIFTY options.
"""

import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from backtester.data_ingestion import get_trading_dates, load_futures, load_options
from backtester.time_sync       import generate_snapshots
from strategies.strategy         import StraddleRollingStrategy
from strategies.strategy_1       import MorningBreakoutStrategy
from strategies.strategy_2       import OpeningRangeBreakoutStrategy
from backtester.portfolio        import Portfolio
from backtester.evaluator        import build_results


# Configuration

DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'allData')
UNDERLIERS = ['NIFTY', 'BANKNIFTY']


# Main loop

def run_backtest(strategy_name="straddle"):
    """
    Run the full backtest across every trading date and underlier.

    Flow per day per underlier:
        1.  data_ingestion  → load futures + filtered options
        2.  time_sync       → resample to 1-second snapshots
        3.  for each snapshot:
              strategy      → generate orders
              portfolio     → execute orders, record MTM
        4.  portfolio       → close all positions at day end

    After all days:
        5.  evaluator       → aggregate, compute metrics, save plots
    """
    trading_dates = get_trading_dates(DATA_DIR)
    print(f'\n{"=" * 55}')
    print(f'  BACKTESTER — {strategy_name.capitalize()} Strategy')
    print(f'{"=" * 55}')
    print(f'    Trading dates : {len(trading_dates)}  '
          f'({trading_dates[0]} → {trading_dates[-1]})')
    print(f'    Underliers    : {", ".join(UNDERLIERS)}')
    print(f'{"=" * 55}\n')

    # Create one portfolio and one strategy per underlier.
    portfolios = {ul: Portfolio(ul) for ul in UNDERLIERS}
    
    if strategy_name == "breakout":
        strategies = {ul: MorningBreakoutStrategy(ul) for ul in UNDERLIERS}
    elif strategy_name == "orb":
        strategies = {ul: OpeningRangeBreakoutStrategy(ul) for ul in UNDERLIERS}
    else:
        strategies = {ul: StraddleRollingStrategy(ul) for ul in UNDERLIERS}

    total_t0 = time.time()

    for day_num, trading_date in enumerate(trading_dates, start=1):
        day_t0 = time.time()
        print(f'  [{day_num:2d}/{len(trading_dates)}]  {trading_date}', end='  ')

        for underlier in UNDERLIERS:

            # Load data.
            strategy  = strategies[underlier]
            futures_df = load_futures(DATA_DIR, trading_date, underlier)
            options_dict, expiry = load_options(
                DATA_DIR, trading_date, underlier,
                requirements=strategy.data_requirements(),
            )

            if not options_dict:
                print(f'⚠ {underlier}: no options', end='  ')
                continue

            portfolio = portfolios[underlier]

            # Simulate tick by tick.
            last_snapshot = None

            for snapshot in generate_snapshots(
                futures_df, options_dict, trading_date
            ):
                # Strategy decides
                orders = strategy.on_tick(snapshot, portfolio.positions)

                # Execute orders.
                if orders:
                    portfolio.execute_orders(orders, snapshot.timestamp)

                # Record mark-to-market PnL.
                portfolio.mark_to_market(
                    snapshot.timestamp, snapshot.options_prices
                )

                last_snapshot = snapshot

            # Flatten positions at end of day.
            if last_snapshot and portfolio.positions:
                portfolio.close_all(
                    last_snapshot.timestamp,
                    last_snapshot.options_prices,
                )
                # Record the final flat state.
                portfolio.mark_to_market(
                    last_snapshot.timestamp,
                    last_snapshot.options_prices,
                )

        elapsed = time.time() - day_t0
        print(f'  ({elapsed:5.1f}s)')

    total_elapsed = time.time() - total_t0
    print(f'\n    ✅  Simulation finished in {total_elapsed:.0f}s\n')

    # Evaluate and generate outputs.
    print('    Generating results …\n')
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

    pnl_df, trade_df, metrics = build_results(
        list(portfolios.values()),
        output_dir=results_dir,
    )

    print(f'\n    All outputs saved to:  {results_dir}/')
    return pnl_df, trade_df, metrics


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Options Backtester")
    parser.add_argument('--strategy', type=str, default="straddle", 
                        choices=["straddle", "breakout", "orb"],
                        help="Choose the strategy to run (straddle, breakout, or orb)")
    args = parser.parse_args()
    
    run_backtest(strategy_name=args.strategy)

"""
Module 2: The Master Clock

Drives time forward second-by-second and ensures all data
(futures + options) is aligned to a common 1-second grid.
"""

import pandas as pd
import numpy as np
from collections import namedtuple


# A perfectly synchronized snapshot of the market at one second.
MarketSnapshot = namedtuple(
    'MarketSnapshot',
    ['timestamp', 'futures_price', 'options_prices'],
)


# Internal helpers

def _build_second_grid(trading_date):
    """
    Create the second grid for the trading day.
    NSE equity derivatives: 09:15:00  →  15:30:00  (22 501 seconds).
    """
    start_second = 9 * 3600 + 15 * 60
    end_second = 15 * 3600 + 30 * 60
    grid_seconds = np.arange(start_second, end_second + 1, dtype=np.int32)
    grid_timestamps = pd.Timestamp(f'{trading_date} 00:00:00') + pd.to_timedelta(
        grid_seconds, unit='s'
    )
    return grid_seconds, grid_timestamps


def _resample_to_grid(contract_ticks, grid_seconds):
    """
    Align scattered trade timestamps into a second-by-second grid.

    contract_ticks is a sequence of NumPy arrays with columns:
        Second, Price, Volume, OI

    Returns a contiguous 2D matrix of shape (seconds, contracts) containing
    only the forward-filled prices.
    """
    n_seconds = grid_seconds.size
    n_contracts = len(contract_ticks)

    matrix = np.empty((n_seconds, n_contracts), dtype=np.float64)
    matrix.fill(np.nan)

    for col_idx, ticks in enumerate(contract_ticks):
        if ticks.size == 0:
            continue

        tick_seconds = ticks[:, 0].astype(np.int32, copy=False)
        tick_prices = ticks[:, 1].astype(np.float64, copy=False)

        last_tick_idx = np.searchsorted(tick_seconds, grid_seconds, side='right') - 1
        valid = last_tick_idx >= 0
        if not np.any(valid):
            continue

        column = matrix[:, col_idx]
        column[valid] = tick_prices[last_tick_idx[valid]]

    return matrix


# Public API

def generate_snapshots(futures_df, options_dict, trading_date):
    """
    Yield one MarketSnapshot per second from 09:15:00 to 15:30:00.

    Parameters:
    futures_df   : NumPy array with columns [Second, Price, Volume, OI]
    options_dict : {(strike, opt_type): NumPy array}  - from data_ingestion
    trading_date : str 'YYYYMMDD'

    Yields:
    MarketSnapshot(timestamp, futures_price, options_prices)
        options_prices is a dict {(strike, opt_type): float}
        containing only options that have a valid (non-NaN) price.
    """
    grid_seconds, grid_timestamps = _build_second_grid(trading_date)

    # Pre-resample everything to the 1-second grid.
    futures_matrix = _resample_to_grid([futures_df], grid_seconds)
    futures_prices = futures_matrix[:, 0]

    option_items = list(options_dict.items())
    option_keys = [key for key, _ in option_items]
    option_ticks = [ticks for _, ticks in option_items]
    options_matrix = _resample_to_grid(option_ticks, grid_seconds)

    # Walk through every second using O(1) row indexing.
    for row_idx, ts in enumerate(grid_timestamps):
        fut_price = futures_prices[row_idx]

        # Skip seconds before the first futures tick
        if pd.isna(fut_price):
            continue

        # Collect option prices (exclude NaN → option hasn't traded yet)
        opt_prices = {}
        if options_matrix.size:
            row = options_matrix[row_idx]
            valid = ~np.isnan(row)
            opt_prices = {
                key: float(price)
                for key, price, keep in zip(option_keys, row, valid)
                if keep
            }

        yield MarketSnapshot(
            timestamp=ts,
            futures_price=float(fut_price),
            options_prices=opt_prices,
        )

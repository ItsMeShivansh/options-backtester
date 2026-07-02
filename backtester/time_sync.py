"""
Module 2: The Master Clock

Drives time forward second-by-second and ensures all data
(futures + options) is aligned to a common 1-second grid.
"""

import pandas as pd
from collections import namedtuple


# A perfectly synchronized snapshot of the market at one second.
MarketSnapshot = namedtuple(
    'MarketSnapshot',
    ['timestamp', 'futures_price', 'options_prices'],
)


# Internal helpers

def _build_second_grid(trading_date):
    """
    Create a DatetimeIndex covering every second of the trading day.
    NSE equity derivatives: 09:15:00  →  15:30:00  (22 501 seconds).
    """
    start = pd.Timestamp(f'{trading_date} 09:15:00')
    end   = pd.Timestamp(f'{trading_date} 15:30:00')
    return pd.date_range(start, end, freq='s')


def _resample_to_grid(df, grid):
    """
    Aligns scattered trade timestamps into a second-by-second grid. 
    If a second has no trade, it carries forward the last known price. 
    Timestamps before the first trade remain blank (NaN) to prevent look-ahead bias.
    """
    return (
        df
        .set_index('Datetime')['Price']
        .reindex(grid, method='ffill')
    )


# Public API

def generate_snapshots(futures_df, options_dict, trading_date):
    """
    Yield one MarketSnapshot per second from 09:15:00 to 15:30:00.

    Parameters:
    futures_df   : DataFrame with columns [Datetime, Price, …]
    options_dict : {(strike, opt_type): DataFrame}  - from data_ingestion
    trading_date : str 'YYYYMMDD'

    Yields:
    MarketSnapshot(timestamp, futures_price, options_prices)
        options_prices is a dict {(strike, opt_type): float}
        containing only options that have a valid (non-NaN) price.
    """
    grid = _build_second_grid(trading_date)

    # Pre-resample everything to the 1-second grid
    futures_series = _resample_to_grid(futures_df, grid)

    options_series = {}
    for key, df in options_dict.items():
        options_series[key] = _resample_to_grid(df, grid)

    # Walk through every second
    for ts in grid:
        fut_price = futures_series.loc[ts]

        # Skip seconds before the first futures tick
        if pd.isna(fut_price):
            continue

        # Collect option prices (exclude NaN → option hasn't traded yet)
        opt_prices = {}
        for key, series in options_series.items():
            price = series.loc[ts]
            if not pd.isna(price):
                opt_prices[key] = price

        yield MarketSnapshot(
            timestamp=ts,
            futures_price=fut_price,
            options_prices=opt_prices,
        )

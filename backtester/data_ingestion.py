"""
Module 1: 

Reads the raw folder/file structure, parses option filenames using regex,
filters to the closest-to-current expiry, and returns clean DataFrames.
"""

import os
import re
import pandas as pd
from datetime import datetime


# Filename parser

# Matches:  NIFTY  221103  17500  CE
#           GROUP1 GROUP2  GROUP3 GROUP4
INSTRUMENT_PATTERN = re.compile(
    r'^(NIFTY|BANKNIFTY|FINNIFTY)(\d{6})(\d+)(CE|PE)$'
)

def parse_instrument_name(filename_without_ext):
    """
    Break an instrument filename into its components.
    """
    match = INSTRUMENT_PATTERN.match(filename_without_ext)
    if not match:
        return None
    return (
        match.group(1),          # underlier
        match.group(2),          # expiry
        int(match.group(3)),     # strike 
        match.group(4),          # option_type
    )


# Expiry helper

def find_closest_expiry(trading_date_str, available_expiries):
    """
    From a set of YYMMDD expiry strings, return the one that is
    closest to (but >= ) the trading date.

    Parameters:
    trading_date_str : str - 'YYYYMMDD'
    available_expiries : set - {'221103', '221110', …}

    Returns:
    str or None - the chosen YYMMDD expiry
    """
    trading_dt = datetime.strptime(trading_date_str, '%Y%m%d')

    candidates = []
    for exp_str in available_expiries:
        exp_dt = datetime.strptime('20' + exp_str, '%Y%m%d')
        if exp_dt >= trading_dt:
            candidates.append((exp_dt, exp_str))

    if not candidates:
        return None
    return min(candidates, key=lambda pair: pair[0])[1]


# CSV reader (shared by futures and options)

def _read_tick_csv(filepath):
    """
    Read a headerless tick CSV with columns:
        Date, Time, Price, Volume, OI

    - When multiple ticks fall in the same second, keeps only the
      last traded price (standard practice).

    Returns a DataFrame with columns: Datetime, Price, Volume, OI.
    """
    df = pd.read_csv(
        filepath,
        header=None,
        names=['Date', 'Time', 'Price', 'Volume', 'OI'],
    )
    df['Datetime'] = pd.to_datetime(
        df['Date'].astype(str) + ' ' + df['Time']
    )
    # Last tick per second
    df = df.groupby('Datetime').last().reset_index()
    return df[['Datetime', 'Price', 'Volume', 'OI']]


# Public API

def get_trading_dates(data_dir):
    """Return a sorted list of trading-date strings (YYYYMMDD)."""
    dates = []
    for name in sorted(os.listdir(data_dir)):
        if name.startswith('NSE_') and os.path.isdir(os.path.join(data_dir, name)):
            dates.append(name.replace('NSE_', ''))
    return dates


def load_futures(data_dir, trading_date, underlier):
    """
    Load the near-month continuous futures file.

    Returns a DataFrame: [Datetime, Price, Volume, OI].
    """
    filepath = os.path.join(
        data_dir,
        f'NSE_{trading_date}',
        'Futures (Continuous)',
        f'{underlier}-I.csv',
    )
    return _read_tick_csv(filepath)


def load_options(data_dir, trading_date, underlier, requirements=None):
    """
    Load option contracts for one underlier on one date.

    The requirements dict (from Strategy.data_requirements()) controls
    which expiry gets loaded into RAM:

        {"expiry_filter": "closest"}   → nearest expiry >= trading date
        {"expiry_filter": "221103"}    → that exact expiry

    Returns
    options_dict : dict  - {(strike, option_type): DataFrame}
    expiry_str   : str   - the YYMMDD expiry that was selected (or None)
    """
    if requirements is None:
        requirements = {"expiry_filter": "closest"}

    expiry_filter = requirements.get("expiry_filter", "closest")

    options_dir = os.path.join(data_dir, f'NSE_{trading_date}', 'Options')

    # 1. Discover available expiries for this underlier
    available_expiries = set()
    for fname in os.listdir(options_dir):
        if not fname.endswith('.csv'):
            continue
        parsed = parse_instrument_name(fname[:-4])      # strip .csv
        if parsed and parsed[0] == underlier:
            available_expiries.add(parsed[1])            # expiry string

    # 2. Select the target expiry based on the strategy's requirement
    if expiry_filter == "closest":
        target_expiry = find_closest_expiry(trading_date, available_expiries)
    elif expiry_filter in available_expiries:
        target_expiry = expiry_filter               # exact match requested
    else:
        target_expiry = None

    if target_expiry is None:
        return {}, None

    # 3. Load only the files that match the target expiry
    options_dict = {}
    for fname in os.listdir(options_dir):
        if not fname.endswith('.csv'):
            continue
        parsed = parse_instrument_name(fname[:-4])
        if parsed is None:
            continue
        ul, expiry, strike, opt_type = parsed
        if ul != underlier or expiry != target_expiry:
            continue

        filepath = os.path.join(options_dir, fname)
        options_dict[(strike, opt_type)] = _read_tick_csv(filepath)

    return options_dict, target_expiry

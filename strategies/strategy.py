"""
Module 3: 

The decision logic

Receives a market snapshot + current positions and returns a list
of Order instructions.  To create a new strategy, subclass Strategy
and implement on_tick().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Tuple


# Data structures

@dataclass
class Order:
    """A single instruction to buy or sell one option contract."""
    instrument:  str    # human-readable, e.g. "NIFTY_18200_CE"
    strike:      int    # strike price
    option_type: str    # "CE" or "PE"
    side:        str    # "BUY" or "SELL"
    price:       float  # execution price


# Base class

class Strategy(ABC):
    """
    Abstract base class for trading strategies.

    To plug in a different strategy, create a subclass and implement
    on_tick().  Override data_requirements() to tell the data_ingestion.py
    exactly what data to load into RAM.
    """

    def data_requirements(self) -> dict:
        """
        Declare what market data this strategy needs.

        Supported keys:
        expiry_filter : str
            "closest"  - only the nearest expiry >= trading date (default)
            "YYMMDD"   - a specific expiry string, e.g. "221103"
        """
        return {"expiry_filter": "closest"}

    @abstractmethod
    def on_tick(self, snapshot, current_positions) -> List[Order]:
        """
        Called once per second with the current market state.

        Parameters:
        snapshot          : MarketSnapshot from time_sync
        current_positions : dict {(strike, opt_type): Position} from the Portfolio

        Returns:
        list[Order] - orders to execute
        """
        pass


# Concrete strategy: Straddle Rolling

class StraddleRollingStrategy(Strategy):
    """
    At every tick:
      1. Find the available strike closest to the current futures price.
      2. If we already hold CE + PE at that strike → do nothing.
      3. Otherwise → sell the old straddle, buy the new one.
    """

    def __init__(self, underlier: str):
        self.underlier = underlier

    def data_requirements(self) -> dict:
        """This strategy only needs the closest expiry."""
        return {"expiry_filter": "closest"}

    # core logic
    def on_tick(self, snapshot, current_positions) -> List[Order]:
        orders: List[Order] = []

        # Step 1: find strikes that have BOTH CE and PE available
        ce_strikes = set()
        pe_strikes = set()
        for (strike, opt_type) in snapshot.options_prices:
            if opt_type == 'CE':
                ce_strikes.add(strike)
            else:
                pe_strikes.add(strike)

        strikes_with_both = sorted(ce_strikes & pe_strikes)
        if not strikes_with_both:
            return orders                               # nothing tradeable

        # Step 2: closest strike to the futures price
        target_strike = min(
            strikes_with_both,
            key=lambda s: abs(s - snapshot.futures_price),
        )

        # Step 3: do we already hold the right straddle?
        held_strikes = set(key[0] for key in current_positions)
        if held_strikes == {target_strike}:
            return orders                               # no roll needed

        # Step 4: roll — sell old, buy new ---

        # Sell every existing position
        for (strike, opt_type) in list(current_positions.keys()):
            price = snapshot.options_prices.get((strike, opt_type))
            if price is not None:
                orders.append(Order(
                    instrument=f'{self.underlier}_{strike}_{opt_type}',
                    strike=strike,
                    option_type=opt_type,
                    side='SELL',
                    price=price,
                ))

        # Buy the new CE + PE
        for opt_type in ['CE', 'PE']:
            price = snapshot.options_prices.get((target_strike, opt_type))
            if price is not None:
                orders.append(Order(
                    instrument=f'{self.underlier}_{target_strike}_{opt_type}',
                    strike=target_strike,
                    option_type=opt_type,
                    side='BUY',
                    price=price,
                ))

        return orders

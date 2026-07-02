"""
Module 4: 

Receives orders from the Strategy, executes them, maintains a ledger
of open positions, and computes the Mark-to-Market PnL at every second.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple


# Data structures

@dataclass
class Position:
    """One open position in an option contract."""
    instrument:  str        # e.g. "NIFTY_18200_CE"
    strike:      int
    option_type: str        # "CE" / "PE"
    entry_price: float
    entry_time:  object     # pd.Timestamp


@dataclass
class TradeRecord:
    """One row in the trade log."""
    timestamp:   object
    underlier:   str
    instrument:  str
    strike:      int
    option_type: str
    side:        str        # "BUY" / "SELL"
    price:       float
    pnl:         float      # 0 for BUY; realised P&L for SELL


@dataclass
class PnLSnapshot:
    """The portfolio state at one specific second."""
    timestamp:       object
    mtm_pnl:         float   # realised + unrealised
    realized_pnl:    float
    unrealized_pnl:  float
    positions_held:  str     # comma-separated names, or "FLAT"


# Portfolio

class Portfolio:
    """
    Manages positions and PnL tracking for a single underlier.

    The same Portfolio instance is reused across trading days so that
    cumulative PnL is tracked automatically.
    """

    def __init__(self, underlier: str):
        self.underlier   = underlier
        self.positions:    Dict[Tuple[int, str], Position] = {}
        self.realized_pnl = 0.0
        self.trade_log:    List[TradeRecord] = []
        self.pnl_log:      List[PnLSnapshot] = []

    # ----- order execution -----

    def execute_orders(self, orders, timestamp):
        """
        Process a list of Order objects.

        BUY  → open a new position, record entry price.
        SELL → close the position, realise PnL = sell − entry.
        """
        for order in orders:
            key = (order.strike, order.option_type)

            if order.side == 'SELL' and key in self.positions:
                pos = self.positions.pop(key)
                trade_pnl = order.price - pos.entry_price
                self.realized_pnl += trade_pnl

                self.trade_log.append(TradeRecord(
                    timestamp=timestamp,
                    underlier=self.underlier,
                    instrument=order.instrument,
                    strike=order.strike,
                    option_type=order.option_type,
                    side='SELL',
                    price=order.price,
                    pnl=trade_pnl,
                ))

            elif order.side == 'BUY':
                self.positions[key] = Position(
                    instrument=order.instrument,
                    strike=order.strike,
                    option_type=order.option_type,
                    entry_price=order.price,
                    entry_time=timestamp,
                )

                self.trade_log.append(TradeRecord(
                    timestamp=timestamp,
                    underlier=self.underlier,
                    instrument=order.instrument,
                    strike=order.strike,
                    option_type=order.option_type,
                    side='BUY',
                    price=order.price,
                    pnl=0.0,
                ))

    # ----- mark-to-market -----

    def mark_to_market(self, timestamp, options_prices):
        """
        Compute the current MTM PnL and append to the log.

        MTM = realised_pnl  +  Σ (current_price - entry_price)
                                 for each open position
        """
        unrealized = 0.0
        held = []

        for key, pos in self.positions.items():
            current_price = options_prices.get(key)
            if current_price is not None:
                unrealized += current_price - pos.entry_price
            held.append(pos.instrument)

        self.pnl_log.append(PnLSnapshot(
            timestamp=timestamp,
            mtm_pnl=self.realized_pnl + unrealized,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized,
            positions_held=', '.join(held) if held else 'FLAT',
        ))

    # ----- end-of-day liquidation -----

    def close_all(self, timestamp, options_prices):
        """
        Close every open position at the latest available prices.
        Called at the end of each trading day.
        """
        
        from strategies.strategy import Order

        orders = []
        for key, pos in list(self.positions.items()):
            price = options_prices.get(key)
            if price is not None:
                orders.append(Order(
                    instrument=pos.instrument,
                    strike=pos.strike,
                    option_type=pos.option_type,
                    side='SELL',
                    price=price,
                ))

        if orders:
            self.execute_orders(orders, timestamp)

import datetime
from typing import List
from strategies.strategy import Strategy, Order


# Concrete strategy: Morning Breakout

class MorningBreakoutStrategy(Strategy):
    """
    Morning breakout strategy.

    1. At 09:15, record the futures open.
    2. At 09:30, buy ATM CE if futures are above the open, otherwise buy ATM PE.
    3. Hold the position until end of day.
    """

    def __init__(self, underlier: str):
        self.underlier = underlier
        self.current_date = None
        self.open_price = None
        self.has_traded = False

    def data_requirements(self) -> dict:
        """This strategy only needs the closest expiry."""
        return {"expiry_filter": "closest"}

    def on_tick(self, snapshot, current_positions) -> List[Order]:
        orders: List[Order] = []

        # Reset state for a new trading day.
        trade_date = snapshot.timestamp.date()
        if self.current_date != trade_date:
            self.current_date = trade_date
            self.open_price = None
            self.has_traded = False

        current_time = snapshot.timestamp.time()

        # Record the futures open at 09:15.
        if current_time == datetime.time(9, 15, 0):
            self.open_price = snapshot.futures_price

        # Make the directional trade at 09:30.
        if current_time == datetime.time(9, 30, 0) and not self.has_traded and self.open_price is not None:
            self.has_traded = True

            # Find strikes available for both CE and PE.
            ce_strikes = set()
            pe_strikes = set()
            for (strike, opt_type) in snapshot.options_prices:
                if opt_type == 'CE':
                    ce_strikes.add(strike)
                else:
                    pe_strikes.add(strike)

            strikes_with_both = sorted(ce_strikes & pe_strikes)
            if not strikes_with_both:
                return orders

            # Choose the ATM strike.
            target_strike = min(
                strikes_with_both,
                key=lambda s: abs(s - snapshot.futures_price)
            )

            # Select the option side based on the opening range move.
            if snapshot.futures_price > self.open_price:
                opt_type = 'CE'
            else:
                opt_type = 'PE'

            price = snapshot.options_prices.get((target_strike, opt_type))
            if price is not None:
                orders.append(Order(
                    instrument=f'{self.underlier}_{target_strike}_{opt_type}',
                    strike=target_strike,
                    option_type=opt_type,
                    side='BUY',
                    price=price
                ))

        # Hold the position until EOD.
        
        return orders

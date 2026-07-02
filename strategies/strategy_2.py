import datetime
from typing import List
from strategies.strategy import Strategy, Order


# Concrete strategy: Opening Range Breakout

class OpeningRangeBreakoutStrategy(Strategy):
    """
    Opening range breakout strategy.

    1. From 09:15 to 10:00, track the highest and lowest futures price.
    2. After 10:00, buy ATM CE on an upside breakout or ATM PE on a downside breakout.
    3. Limit to one trade per day.
    4. Hold the position until end of day.
    """

    def __init__(self, underlier: str):
        self.underlier = underlier
        self.current_date = None
        self.highest_price = -float('inf')
        self.lowest_price = float('inf')
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
            self.highest_price = -float('inf')
            self.lowest_price = float('inf')
            self.has_traded = False

        current_time = snapshot.timestamp.time()

        # Track the opening range until 10:00.
        if current_time <= datetime.time(10, 0, 0):
            if snapshot.futures_price > self.highest_price:
                self.highest_price = snapshot.futures_price
            if snapshot.futures_price < self.lowest_price:
                self.lowest_price = snapshot.futures_price

        # Look for a breakout after 10:00.
        elif current_time > datetime.time(10, 0, 0) and not self.has_traded:

            # Check for a breakout beyond the morning range.
            is_breakout_up = snapshot.futures_price > self.highest_price
            is_breakout_down = snapshot.futures_price < self.lowest_price

            if is_breakout_up or is_breakout_down:
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

                # Select the option side based on the breakout direction.
                if is_breakout_up:
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

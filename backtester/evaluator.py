"""
Module 5: 

Wakes up after the simulation finishes.  Reads the PnL and trade logs
produced by the Broker, computes summary metrics, and generates plots.
"""

import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')                       # headless — no GUI needed
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# Public entry point

def build_results(portfolios, output_dir='results'):
    """
    Aggregate all portfolio data, compute metrics, save CSVs and plots.

    Parameters:
    portfolios : list[Portfolio]
    output_dir : str - folder to write into (created if absent)

    Returns:
    (pnl_df, trade_df, metrics)
    """
    os.makedirs(output_dir, exist_ok=True)

    # ---- assemble DataFrames ----
    pnl_rows   = []
    trade_rows = []

    for pf in portfolios:
        for rec in pf.pnl_log:
            pnl_rows.append({
                'Timestamp':      rec.timestamp,
                'Underlier':      pf.underlier,
                'MTM_PnL':        rec.mtm_pnl,
                'Realized_PnL':   rec.realized_pnl,
                'Unrealized_PnL': rec.unrealized_pnl,
                'Positions':      rec.positions_held,
            })
        for tr in pf.trade_log:
            trade_rows.append({
                'Timestamp':   tr.timestamp,
                'Underlier':   tr.underlier,
                'Instrument':  tr.instrument,
                'Strike':      tr.strike,
                'Option_Type': tr.option_type,
                'Side':        tr.side,
                'Price':       tr.price,
                'PnL':         tr.pnl,
            })

    pnl_df   = pd.DataFrame(pnl_rows)
    trade_df = pd.DataFrame(trade_rows)

    # ---- save CSVs ----
    pnl_df.to_csv(os.path.join(output_dir, 'pnl_timeseries.csv'), index=False)
    trade_df.to_csv(os.path.join(output_dir, 'trade_log.csv'), index=False)
    print('  ✓ Saved pnl_timeseries.csv')
    print('  ✓ Saved trade_log.csv')

    # ---- metrics ----
    metrics = _compute_metrics(pnl_df, trade_df)
    _save_metrics(metrics, output_dir)

    # ---- plots ----
    _plot_cumulative_combined(pnl_df, output_dir)
    _plot_cumulative_per_underlier(pnl_df, output_dir)
    _plot_daily_bar(pnl_df, output_dir)

    return pnl_df, trade_df, metrics


# Metrics

def _compute_metrics(pnl_df, trade_df):
    """Return an ordered dict of summary statistics."""
    metrics = {}

    # Combined final PnL
    final_combined = pnl_df.groupby('Underlier')['MTM_PnL'].last().sum()
    metrics['Combined Final PnL'] = round(final_combined, 2)

    for ul in sorted(pnl_df['Underlier'].unique()):
        ul_pnl    = pnl_df[pnl_df['Underlier'] == ul]
        ul_trades = trade_df[trade_df['Underlier'] == ul]

        final_pnl    = ul_pnl['MTM_PnL'].iloc[-1]
        total_trades  = len(ul_trades)
        sell_count    = len(ul_trades[ul_trades['Side'] == 'SELL'])

        # Daily PnL series
        tmp = ul_pnl.copy()
        tmp['Date'] = tmp['Timestamp'].dt.date
        eod = tmp.groupby('Date')['MTM_PnL'].last()
        daily = eod.diff()
        daily.iloc[0] = eod.iloc[0]

        # Max drawdown (intra-tick)
        cum      = ul_pnl['MTM_PnL']
        peak     = cum.cummax()
        max_dd   = (cum - peak).min()

        metrics[f'{ul} Final PnL']       = round(final_pnl, 2)
        metrics[f'{ul} Total Trades']    = total_trades
        metrics[f'{ul} Rolls (sells)']   = sell_count
        metrics[f'{ul} Best Day PnL']    = round(daily.max(), 2)
        metrics[f'{ul} Worst Day PnL']   = round(daily.min(), 2)
        metrics[f'{ul} Max Drawdown']    = round(max_dd, 2)

    return metrics


def _save_metrics(metrics, output_dir):
    """Print and persist summary metrics."""
    filepath = os.path.join(output_dir, 'summary_metrics.txt')
    lines = []
    lines.append('=' * 55)
    lines.append('  BACKTEST RESULTS — SUMMARY')
    lines.append('=' * 55)
    for k, v in metrics.items():
        lines.append(f'  {k:<30s} : {v}')
    lines.append('=' * 55)

    text = '\n'.join(lines)
    with open(filepath, 'w') as f:
        f.write(text + '\n')

    print('\n' + text + '\n')
    print(f'  ✓ Saved summary_metrics.txt')


# Plots

_COLORS = {
    'NIFTY':     '#4CAF50',
    'BANKNIFTY': '#FF9800',
    'combined':  '#2196F3',
}


def _plot_cumulative_combined(pnl_df, output_dir):
    """Line chart: combined (NIFTY + BANKNIFTY) cumulative MTM PnL."""
    pivot = pnl_df.pivot_table(
        index='Timestamp', columns='Underlier',
        values='MTM_PnL', aggfunc='last',
    ).ffill()
    combined = pivot.sum(axis=1)

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.plot(combined.index, combined.values,
            color=_COLORS['combined'], linewidth=0.6, label='Combined MTM PnL')
    ax.axhline(0, color='grey', linewidth=0.4, linestyle='--')
    ax.fill_between(combined.index, combined.values, 0,
                    where=combined.values >= 0, alpha=0.12, color='green')
    ax.fill_between(combined.index, combined.values, 0,
                    where=combined.values < 0, alpha=0.12, color='red')
    ax.set_title('Combined Cumulative MTM PnL  (NIFTY + BANKNIFTY)', fontsize=13)
    ax.set_ylabel('PnL (₹)')
    ax.legend()
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'cumulative_pnl_combined.png'), dpi=150)
    plt.close(fig)
    print('  ✓ Saved cumulative_pnl_combined.png')


def _plot_cumulative_per_underlier(pnl_df, output_dir):
    """Separate cumulative PnL subplots for each underlier."""
    underliers = sorted(pnl_df['Underlier'].unique())
    fig, axes = plt.subplots(
        len(underliers), 1,
        figsize=(16, 4.5 * len(underliers)),
        sharex=False,
    )
    if len(underliers) == 1:
        axes = [axes]

    for ax, ul in zip(axes, underliers):
        data  = pnl_df[pnl_df['Underlier'] == ul]
        color = _COLORS.get(ul, '#2196F3')

        ax.plot(data['Timestamp'], data['MTM_PnL'],
                color=color, linewidth=0.6)
        ax.axhline(0, color='grey', linewidth=0.4, linestyle='--')
        ax.fill_between(
            data['Timestamp'], data['MTM_PnL'], 0,
            where=data['MTM_PnL'] >= 0, alpha=0.12, color='green')
        ax.fill_between(
            data['Timestamp'], data['MTM_PnL'], 0,
            where=data['MTM_PnL'] < 0, alpha=0.12, color='red')
        ax.set_title(f'{ul} — Cumulative MTM PnL', fontsize=12)
        ax.set_ylabel('PnL (₹)')
        ax.grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'cumulative_pnl_per_underlier.png'), dpi=150)
    plt.close(fig)
    print('  ✓ Saved cumulative_pnl_per_underlier.png')


def _plot_daily_bar(pnl_df, output_dir):
    """Bar chart: end-of-day PnL per underlier."""
    tmp = pnl_df.copy()
    tmp['Date'] = tmp['Timestamp'].dt.date
    eod = tmp.groupby(['Date', 'Underlier'])['MTM_PnL'].last().unstack(fill_value=0)

    daily_change = eod.diff()
    daily_change.iloc[0] = eod.iloc[0]

    fig, ax = plt.subplots(figsize=(14, 5))
    bar_colors = [_COLORS.get(c, '#2196F3') for c in daily_change.columns]
    daily_change.plot(kind='bar', ax=ax, width=0.7, color=bar_colors)

    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_title('Daily PnL by Underlier', fontsize=13)
    ax.set_xlabel('Date')
    ax.set_ylabel('PnL (₹)')
    ax.legend(title='Underlier')
    ax.grid(True, alpha=0.25, axis='y')
    plt.xticks(rotation=45, ha='right')
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'daily_pnl.png'), dpi=150)
    plt.close(fig)
    print('  ✓ Saved daily_pnl.png')

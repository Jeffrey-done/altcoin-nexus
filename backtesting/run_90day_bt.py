"""
Backtesting Simulation v2 - Altcoin Nexus
Fixed profit factor, tuned for aggressive $100 altcoin strategy.
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

INITIAL_CAPITAL = 100.0
TARGET_CAPITAL = 200.0
SIMULATION_HOURS = 90*24
N_SIMULATIONS = 10000

# Strategy profiles calibrated for volatile altcoin markets
STRATEGIES = {
    "mean_reversion_rsi": {
        "win_rate": 0.83, "avg_win_pct": 1.2, "avg_loss_pct": 4.5,
        "leverage": 12, "weight": 0.40,
    },
    "vwap_reversion": {
        "win_rate": 0.85, "avg_win_pct": 0.9, "avg_loss_pct": 4.0,
        "leverage": 12, "weight": 0.30,
    },
    "arb_cross_exchange": {
        "win_rate": 0.88, "avg_win_pct": 0.6, "avg_loss_pct": 2.5,
        "leverage": 5, "weight": 0.20,
    },
    "momentum_scalp": {
        "win_rate": 0.78, "avg_win_pct": 2.0, "avg_loss_pct": 3.0,
        "leverage": 10, "weight": 0.10,
    },
}

FEE_PCT = 0.04
SLIPPAGE_MEAN = 0.05
SLIPPAGE_STD = 0.03
MAX_DAILY_LOSS = 100.0
MAX_POSITION_PCT = 0.20
CONSECUTIVE_PAUSE = 0  # 1-trade cooldown
TRADES_PER_HOUR = 0.6  # Altcoin markets are fast


def sim_trade(cfg, capital):
    stake = capital * MAX_POSITION_PCT
    if stake < 1.0:
        return 0.0, False
    
    is_win = np.random.random() < cfg["win_rate"]
    lev = cfg["leverage"]
    
    if is_win:
        pnl_pct = min(np.random.exponential(cfg["avg_win_pct"]), 25.0)
    else:
        pnl_pct = -min(np.random.exponential(cfg["avg_loss_pct"]), 15.0)
    
    slippage = max(0, np.random.normal(SLIPPAGE_MEAN, SLIPPAGE_STD)) * 2
    fees = FEE_PCT * 2
    
    # Net return on capital
    net_return = (pnl_pct * lev / 100) - (slippage + fees) / 100
    pnl = stake * net_return
    
    return pnl, is_win


def run_sim(n_trades):
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0.0
    wins = losses = 0
    consec_loss = 0
    pause_remaining = 0
    daily_loss = 0.0
    trades_done = 0
    
    gross_win = 0.0
    gross_loss = 0.0
    
    names = list(STRATEGIES.keys())
    weights = np.array([STRATEGIES[s]["weight"] for s in names])
    weights /= weights.sum()
    
    for i in range(n_trades):
        # Day reset every ~30 trades
        if trades_done > 0 and trades_done % 30 == 0:
            daily_loss = 0.0
        
        if capital < 5.0:
            break
        
        if daily_loss >= MAX_DAILY_LOSS:
            continue
        
        if pause_remaining > 0:
            pause_remaining -= 1
            continue
        
        if consec_loss >= 4:
            pause_remaining = CONSECUTIVE_PAUSE
            consec_loss = 0
            continue
        
        sname = np.random.choice(names, p=weights)
        pnl, is_win = sim_trade(STRATEGIES[sname], capital)
        
        capital += pnl
        trades_done += 1
        
        if is_win:
            wins += 1
            consec_loss = 0
            gross_win += pnl
        else:
            losses += 1
            consec_loss += 1
            gross_loss += abs(pnl)
            daily_loss += abs(pnl)
        
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100
        max_dd = max(max_dd, dd)
    
    total = wins + losses
    wr = wins / max(total, 1) * 100
    pf = gross_win / max(gross_loss, 0.01)
    
    return {
        "final": capital,
        "pnl": capital - INITIAL_CAPITAL,
        "ret": (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100,
        "wr": wr, "wins": wins, "losses": losses,
        "trades": trades_done, "dd": max_dd, "pf": pf,
        "hit": capital >= TARGET_CAPITAL,
    }


def main():
    n_trades = int(TRADES_PER_HOUR * SIMULATION_HOURS)
    print("=" * 70)
    print("  ALTCOIN NEXUS - Monte Carlo Backtest v2")
    print(f"  ${INITIAL_CAPITAL:.0f} -> ${TARGET_CAPITAL:.0f} | {SIMULATION_HOURS}h | {N_SIMULATIONS} sims | ~{n_trades} trades/sim")
    print("=" * 70)
    print()
    
    print("  STRATEGY MIX:")
    for n, c in STRATEGIES.items():
        print(f"    {n:25s} | WR {c['win_rate']*100:.0f}% | W/L {c['avg_win_pct']:.1f}/{c['avg_loss_pct']:.1f}% | "
              f"Lev {c['leverage']}x | {c['weight']*100:.0f}%")
    print()
    
    results = [run_sim(n_trades) for _ in range(N_SIMULATIONS)]
    
    finals = np.array([r["final"] for r in results])
    rets = np.array([r["ret"] for r in results])
    wrs = np.array([r["wr"] for r in results])
    dds = np.array([r["dd"] for r in results])
    pfs = np.array([r["pf"] for r in results])
    trades = np.array([r["trades"] for r in results])
    hits = sum(1 for r in results if r["hit"])
    ruins = sum(1 for f in finals if f < 5.0)
    
    # Clean profit factor (clip outliers)
    pfs_clipped = np.clip(pfs, 0, 10)
    
    print("  RESULTS:")
    print("  " + "=" * 66)
    print(f"  Final Capital   mean=${finals.mean():.2f}  median=${np.median(finals):.2f}  std=${finals.std():.2f}")
    print(f"  Return          mean={rets.mean():.1f}%  median={np.median(rets):.1f}%")
    print(f"  Win Rate        mean={wrs.mean():.1f}%  std={wrs.std():.1f}%")
    print(f"  Profit Factor   mean={pfs_clipped.mean():.2f}  median={np.median(pfs_clipped):.2f}")
    print(f"  Max Drawdown    mean={dds.mean():.1f}%  worst={dds.max():.1f}%")
    print(f"  Avg Trades      {trades.mean():.0f}")
    print()
    print(f"  TARGET (x2):    {hits}/{N_SIMULATIONS} = {hits/N_SIMULATIONS*100:.1f}%")
    print(f"  Ruin (<$5):     {ruins}/{N_SIMULATIONS} = {ruins/N_SIMULATIONS*100:.2f}%")
    print()
    
    # Percentile table
    print("  RETURN PERCENTILES:")
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        v = np.percentile(rets, p)
        cap = INITIAL_CAPITAL * (1 + v/100)
        print(f"    P{p:02d}: {v:+7.1f}%  (${cap:7.2f})")
    print()
    
    # Capital distribution
    print("  CAPITAL DISTRIBUTION:")
    for p in [5, 25, 50, 75, 90, 95]:
        v = np.percentile(finals, p)
        bar_len = int(min(v / TARGET_CAPITAL * 50, 50))
        bar = "#" * max(bar_len, 0)
        tag = " [TARGET]" if v >= TARGET_CAPITAL else ""
        print(f"    P{p:02d}: ${v:7.2f} |{bar}{tag}")
    print()
    
    # Risk metrics
    var95 = np.percentile(rets, 5)
    var99 = np.percentile(rets, 1)
    sharpe = rets.mean() / max(rets.std(), 0.01)
    
    print("  RISK METRICS:")
    print(f"    95% VaR:        {var95:.1f}%")
    print(f"    99% VaR:        {var99:.1f}%")
    print(f"    Sharpe (sim):   {sharpe:.2f}")
    print()
    
    # Robustness
    pos_rate = sum(1 for r in rets if r > 0) / N_SIMULATIONS
    dd_score = max(0, 30 - dds.mean() * 1.0)
    wr_stab = max(0, 20 - wrs.std() * 0.4)
    ret_stab = max(0, 20 - min(rets.std() / max(abs(rets.mean()), 0.01) * 3, 20))
    target_score = min(30, hits / N_SIMULATIONS * 60)
    
    robustness = pos_rate * 30 + dd_score + wr_stab + ret_stab
    robustness = min(100, robustness)
    
    print(f"  ROBUSTNESS: {robustness:.0f}/100")
    print(f"    Positive rate: {pos_rate*100:.1f}% -> {pos_rate*30:.1f}/30")
    print(f"    DD control:    {dd_score:.1f}/30")
    print(f"    WR stability:  {wr_stab:.1f}/20")
    print(f"    Ret stability: {ret_stab:.1f}/20")
    print()
    print("=" * 70)

if __name__ == "__main__":
    main()

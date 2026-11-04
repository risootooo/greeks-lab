#!/usr/bin/env python3
"""GreeksLab CLI demo.

1. Prices one option three ways (Black-Scholes / CRR binomial / Monte
   Carlo) and shows they agree within tolerance.
2. Loads the bundled *real* NIFTY chain (extracted from the NSE bhavcopy
   of 3 Nov 2026) and prints its analytics: ATM IV, smile range, parity
   diagnostic, GEX flip level, max pain.

Run:  python main.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from greekslab import bs_price, binomial_price, mc_price, all_greeks
from greekslab import chain as ch


def demo_pricing():
    S, K, T, r, q, sigma = 23800.0, 23800.0, 6 / 365, 0.065, 0.0, 0.13
    bs = bs_price(S, K, T, r, q, sigma, "CE")
    bino = binomial_price(S, K, T, r, q, sigma, "CE", steps=800)
    mc, se = mc_price(S, K, T, r, q, sigma, "CE", n_paths=400_000, seed=7)
    print("=== Three pricers, one option (NIFTY-style ATM call, 6 days) ===")
    print(f"Black-Scholes-Merton : {bs:10.2f}")
    print(f"CRR binomial (800)   : {bino:10.2f}   (vs BS {bino - bs:+.2f})")
    print(f"Monte Carlo (400k)   : {mc:10.2f} ± {se:.2f} SE "
          f"({abs(mc - bs) / se:.1f} SE from BS)")
    g = all_greeks(S, K, T, r, q, sigma, "CE")
    print("Greeks:", ", ".join(f"{k}={v:.4f}" for k, v in g.items()))
    print()


def demo_chain():
    path = os.path.join(os.path.dirname(__file__), "data", "sample_nifty_chain.csv")
    raw = pd.read_csv(path)
    spot = float(raw["spot"].iloc[0])
    chain = ch.add_iv(raw)
    atm, atm_strike = ch.atm_iv(chain)
    sm = ch.smile(chain)
    gex = ch.gamma_exposure(chain)
    flip = ch.gamma_flip_level(gex)
    pain = ch.max_pain(chain)
    par = ch.parity_diagnostics(chain)
    lot = int(raw["lot_size"].iloc[0])
    print("=== Real NIFTY chain — NSE bhavcopy, 3 Nov 2026 "
          f"(expiry {raw['expiry'].iloc[0]}, {int(raw['days_to_expiry'].iloc[0])} days) ===")
    print(f"Spot (UndrlygPric)   : {spot:,.2f}   lot size {lot}")
    print(f"Liquid strikes (OI>0): {chain['strike'].nunique()}")
    print(f"ATM IV @ {atm_strike:,.0f}      : {atm * 100:.2f}%")
    print(f"Smile IV range       : {sm['iv'].min() * 100:.2f}% .. {sm['iv'].max() * 100:.2f}%")
    if par:
        print(f"Parity implied fwd   : {par['implied_forward']:,.0f} "
              f"({par['forward_minus_spot']:+,.0f} vs spot, resid sd "
              f"{par['residual_std_points']:.0f} pts)")
    print(f"Net GEX total        : {gex['gex_rs'].sum() / 1e7:+,.1f} Rs crore "
          f"per 1% move")
    print(f"Gamma flip level     : {flip:,.0f}")
    print(f"Max pain             : {pain:,.0f} "
          f"({(pain / spot - 1) * 100:+.2f}% vs spot)")


if __name__ == "__main__":
    demo_pricing()
    demo_chain()

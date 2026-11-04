"""Multi-leg option strategy builder.

A ``Strategy`` is a list of ``Leg`` objects (long/short, any strike/kind,
traded at a known premium). From the legs you get:
  * payoff at expiry over any underlying grid (exact, piecewise linear)
  * aggregate Greeks at any (S, T, sigma) using the analytic Greeks
  * net premium (debit positive / credit negative, per share)
  * max profit / max loss on a wide grid, and breakeven levels
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import greeks as _g


@dataclass
class Leg:
    kind: str          # 'CE' or 'PE'
    strike: float
    qty: int           # +1 long, -1 short (per contract unit)
    premium: float     # premium paid per share when the leg was opened

    def payoff(self, S):
        intrinsic = (np.maximum(S - self.strike, 0.0) if self.kind == "CE"
                     else np.maximum(self.strike - S, 0.0))
        return self.qty * (intrinsic - self.premium)


@dataclass
class Strategy:
    name: str
    legs: list = field(default_factory=list)

    # -- construction helpers -------------------------------------------------
    def add(self, kind, strike, qty, premium):
        self.legs.append(Leg(kind, float(strike), int(qty), float(premium)))
        return self

    # -- analytics ------------------------------------------------------------
    def payoff(self, S):
        S = np.asarray(S, dtype=float)
        total = np.zeros_like(S)
        for leg in self.legs:
            total = total + leg.payoff(S)
        return total

    def net_premium(self):
        """Net debit per share (positive = paid, negative = received)."""
        return float(sum(leg.qty * leg.premium for leg in self.legs))

    def greeks(self, S, T, r, q, sigma):
        """Aggregate position Greeks at one underlying state."""
        keys = ["delta", "gamma", "theta", "vega", "rho",
                "vanna", "charm", "vomma"]
        out = {k: 0.0 for k in keys}
        for leg in self.legs:
            g = _g.all_greeks(S, leg.strike, T, r, q, sigma, leg.kind)
            for k in keys:
                out[k] += leg.qty * g[k]
        return out

    def risk_profile(self, S_grid=None):
        """Max profit/loss and breakevens over a wide expiry grid."""
        if S_grid is None:
            strikes = [leg.strike for leg in self.legs] or [100.0]
            lo = max(0.0, min(strikes) * 0.5)
            hi = max(strikes) * 1.6 + 1.0
            S_grid = np.linspace(lo, hi, 20001)
        S_grid = np.asarray(S_grid, dtype=float)
        pnl = self.payoff(S_grid)
        breakevens = []
        for i in range(1, len(S_grid)):
            if pnl[i - 1] == 0:
                breakevens.append(float(S_grid[i - 1]))
            elif pnl[i - 1] * pnl[i] < 0:
                frac = pnl[i - 1] / (pnl[i - 1] - pnl[i])
                breakevens.append(float(S_grid[i - 1]
                                        + frac * (S_grid[i] - S_grid[i - 1])))
        return {
            "max_profit": float(pnl.max()),
            "max_loss": float(pnl.min()),
            "breakevens": breakevens,
            "net_premium": self.net_premium(),
        }


# -- named builders (premiums supplied by the caller, e.g. from a chain) -----

def long_straddle(K, ce_premium, pe_premium):
    return (Strategy(f"Long Straddle {K:g}")
            .add("CE", K, +1, ce_premium).add("PE", K, +1, pe_premium))


def long_strangle(K_call, K_put, ce_premium, pe_premium):
    return (Strategy(f"Long Strangle {K_put:g}/{K_call:g}")
            .add("CE", K_call, +1, ce_premium).add("PE", K_put, +1, pe_premium))


def iron_condor(K1, K2, K3, K4, p1, p2, p3, p4):
    """Short K2 put / long K1 put / short K3 call / long K4 call,
    K1 < K2 < spot < K3 < K4. Premiums in leg order (K1 put, K2 put,
    K3 call, K4 call)."""
    return (Strategy(f"Iron Condor {K1:g}/{K2:g}/{K3:g}/{K4:g}")
            .add("PE", K1, +1, p1).add("PE", K2, -1, p2)
            .add("CE", K3, -1, p3).add("CE", K4, +1, p4))


def bull_call_spread(K_long, K_short, long_premium, short_premium):
    return (Strategy(f"Bull Call Spread {K_long:g}/{K_short:g}")
            .add("CE", K_long, +1, long_premium)
            .add("CE", K_short, -1, short_premium))


def bear_put_spread(K_long, K_short, long_premium, short_premium):
    """Long the higher put, short the lower put (K_long > K_short)."""
    return (Strategy(f"Bear Put Spread {K_short:g}/{K_long:g}")
            .add("PE", K_long, +1, long_premium)
            .add("PE", K_short, -1, short_premium))

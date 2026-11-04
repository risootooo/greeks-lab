#!/usr/bin/env python3
"""Build docs/dashboard.html from the bundled sample chain + cases_data.json."""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from greekslab import chain as ch
from greekslab.report import build_dashboard

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main():
    raw = pd.read_csv(os.path.join(ROOT, "data", "sample_nifty_chain.csv"))
    with open(os.path.join(ROOT, "docs", "cases_data.json")) as fh:
        d = json.load(fh)
    chain = ch.add_iv(raw)
    spot = d["spot"]
    sm = ch.smile(chain)
    sm = sm[(sm["strike"] >= spot * 0.90) & (sm["strike"] <= spot * 1.10)]
    gex = ch.gamma_exposure(chain)
    cards = [
        ("Case A — ATM IV (3 Nov 2026)",
         f"NIFTY spot <span class='num'>{spot:,.2f}</span>, expiry "
         f"{d['expiry']} ({d['days_to_expiry']} days). ATM "
         f"{d['atm_strike']:,.0f} CE IV <span class='num'>"
         f"{d['atm_ce_iv_pct']:.2f}%</span> / PE IV <span class='num'>"
         f"{d['atm_pe_iv_pct']:.2f}%</span> — the CE/PE gap is itself a "
         f"finding (see parity diagnostic)."),
        ("Case A — Gamma flip & max pain",
         f"Net dealer GEX <span class='num'>{d['net_gex_rs_crore']:+,.0f} "
         f"₹ crore</span> per 1% move; gamma flip at <span class='num'>"
         f"{d['gamma_flip']:,.0f}</span>; max pain <span class='num'>"
         f"{d['max_pain']:,.0f}</span> ({d['max_pain_vs_spot_pct']:+.2f}% "
         f"vs spot)."),
        ("Case A — Parity diagnostic",
         f"Put-call parity on settlement prints implies a forward of "
         f"<span class='num'>{d['parity']['implied_forward']:,.0f}</span> "
         f"({d['parity']['forward_minus_spot']:+,.0f} vs spot, residual "
         f"sd {d['parity']['residual_std_points']:.0f} pts). The feed is "
         f"not parity-clean — GreeksLab measures it instead of hiding it."),
        ("Case B — Theta bleed (real, 5 sessions)",
         f"The rolling ATM straddle of the 9 Nov expiry fell from "
         f"<span class='num'>{d['theta_series'][0]['straddle']:.2f}</span> "
         f"to <span class='num'>{d['theta_series'][-1]['straddle']:.2f}"
         f"</span> points between 28 Oct and 3 Nov 2026: "
         f"<span class='num'>−{d['theta_decay_pts']:.1f} pts "
         f"(−{d['theta_decay_pct']:.1f}%, ₹{d['theta_decay_rs_per_lot']:,.0f}"
         f" per lot)</span> — while spot rallied +1,112 points."),
    ]
    out = build_dashboard(sm, gex, cards,
                          os.path.join(ROOT, "docs", "dashboard.html"),
                          spot=spot)
    print("wrote", out)


if __name__ == "__main__":
    main()

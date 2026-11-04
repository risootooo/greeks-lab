#!/usr/bin/env python3
"""Regenerate data/sample_nifty_chain.csv and docs/cases_data.json from the
full NSE bhavcopy archive.

The full archive (220 daily F&O files, ~267 MB) is NOT shipped with the
repo. If you have it, point BHAV_DIR at it:

    BHAV_DIR=/path/to/bhavcopy python tools/build_sample.py

It extracts:
  * the NIFTY nearest-live-expiry chain of 2026-11-03 (the repo sample);
  * the ATM straddle of the 2026-11-09 expiry across the five consecutive
    trading days 2026-10-28 .. 2026-11-03 (theta-bleed case study);
  * all headline analytics (IV smile, GEX, flip, max pain, parity check)
    into docs/cases_data.json, which docs/CASES.md and the dashboard quote.
"""

from __future__ import annotations

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from greekslab import chain as ch

BHAV_DIR = os.environ.get(
    "BHAV_DIR",
    os.path.expanduser("~/workspace/trading/india-options-paper/data/bhavcopy"))
MAIN_DAY = "20261103"
THETA_DAYS = ["20261028", "20261029", "20261030", "20261102", "20261103"]
THETA_EXPIRY = pd.Timestamp("2026-11-09").date()
OUT_DIR = os.path.join(os.path.dirname(__file__), "..")
LOT_FALLBACK_NOTE = "lot size read from NewBrdLotQty in the bhavcopy itself"


def day_path(day):
    if day == MAIN_DAY:
        return os.path.join(
            BHAV_DIR, "BhavCopy_NSE_FO_0_0_0_20261103_F_0000.csv")
    return os.path.join(BHAV_DIR, f"fo_{day}.zip")


def main():
    raw = ch.load_bhavcopy(day_path(MAIN_DAY))
    chain = ch.extract_chain(raw)
    chain.to_csv(os.path.join(OUT_DIR, "data", "sample_nifty_chain.csv"),
                 index=False)

    chain_iv = ch.add_iv(chain)
    atm, atm_strike = ch.atm_iv(chain_iv)
    sm = ch.smile(chain_iv)
    gex = ch.gamma_exposure(chain_iv)
    flip = ch.gamma_flip_level(gex)
    pain = ch.max_pain(chain_iv)
    par = ch.parity_diagnostics(chain_iv)
    spot = float(chain["spot"].iloc[0])
    lot = int(chain["lot_size"].iloc[0])

    smile_min = sm.loc[sm["iv"].idxmin()]
    smile_max = sm.loc[sm["iv"].idxmax()]
    band = sm[(sm["strike"] >= spot * 0.90) & (sm["strike"] <= spot * 1.10)]
    band_pe = band[band["kind"] == "PE"].reset_index(drop=True)
    band_ce = band[band["kind"] == "CE"].reset_index(drop=True)
    atm_rows = chain_iv[chain_iv["strike"] == atm_strike]
    atm_ce_iv = atm_rows.loc[atm_rows["kind"] == "CE", "iv"]
    atm_pe_iv = atm_rows.loc[atm_rows["kind"] == "PE", "iv"]

    frames = [ch.load_bhavcopy(day_path(d)) for d in THETA_DAYS]
    strad = ch.straddle_series(frames, THETA_EXPIRY)
    first, last = strad.iloc[0], strad.iloc[-1]
    total_decay_pts = float(first["straddle"] - last["straddle"])
    total_decay_pct = float(total_decay_pts / first["straddle"] * 100.0)
    fixed_decay_pts = float(first["fixed_straddle"] - last["fixed_straddle"])
    fixed_decay_pct = float(fixed_decay_pts / first["fixed_straddle"] * 100.0)

    data = {
        "trade_date": str(chain["trade_date"].iloc[0]),
        "expiry": str(chain["expiry"].iloc[0]),
        "days_to_expiry": int(chain["days_to_expiry"].iloc[0]),
        "spot": spot,
        "lot_size": lot,
        "liquid_strikes": int(chain_iv["strike"].nunique()),
        "atm_strike": atm_strike,
        "atm_iv_pct": atm * 100,
        "atm_ce_iv_pct": float(atm_ce_iv.iloc[0] * 100) if len(atm_ce_iv) else None,
        "atm_pe_iv_pct": float(atm_pe_iv.iloc[0] * 100) if len(atm_pe_iv) else None,
        "smile_band_min_iv_pct": float(band["iv"].min() * 100),
        "smile_band_max_iv_pct": float(band["iv"].max() * 100),
        "smile_put_5pct_otm_iv_pct": float(
            band_pe.iloc[(band_pe["strike"] - spot * 0.95).abs().argsort()
                         .iloc[0]]["iv"] * 100) if len(band_pe) else None,
        "smile_call_5pct_otm_iv_pct": float(
            band_ce.iloc[(band_ce["strike"] - spot * 1.05).abs().argsort()
                         .iloc[0]]["iv"] * 100) if len(band_ce) else None,
        "smile_min": {"strike": float(smile_min["strike"]),
                      "iv_pct": float(smile_min["iv"] * 100),
                      "kind": smile_min["kind"]},
        "smile_max": {"strike": float(smile_max["strike"]),
                      "iv_pct": float(smile_max["iv"] * 100),
                      "kind": smile_max["kind"]},
        "parity": par,
        "net_gex_rs_crore": float(gex["gex_rs"].sum() / 1e7),
        "gamma_flip": flip,
        "max_pain": pain,
        "max_pain_vs_spot_pct": float((pain / spot - 1) * 100),
        "theta_series": [
            {"date": str(r["date"]), "spot": float(r["spot"]),
             "days_to_expiry": int(r["days_to_expiry"]),
             "atm_strike": float(r["atm_strike"]),
             "ce": float(r["ce"]), "pe": float(r["pe"]),
             "straddle": float(r["straddle"]),
             "fixed_strike": float(r["fixed_strike"]),
             "fixed_straddle": float(r["fixed_straddle"])}
            for _, r in strad.iterrows()
        ],
        "theta_decay_pts": total_decay_pts,
        "theta_decay_pct": total_decay_pct,
        "theta_decay_rs_per_lot": total_decay_pts * lot,
        "fixed_decay_pts": fixed_decay_pts,
        "fixed_decay_pct": fixed_decay_pct,
        "fixed_decay_rs_per_lot": fixed_decay_pts * lot,
    }
    with open(os.path.join(OUT_DIR, "docs", "cases_data.json"), "w") as fh:
        json.dump(data, fh, indent=2)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()

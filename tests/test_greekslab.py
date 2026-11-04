"""GreeksLab test suite.

Run: /path/to/python -m pytest tests -q   (numpy/pandas/scipy + pytest)
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from greekslab import (bs_price, binomial_price, mc_price, all_greeks,
                       implied_vol)
from greekslab import greeks as G
from greekslab import chain as ch
from greekslab import strategies as st

S, K, T, R, Q, SIG = 100.0, 100.0, 0.5, 0.05, 0.01, 0.22


# ---------------------------------------------------------------- pricing
@pytest.mark.parametrize("kind", ["CE", "PE"])
def test_put_call_parity(kind):
    c = bs_price(S, K, T, R, Q, SIG, "CE")
    p = bs_price(S, K, T, R, Q, SIG, "PE")
    lhs = c - p
    rhs = S * np.exp(-Q * T) - K * np.exp(-R * T)
    assert lhs == pytest.approx(rhs, abs=1e-10)


@pytest.mark.parametrize("kind", ["CE", "PE"])
def test_binomial_converges_to_bs(kind):
    bs = bs_price(S, K, T, R, Q, SIG, kind)
    bino = binomial_price(S, K, T, R, Q, SIG, kind, steps=2000)
    assert bino == pytest.approx(bs, abs=0.01)


@pytest.mark.parametrize("kind", ["CE", "PE"])
def test_american_put_worth_at_least_european(kind):
    euro = binomial_price(90.0, 110.0, 1.0, 0.08, 0.0, 0.25, "PE",
                          steps=400, american=False)
    amer = binomial_price(90.0, 110.0, 1.0, 0.08, 0.0, 0.25, "PE",
                          steps=400, american=True)
    assert amer >= euro - 1e-9
    if kind == "PE":
        assert amer > euro + 0.05          # real early-exercise premium


@pytest.mark.parametrize("kind", ["CE", "PE"])
def test_mc_within_3se_of_bs(kind):
    bs = bs_price(S, K, T, R, Q, SIG, kind)
    mc, se = mc_price(S, K, T, R, Q, SIG, kind, n_paths=200_000, seed=3)
    assert se > 0
    assert abs(mc - bs) <= 3 * se


def test_bs_at_expiry_is_intrinsic():
    assert bs_price(120.0, 100.0, 0.0, R, Q, SIG, "CE") == 20.0
    assert bs_price(80.0, 100.0, 0.0, R, Q, SIG, "PE") == 20.0


def test_bs_limits():
    # Deep ITM call ~ discounted intrinsic; huge vol call -> S e^{-qT}
    deep = bs_price(200.0, 100.0, T, R, Q, SIG, "CE")
    assert deep == pytest.approx(200 * np.exp(-Q * T) - 100 * np.exp(-R * T),
                                 abs=0.05)


# ----------------------------------------------------------------- greeks
@pytest.mark.parametrize("kind", ["CE", "PE"])
@pytest.mark.parametrize("name", ["delta", "gamma", "theta", "vega", "rho",
                                  "vanna", "charm", "vomma"])
def test_analytic_greek_matches_finite_difference(name, kind):
    analytic = getattr(G, name)(S, K, T, R, Q, SIG, kind) \
        if name in ("delta", "theta", "rho", "charm") else \
        getattr(G, name)(S, K, T, R, Q, SIG)
    fd = G.finite_diff_greek(name, S, K, T, R, Q, SIG, kind)
    tol = {"gamma": 2e-4, "charm": 2e-4, "vomma": 5e-2}.get(name, 2e-3)
    assert analytic == pytest.approx(fd, abs=tol), name


@pytest.mark.parametrize("kind", ["CE", "PE"])
def test_second_order_greeks_otm(kind):
    # repeat the FD check away from the money, where vanna/charm bend
    s2, k2 = 100.0, 115.0
    for name in ["vanna", "charm", "vomma"]:
        analytic = getattr(G, name)(s2, k2, T, R, Q, SIG, kind) \
            if name == "charm" else getattr(G, name)(s2, k2, T, R, Q, SIG)
        fd = G.finite_diff_greek(name, s2, k2, T, R, Q, SIG, kind)
        tol = {"vomma": 5e-2}.get(name, 3e-3)
        assert analytic == pytest.approx(fd, abs=tol), name


def test_delta_bounds_and_gamma_positive():
    assert 0 < G.delta(S, K, T, R, Q, SIG, "CE") < 1
    assert -1 < G.delta(S, K, T, R, Q, SIG, "PE") < 0
    assert G.gamma(S, K, T, R, Q, SIG) > 0
    # put-call delta parity: delta_C - delta_P = e^{-qT}
    diff = G.delta(S, K, T, R, Q, SIG, "CE") - G.delta(S, K, T, R, Q, SIG, "PE")
    assert diff == pytest.approx(np.exp(-Q * T), abs=1e-10)


def test_theta_negative_for_long_atm():
    assert G.theta(S, K, T, R, Q, SIG, "CE") < 0
    assert G.theta(S, K, T, R, Q, SIG, "PE") < 0


# --------------------------------------------------------------------- iv
@pytest.mark.parametrize("kind", ["CE", "PE"])
@pytest.mark.parametrize("sigma_true", [0.08, 0.13, 0.25, 0.60])
def test_iv_round_trip(kind, sigma_true):
    price = bs_price(S, K, T, R, Q, sigma_true, kind)
    iv = implied_vol(price, S, K, T, R, Q, kind)
    assert iv == pytest.approx(sigma_true, abs=1e-6)


def test_iv_below_intrinsic_returns_nan():
    # a call quoted under intrinsic has no arbitrage-consistent IV
    iv = implied_vol(1.0, 200.0, 100.0, T, R, 0.0, "CE")
    assert np.isnan(iv)


def test_iv_monotone_in_price():
    p1 = bs_price(S, K, T, R, Q, 0.15, "CE")
    p2 = bs_price(S, K, T, R, Q, 0.30, "CE")
    assert implied_vol(p2, S, K, T, R, Q, "CE") > implied_vol(p1, S, K, T, R, Q, "CE")


# ------------------------------------------------------------------ chain
def _toy_bhav(rows):
    return pd.DataFrame(rows)


def test_chain_parser_and_max_pain():
    rows = []
    spot = 100.0
    # expiry 7 days after trade date; puts concentrated at 100 -> pain 100
    for strike, ce_oi, pe_oi in [(90, 10, 500), (100, 10, 900), (110, 500, 10)]:
        for kind, oi in (("CE", ce_oi), ("PE", pe_oi)):
            rows.append({
                "TradDt": "2026-11-03", "FinInstrmTp": "IDO",
                "TckrSymb": "NIFTY", "XpryDt": "2026-11-10",
                "StrkPric": strike, "OptnTp": kind,
                "ClsPric": 2.0, "UndrlygPric": spot, "OpnIntrst": oi,
                "TtlTradgVol": 100, "NewBrdLotQty": 65,
            })
    chain = ch.extract_chain(_toy_bhav(rows))
    assert chain["days_to_expiry"].iloc[0] == 7
    assert ch.max_pain(chain) == 100.0


def test_sample_chain_loads_and_iv_solves():
    path = os.path.join(os.path.dirname(__file__), "..", "data",
                        "sample_nifty_chain.csv")
    raw = pd.read_csv(path)
    chain = ch.add_iv(raw)
    # Every OTM option in the real chain solves. Many ITM prints sit below
    # the spot-intrinsic no-arb bound (the feed's parity deviation, see
    # docs/CASES.md) and correctly return NaN instead of a fantasy IV.
    otm = chain[chain["otm"]]
    assert otm["iv"].notna().mean() == 1.0
    assert chain["iv"].notna().mean() > 0.70
    assert chain["strike"].nunique() > 60
    gex = ch.gamma_exposure(chain)
    assert np.isfinite(gex["gex_rs"]).all()


# -------------------------------------------------------------- strategies
def test_long_straddle_identities():
    s = st.long_straddle(100.0, 5.0, 4.0)
    assert s.net_premium() == pytest.approx(9.0)
    assert s.payoff(np.array([100.0]))[0] == pytest.approx(-9.0)
    rp = s.risk_profile()
    assert rp["max_loss"] == pytest.approx(-9.0, abs=0.01)   # grid-sampled
    wide = s.risk_profile(S_grid=np.linspace(0, 400, 40001))
    assert wide["max_profit"] == pytest.approx(291.0, abs=0.1)  # at S=400
    assert len(rp["breakevens"]) == 2
    assert rp["breakevens"][0] == pytest.approx(91.0, abs=0.05)
    assert rp["breakevens"][1] == pytest.approx(109.0, abs=0.05)


def test_iron_condor_bounded_risk():
    ic = st.iron_condor(90, 95, 105, 110, 0.5, 2.0, 2.0, 0.5)
    rp = ic.risk_profile()
    credit = -ic.net_premium()
    assert credit == pytest.approx(3.0)
    assert rp["max_profit"] == pytest.approx(3.0)
    assert rp["max_loss"] == pytest.approx(-(5.0 - 3.0))
    assert len(rp["breakevens"]) == 2


def test_bull_call_spread_payoff():
    bcs = st.bull_call_spread(100, 110, 6.0, 2.0)
    assert bcs.payoff(np.array([90.0]))[0] == pytest.approx(-4.0)
    assert bcs.payoff(np.array([120.0]))[0] == pytest.approx(6.0)


def test_strategy_greeks_long_straddle_is_long_gamma_vega_short_theta():
    s = st.long_straddle(100.0, 5.0, 4.0)
    g = s.greeks(S, T, R, Q, SIG)
    assert g["gamma"] > 0 and g["vega"] > 0 and g["theta"] < 0


def test_vertical_spread_greeks_net_small_delta():
    bcs = st.bull_call_spread(100, 110, 6.0, 2.0)
    g = bcs.greeks(S, T, R, Q, SIG)
    single = G.delta(S, 100.0, T, R, Q, SIG, "CE")
    assert 0 < g["delta"] < single

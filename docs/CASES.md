# Case Studies — Real NSE Data, Real Numbers

Every number in this document is an output of the code in this repository
run on real NSE F&O bhavcopy files. Reproduce them with:

```bash
python tools/build_sample.py      # regenerates docs/cases_data.json
python tools/build_dashboard.py   # regenerates docs/dashboard.html
python main.py                    # prints the Case A headline analytics
```

Conventions (see README for the full list): premiums = bhavcopy `ClsPric`,
underlying = `UndrlygPric`, r = 6.5%, q = 0, T = actual days/365, IV from
OTM options for the smile, lot size 65 read from the file itself.

---

## Case A — The 3 Nov 2026 NIFTY chain, taken apart

**Input:** NSE bhavcopy of Tuesday 3 Nov 2026. Nearest live expiry
9 Nov 2026 (6 days; the series expiring *on* 3 Nov has T = 0 and no IV).
Spot (index close in the file): **23,810.85**. Liquid strikes (OI > 0):
**114**.

### The smile is a skew with wings, and it is not subtle

| Point on the smile | IV |
|---|---|
| ATM 23,800 CE | **10.76%** |
| ATM 23,800 PE | **19.92%** |
| Smile minimum (23,850 CE) | **11.23%** |
| 5% OTM put (~22,600 PE) | **24.42%** |
| 5% OTM call (~25,000 CE) | **17.64%** |
| −10% put wing (21,450 PE) | **36.36%** |
| Deepest put wing (20,050 PE) | **52.08%** |

Read: downside protection is priced far richer than upside participation —
a 5%-OTM put carries ≈ **6.8 vol points** more implied vol than the
equidistant call, and the put wing keeps rising monotonically to 36%+ at
−10%. This is the classic equity-index skew, measured here strike by
strike from settlement premiums rather than drawn from a textbook.

### The ATM CE/PE gap is a data-quality finding, not a typo

At the same strike and expiry, put-call parity forces one IV. The file
gives two: 10.76% (CE) vs 19.92% (PE). GreeksLab's parity diagnostic
quantifies the whole chain at once — regressing (C − P) on K across 72
strikes:

- **Implied forward: 23,690** — 121 points *below* the quoted spot
- Fitted discount factor 0.9509 vs the theoretical e^(−rT) = 0.9989
- Residual standard deviation: **155 points**

Consistent with that, **100% of OTM options solve for an IV, while 58% of
ITM prints sit below the spot-intrinsic no-arbitrage bound** (a stale or
model-marked settlement print can do that; a tradable price cannot).
GreeksLab therefore (a) builds the smile from OTM options only, (b)
returns NaN — never a fantasy IV — for bound-violating prints, and (c)
ships the diagnostic so users can see the feed's quality for themselves.
Most retail chain tools silently average this away.

### Dealer gamma: spot sat 61 points under the flip

- **Net GEX: +₹12,619 crore per 1% spot move** (dealers net long gamma at
  spot under the standard positioning model — rallies get sold into,
  dips get bought; realised vol is damped while spot stays in this zone)
- **Gamma flip level: 23,872** — just **+0.26% above spot**. A close above
  it flips the modelled dealer book to short gamma, where hedging flows
  *amplify* moves instead of absorbing them.
- **Max pain: 23,600** — 211 points (−0.89%) below spot for the 9 Nov
  expiry: the level that minimises total intrinsic payout to holders.

Flip and max pain disagree by 272 points; the document records both
because they answer different questions (flow regime vs expiry payout).

---

## Case B — Theta bleed, measured on real premiums (28 Oct → 3 Nov 2026)

The rolling at-the-money straddle of the **9 Nov 2026 expiry**, repriced
from the bhavcopy close every session (strike rolled to the money daily,
exactly as a desk would hold it):

| Date | Spot | Days to expiry | ATM strike | CE | PE | Straddle |
|---|---|---|---|---|---|---|
| Wed 28 Oct 2026 | 22,698.85 | 12 | 22,700 | 275.45 | 248.35 | **523.80** |
| Thu 29 Oct 2026 | 22,936.75 | 11 | 22,950 | 252.30 | 201.00 | **453.30** |
| Fri 30 Oct 2026 | 23,053.10 | 10 | 23,050 | 210.90 | 209.40 | **420.30** |
| Mon 2 Nov 2026 | 23,440.80 | 7 | 23,450 | 137.35 | 234.65 | **372.00** |
| Tue 3 Nov 2026 | 23,810.85 | 6 | 23,800 | 149.90 | 224.75 | **374.65** |

**Total decay: −149.15 points (−28.5%) in five sessions — ₹9,695 per lot**
(lot 65) paid by the straddle *buyer* to the seller — in a week when spot
**rallied +1,112 points (+4.9%)**. Direction was not quiet; the straddle
still bled, because six calendar days of the twelve remaining days of
life expired (note the Fri→Mon step: three calendar days of theta, one
trading day). Average bleed ≈ **29.8 points per session**. That is the
hurdle every long-premium NIFTY trade must clear *before* it earns a
single rupee — roughly ₹1,940 per lot, per day, at this vol level.

---

## Case C — Why directional option buying died on real premiums

**The test (Samrat Banerjee, 2026-11-03, engine in the author's research
workspace):** three popular index strategies — Opening Range Breakout
(ORB), 5-EMA, and Order Block — re-run over 60 days of real NSE bhavcopy
premiums, entering and exiting actual option contracts at their real
settlement prices, in two strategy designs each. On **index points**,
variants of these systems are all over social media with glowing
backtests. On **real premiums**, every single one lost:

| Strategy | Design 1 PF | Design 2 PF |
|---|---|---|
| ORB | 0.44 | 0.38 |
| 5-EMA | 0.78 | 0.59 |
| Order Block | 0.59 | 0.89 |

All six runs: **profit factor < 0.9 after theta and costs.**

### What the index-point backtest hid — in Greeks

1. **Delta is not 1.** An index backtest books the full index move. An
   ATM option captures roughly half of it at entry (Δ ≈ 0.5), and less as
   the trade ages or moves away from the strike. Half the advertised
   edge evaporates before anything else goes wrong.
2. **Theta is a fixed daily tax.** Case B measured it on this very
   chain family: ≈ 30 points/day on the ATM straddle, ≈ ₹1,940/lot/day.
   A day-trade held for hours still pays a slice of it; a strategy whose
   average winner is a few tens of index points cannot outrun it.
3. **Vega works against the event buyer.** Entries triggered by a
   breakout happen *after* implied vol has already expanded; the
   post-move IV crush taxes the exit even when direction is right.
4. **Gamma helps only near the strike, briefly.** The convexity that
   makes options attractive is concentrated near ATM near expiry —
   precisely where theta is most violent. The Greeks are a package deal.
5. **Settlement ≠ tradable.** Case A's parity diagnostic shows the
   feed's own prints deviate from parity by ~155 points (residual sd);
   real fills are worse than settlement marks, never better.

**The transferable rule:** any directional system whose average gross
win, in index points × realistic delta, does not exceed roughly **2× the
daily theta + spread + cost drag** is structurally unprofitable in
options no matter how it looks on the index chart. Test on real premiums
or do not test at all. GreeksLab exists to make that test cheap:
price the legs, aggregate the Greeks, and look at the theta line before
the equity curve.

---

*Data: NSE F&O bhavcopy (exchange-published end-of-day file). Analysis is
educational research, not investment advice.*

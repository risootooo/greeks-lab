# Data

`sample_nifty_chain.csv` — the NIFTY option chain of the nearest live
expiry (9 Nov 2026) extracted from the official NSE F&O bhavcopy of
3 Nov 2026 (`BhavCopy_NSE_FO_0_0_0_20261103_F_0000.csv`). 246 rows,
one per (strike, CE/PE), with premium (close), spot, open interest,
volume and the contract lot size (65) exactly as published.

It is deliberately small (22 KB) so the whole repo — chain analytics,
case studies, tests, dashboard — runs offline. The full archive it came
from is 220 daily F&O bhavcopy files (~267 MB) and is not redistributed.

Regenerate from a full archive:

```bash
BHAV_DIR=/path/to/bhavcopy python tools/build_sample.py
```

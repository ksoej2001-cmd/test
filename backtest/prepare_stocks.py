"""Build cleaned month-end prices and monthly S&P 500 membership.

Inputs (not committed; about 1 GB) come from the y-not-finance data release,
https://github.com/PIMPOON/DATA/releases/tag/Y-Not-Finance :
  sp500_intraday_ohlcv_2020_2024.parquet    5-minute bars, unadjusted
  sp500_constituents_19800101_20251231.parquet

Outputs:
  data/stocks_monthly.csv      month-end price per ticker, split-adjusted
  data/sp500_members.csv       tickers in the index at each month-end
  data/stocks_cleaning.csv     what was changed or dropped, per ticker

Cleaning, in order:
  1. Bars more than 50% away from the day's median bar are dropped. The bar
     data mixes in stray prints, apparently from other share classes such as
     preferreds and rights. Daily price = median close of the day's last 12
     remaining bars.
  2. Prints more than 25% away from the median of the surrounding five days
     are dropped.
  3. Splits: the gap from the previous close to the median of the day's
     first six bars must be within 5% of a common split ratio, the
     close-to-close move within 12% of it, the new level must hold for the
     following days. For ratios of 2 or less, which a crash or a takeover jump
     can mimic, dollar volume must also stay under 3x its 20-day median, and
     days when the median stock moved more than 4% are skipped. At most one
     split per 60 trading days. Earlier prices are then divided by the
     ratio. MANUAL_SPLITS adds real splits these rules miss.
  4. Tickers that still have a daily move above 75% are dropped.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

OUT = Path(__file__).parent / "data"
RATIOS = [1.5, 2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 50]
# 3-for-2 split during the March 2020 selloff, when volume was high everywhere.
MANUAL_SPLITS = {"ODFL": [("2020-03-25", 1.5)]}


def daily_prices(path):
    """Return daily close, open and dollar volume, one column per ticker."""
    pf = pq.ParquetFile(path)
    parts = []
    cols = ["ticker", "date", "interval_start", "open", "close", "volume"]
    for i in range(pf.num_row_groups):
        t = pf.read_row_group(i, columns=cols).to_pandas()
        t = t.sort_values(["ticker", "interval_start"])
        day_med = t.groupby(["ticker", "date"]).close.transform("median")
        t = t[(t.close / day_med).between(1 / 1.5, 1.5)]
        t["dv"] = t.close * t.volume
        g = t.groupby(["ticker", "date"])
        parts.append(pd.DataFrame({
            "close": g.close.apply(lambda s: s.iloc[-12:].median()),
            "open": g.open.apply(lambda s: s.iloc[:6].median()),
            "dv": g.dv.sum(),
        }))
    d = pd.concat(parts)
    # A ticker's day can straddle two row groups; merge the two halves.
    d = d.groupby(level=[0, 1]).agg({"close": "last", "open": "first", "dv": "sum"})
    out = {}
    for c in d.columns:
        w = d[c].unstack("ticker")
        w.index = pd.to_datetime(w.index)
        out[c] = w.sort_index()
    return out


def drop_spikes(s):
    med = s.rolling(5, center=True, min_periods=3).median()
    bad = (np.log(s / med)).abs() > np.log(1.25)
    return s.mask(bad), int(bad.sum())


def adjust_splits(s, opens, dv, market):
    s = s.copy()
    v = s.dropna()
    dv_med = dv.rolling(20, min_periods=5).median().shift(1)
    found, last_i = [], -60
    for i in range(1, len(v) - 3):
        day = v.index[i]
        gap = v.iloc[i - 1] / opens.get(day, np.nan)
        move = v.iloc[i - 1] / v.iloc[i]
        if i - last_i < 60 or not np.isfinite(gap):
            continue
        busy = abs(market.get(day, 0)) > 0.04 or dv.get(day, np.nan) > 3 * dv_med.get(day, np.nan)
        for k in RATIOS:
            if busy and k <= 2:
                continue
            for ratio in (k, 1 / k):
                if abs(gap / ratio - 1) < 0.05 and abs(move / ratio - 1) < 0.12:
                    after = v.iloc[i : i + 4].median() / v.iloc[i]
                    if abs(after - 1) < 0.1:
                        s.loc[: v.index[i - 1]] /= ratio
                        v = s.dropna()
                        found.append(f"{day:%Y-%m-%d}:{ratio:g}")
                        last_i = i
    return s, found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True, help="directory with the two parquet files")
    a = ap.parse_args()

    d = daily_prices(a.src / "sp500_intraday_ohlcv_2020_2024.parquet")
    p = d["close"]
    market = p.pct_change(fill_method=None).median(axis=1)
    log, clean = [], {}
    for t in p.columns:
        s, n_spikes = drop_spikes(p[t])
        s, splits = adjust_splits(s, d["open"][t], d["dv"][t], market)
        for day, ratio in MANUAL_SPLITS.get(t, []):
            s.loc[s.index < day] /= ratio
            splits.append(f"{day}:{ratio:g}(manual)")
        worst = s.dropna().pct_change().abs().max()
        keep = bool(worst <= 0.75) if pd.notna(worst) else False
        log.append({"ticker": t, "spikes_dropped": n_spikes, "splits": " ".join(splits),
                    "max_daily_move": worst, "kept": keep})
        if keep:
            clean[t] = s
    pd.DataFrame(log).to_csv(OUT / "stocks_cleaning.csv", index=False, float_format="%.4f")

    daily = pd.DataFrame(clean).ffill(limit=5)
    monthly = daily.resample("ME").last()
    # A ticker's last month-end with no trades afterward is its delisting month.
    last = pd.DataFrame(clean).apply(lambda s: s.last_valid_index())
    for t, d in last.items():
        monthly.loc[monthly.index > d + pd.offsets.MonthEnd(0), t] = np.nan
    monthly.to_csv(OUT / "stocks_monthly.csv", float_format="%.4f")

    c = pd.read_parquet(a.src / "sp500_constituents_19800101_20251231.parquet")
    c["date"] = pd.to_datetime(c["date"])
    c = c[(c.date >= "2019-12-01") & (c.date <= "2024-12-31")]
    month_end = c.groupby(c.date.dt.to_period("M")).date.transform("max")
    m = c[c.date == month_end].copy()
    m["date"] = m.date + pd.offsets.MonthEnd(0)
    m[["date", "ticker"]].sort_values(["date", "ticker"]).to_csv(OUT / "sp500_members.csv", index=False)

    n_drop = sum(not r["kept"] for r in log)
    print(f"tickers: {len(log)} kept: {len(clean)} dropped: {n_drop}")


if __name__ == "__main__":
    main()

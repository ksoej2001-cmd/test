"""Monthly market-timing backtest on the S&P 500 versus buy-and-hold.

Rules are chosen on the in-sample period only, then evaluated once on the
out-of-sample period. Run with --phase insample first, then --phase oos.

Data:
  data/sp500.csv  Shiller monthly S&P 500 (github.com/datasets/s-and-p-500).
                  Prices are monthly averages of daily closes.
  data/us10y.csv  US 10-year Treasury yield, monthly
                  (github.com/datasets/bond-yields-us-10y).
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"

IS_START, IS_END = "1872-01-01", "1949-12-01"
OOS_START = "1950-01-01"

COST = 0.001  # one-way cost per switch
# Shiller prices are monthly averages, so month-to-month returns are
# autocorrelated. A signal formed at month t is applied to the return of
# month t+2 to avoid trading on the averaging artifact.
LAG = 2
LOOKBACKS = range(3, 19)


def load():
    sp = pd.read_csv(DATA / "sp500.csv", parse_dates=["Date"]).set_index("Date")
    y10 = pd.read_csv(DATA / "us10y.csv", parse_dates=["Date"]).set_index("Date")["Rate"]

    price = sp["SP500"]
    # Dividends and yields are zero-filled where the source has no data yet.
    div = sp["Dividend"].replace(0.0, np.nan)
    dy = (div / price).ffill()  # carry the last known dividend yield forward
    rate = sp["Long Interest Rate"].replace(0.0, np.nan)
    rate = rate.combine_first(y10).ffill()

    df = pd.DataFrame({"price": price})
    df["stock_ret"] = (price + price * dy / 12) / price.shift(1) - 1
    df["cash_ret"] = rate.shift(1) / 100 / 12
    return df.dropna()


def signal(price, kind, n):
    if kind == "sma":
        return (price > price.rolling(n).mean()).astype(float)
    if kind == "mom":
        return (price / price.shift(n) > 1).astype(float)
    raise ValueError(kind)


def run(df, kind, n):
    w = signal(df["price"], kind, n).shift(LAG)
    switches = w.diff().abs().fillna(0)
    ret = w * df["stock_ret"] + (1 - w) * df["cash_ret"] - switches * COST
    return ret, w


def stats(ret, w=None):
    ret = ret.dropna()
    years = len(ret) / 12
    wealth = (1 + ret).cumprod()
    cagr = wealth.iloc[-1] ** (1 / years) - 1
    vol = ret.std() * np.sqrt(12)
    dd = (wealth / wealth.cummax() - 1).min()
    out = {
        "CAGR": cagr,
        "Vol": vol,
        "Sharpe(0)": ret.mean() * 12 / vol,
        "MaxDD": dd,
        "x100": wealth.iloc[-1],
    }
    if w is not None:
        w = w.loc[ret.index]
        out["InMkt"] = w.mean()
        out["Trades/yr"] = w.diff().abs().sum() / years
    return out


def table(rows):
    t = pd.DataFrame(rows).T
    fmt = {
        "CAGR": "{:.2%}", "Vol": "{:.2%}", "Sharpe(0)": "{:.2f}", "MaxDD": "{:.1%}",
        "x100": "{:,.1f}", "InMkt": "{:.0%}", "Trades/yr": "{:.2f}",
    }
    for c, f in fmt.items():
        if c in t:
            t[c] = t[c].map(lambda v, f=f: "" if pd.isna(v) else f.format(v))
    return t.to_string()


def period(s, start, end=None):
    return s.loc[start:end]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["insample", "oos"], required=True)
    ap.add_argument("--kind", choices=["sma", "mom"])
    ap.add_argument("--n", type=int)
    a = ap.parse_args()
    df = load()

    if a.phase == "insample":
        rows = {"Buy&Hold": stats(period(df["stock_ret"], IS_START, IS_END))}
        for kind in ("sma", "mom"):
            for n in LOOKBACKS:
                ret, w = run(df, kind, n)
                rows[f"{kind}{n}"] = stats(period(ret, IS_START, IS_END), w)
        print(f"In-sample {IS_START[:7]} .. {IS_END[:7]}")
        print(table(rows))
        best = max((k for k in rows if k != "Buy&Hold"), key=lambda k: rows[k]["CAGR"])
        print(f"\nBest in-sample CAGR: {best}")
        return

    if a.kind is None or a.n is None:
        ap.error("--phase oos needs --kind and --n")
    ret, w = run(df, a.kind, a.n)
    rows = {
        "Buy&Hold": stats(period(df["stock_ret"], OOS_START)),
        f"{a.kind}{a.n}": stats(period(ret, OOS_START), w),
    }
    end = df.index[-1].strftime("%Y-%m")
    print(f"Out-of-sample {OOS_START[:7]} .. {end}")
    print(table(rows))


if __name__ == "__main__":
    main()
